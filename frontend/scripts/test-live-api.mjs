/* global process, console, setTimeout, clearTimeout */
/** Real frontend client -> Vite proxy -> actual FastAPI -> disposable SQLite. */
import assert from 'node:assert/strict'
import { spawn } from 'node:child_process'
import { existsSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import path from 'node:path'
import { createServer } from 'vite'

const frontend = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const backend = path.resolve(frontend, '../backend')
const python = path.join(
  backend,
  '.venv',
  process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python',
)
if (!existsSync(python))
  throw new Error('Backend environment is missing. Run uv sync --locked in backend first.')

const child = spawn(python, [path.join(frontend, 'scripts/live-api-server.py')], {
  cwd: backend,
  windowsHide: true,
  stdio: ['pipe', 'pipe', 'pipe'],
})
let vite
let passed = 0
const check = (label, fn) => {
  fn()
  passed += 1
  console.log(`PASS ${label}`)
}

try {
  const fixture = await new Promise((resolve, reject) => {
    let buffer = ''
    const timeout = setTimeout(
      () => reject(new Error('Isolated API setup timed out. Port 18000 must be available.')),
      30_000,
    )
    child.once('error', () => {
      clearTimeout(timeout)
      reject(new Error('Could not start the isolated backend.'))
    })
    child.once('exit', (code) => {
      clearTimeout(timeout)
      reject(new Error(`Isolated backend exited before tests (code ${code}).`))
    })
    child.stdout.on('data', (chunk) => {
      buffer += chunk.toString()
      const newline = buffer.indexOf('\n')
      if (newline !== -1) {
        clearTimeout(timeout)
        try {
          resolve(JSON.parse(buffer.slice(0, newline)))
        } catch {
          reject(new Error('Invalid isolated fixture handshake.'))
        }
        buffer = ''
      }
    })
    // Drain internal startup messages without exposing configuration or credentials.
    child.stderr.on('data', () => undefined)
  })

  const origin = 'http://127.0.0.1:15173'
  vite = await createServer({
    root: frontend,
    configFile: path.join(frontend, 'vite.config.ts'),
    logLevel: 'error',
    define: { 'import.meta.env.VITE_API_BASE_URL': JSON.stringify(origin) },
    server: {
      host: '127.0.0.1',
      port: 15173,
      strictPort: true,
      proxy: { '/api': { target: 'http://127.0.0.1:18000', changeOrigin: true } },
    },
  })
  await vite.listen()
  const { claimsApi, ApiError } = await vite.ssrLoadModule('/src/lib/api/index.ts')
  const { clearSession, setSession, getSessionSnapshot } = await vite.ssrLoadModule(
    '/src/lib/api/session-store.ts',
  )
  const as = (actor) =>
    setSession(fixture.tokens[actor], fixture.ids[actor], Date.now() + 3_600_000)
  const expectApiError = async (promise, status, code) => {
    let error
    try {
      await promise
    } catch (value) {
      error = value
    }
    assert.ok(error instanceof ApiError, 'Expected a typed API error')
    assert.equal(error.status, status)
    assert.equal(error.code, code)
  }

  clearSession()
  await expectApiError(claimsApi.list(), 401, 'UNAUTHENTICATED')
  check('anonymous access receives 401', () => assert.equal(getSessionSnapshot().token, null))

  as('claimant')
  const created = await claimsApi.create({
    found_post_id: fixture.ids.second,
    evidence_description: 'Fictional frontend contract evidence TEST-123.',
  })
  check('POST creates a pending claim without exposing evidence in summary', () => {
    assert.equal(created.status, 'PENDING')
    assert.equal(created.version, 1)
    assert.equal('evidence' in created, false)
  })
  const page = await claimsApi.list({ relation: 'claimant', page: 1, page_size: 1 })
  check('GET list honors pagination and excludes private evidence', () => {
    assert.equal(page.page_size, 1)
    assert.equal(page.items.length, 1)
    assert.equal(page.has_next, true)
    assert.equal('evidence' in page.items[0], false)
  })
  const detail = await claimsApi.detail(created.id)
  check('GET detail returns authorized evidence', () => {
    assert.equal(detail.evidence.length, 1)
    assert.equal(
      detail.evidence[0].private_content,
      'Fictional frontend contract evidence TEST-123.',
    )
  })
  as('other')
  await expectApiError(claimsApi.detail(created.id), 404, 'CLAIM_NOT_FOUND')
  check('unrelated users cannot inspect private evidence', () => undefined)
  as('admin')
  await expectApiError(claimsApi.detail(created.id), 404, 'CLAIM_NOT_FOUND')
  check('administrator role does not bypass claim privacy', () => undefined)

  as('owner')
  const reviewerPage = await claimsApi.list({ relation: 'reviewer', page_size: 20 })
  check('owner can retrieve requests to review', () =>
    assert.ok(reviewerPage.items.some((item) => item.id === created.id)),
  )
  await expectApiError(
    claimsApi.approve(created.id, { expected_version: 99 }),
    409,
    'CLAIM_VERSION_CONFLICT',
  )
  check('stale versions receive 409', () => undefined)
  const rejected = await claimsApi.reject(created.id, {
    expected_version: 1,
    reason: 'Fictional verification did not match.',
  })
  check('PATCH reject transitions to rejected and increments version', () => {
    assert.equal(rejected.status, 'REJECTED')
    assert.equal(rejected.version, 2)
  })

  as('claimant')
  const next = await claimsApi.create({
    found_post_id: fixture.ids.second,
    evidence_description: 'Fictional second evidence for approved request.',
  })
  as('owner')
  const approved = await claimsApi.approve(next.id, { expected_version: next.version })
  check('PATCH approve transitions to approved', () => assert.equal(approved.status, 'APPROVED'))
  as('claimant')
  await expectApiError(
    claimsApi.complete(next.id, { expected_version: approved.version, receipt_confirmed: true }),
    409,
    'RETURN_NOT_READY',
  )
  check('completion is blocked until a real handover exists', () => undefined)
  const completed = await claimsApi.complete(fixture.prepared_claim, {
    expected_version: fixture.prepared_version,
    receipt_confirmed: true,
  })
  check('PATCH complete confirms the explicitly prepared handover fixture', () => {
    assert.equal(completed.status, 'RETURNED')
    assert.equal(completed.return_summary.status, 'CONFIRMED')
  })

  setSession('invalid-token', fixture.ids.claimant, Date.now() + 60_000)
  await expectApiError(claimsApi.list(), 401, 'UNAUTHENTICATED')
  check('invalid authentication clears the frontend session', () =>
    assert.equal(getSessionSnapshot().expired, true),
  )
  console.log(
    `\n${passed} live integration checks passed through Vite :15173 -> FastAPI :18000 (isolated SQLite).`,
  )
  console.log(
    'All six claims endpoints exercised. PostgreSQL concurrency and browser UI are not covered by this harness.',
  )
} finally {
  if (vite) await vite.close()
  child.stdin.end('stop\n')
  if (child.exitCode === null) {
    await new Promise((resolve) => {
      const timer = setTimeout(() => {
        child.kill()
        resolve()
      }, 15_000)
      child.once('exit', () => {
        clearTimeout(timer)
        resolve()
      })
    })
  }
}
