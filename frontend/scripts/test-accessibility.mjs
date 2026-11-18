/* global process, console, document */
import assert from 'node:assert/strict'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { mkdirSync, writeFileSync } from 'node:fs'
import { chromium } from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'
import { createServer } from 'vite'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const server = await createServer({
  root,
  logLevel: 'error',
  server: { host: '127.0.0.1', port: 15175, strictPort: true },
})
let browser
const reports = []
try {
  await server.listen()
  browser = await chromium.launch({
    headless: true,
    ...(process.env.PLAYWRIGHT_CHANNEL
      ? { channel: process.env.PLAYWRIGHT_CHANNEL }
      : process.platform === 'win32'
        ? { channel: 'chrome' }
        : {}),
  })
  const context = await browser.newContext()
  const page = await context.newPage()
  for (const width of [360, 1440]) {
    await page.setViewportSize({ width, height: 1000 })
    for (const route of [
      '/',
      '/kham-pha',
      '/do-vat/11111111-1111-4111-8111-111111111111',
      '/dang-tin',
      '/dang-nhap',
      '/dang-ky',
      '/huong-dan',
      '/quan-tri',
    ]) {
      await page.goto(`http://127.0.0.1:15175${route}`)
      await page.locator('main').waitFor()
      await page.evaluate(() => document.fonts.ready)
      const result = await new AxeBuilder({ page })
        .withTags(['wcag2a', 'wcag2aa', 'wcag21aa', 'wcag22aa'])
        .analyze()
      reports.push({
        route,
        width,
        violations: result.violations.map(({ id, impact, nodes }) => ({
          id,
          impact,
          nodes: nodes.map(({ target, failureSummary }) => ({ target, failureSummary })),
        })),
      })
      console.log(`${result.violations.length ? 'FAIL' : 'PASS'} axe ${width}px ${route}`)
    }
  }
  const destination = path.join(root, '.local/browser-qa')
  mkdirSync(destination, { recursive: true })
  writeFileSync(path.join(destination, 'accessibility.json'), JSON.stringify(reports, null, 2))
  const failures = reports.filter((report) => report.violations.length)
  if (failures.length)
    console.log(
      JSON.stringify(
        failures.map(({ route, width, violations }) => ({
          route,
          width,
          violations: violations.map((v) => ({ id: v.id, targets: v.nodes.map((n) => n.target) })),
        })),
        null,
        2,
      ),
    )
  assert.equal(failures.length, 0, 'Review .local/browser-qa/accessibility.json for failed checks.')
  console.log('16 automated accessibility scans passed. This is not a full WCAG certification.')
} finally {
  if (browser) await browser.close()
  await server.close()
}
