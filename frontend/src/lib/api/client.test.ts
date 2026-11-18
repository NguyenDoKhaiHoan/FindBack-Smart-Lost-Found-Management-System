import { afterEach, describe, expect, it, vi } from 'vitest'
import { claimsApi, ApiError } from './index'
import { clearSession, getSessionSnapshot, setSession } from './session-store'
import { apiRequest } from './client'

const actorId = '8ea5ac28-20b6-4c1d-8da7-fb639db74cd2'
const claimId = '89c06c70-275c-4bc1-9e28-928db7cd58c2'
const errorResponse = (status: number, code: string) =>
  new Response(
    JSON.stringify({
      error: {
        code,
        message: 'Private upstream content must not appear in UI',
        request_id: 'request-123',
        details: [],
      },
    }),
    { status, headers: { 'Content-Type': 'application/json' } },
  )

afterEach(() => {
  clearSession()
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('claims contract boundary', () => {
  it('sends the exact private, paginated list contract without evidence or a GET body', async () => {
    const page = { items: [], page: 2, page_size: 10, has_next: false }
    const fetchMock = vi.fn().mockResolvedValue(Response.json(page))
    vi.stubGlobal('fetch', fetchMock)
    setSession('memory-token', actorId, Date.now() + 60_000)

    await expect(
      claimsApi.list({ relation: 'reviewer', status: 'PENDING', page: 2, page_size: 10 }),
    ).resolves.toEqual(page)
    const [url, options] = fetchMock.mock.calls[0]
    expect(url).toBe('/api/v1/claims/me?relation=reviewer&status=PENDING&page=2&page_size=10')
    expect(options).toMatchObject({
      method: 'GET',
      cache: 'no-store',
      credentials: 'omit',
      redirect: 'error',
      headers: { Authorization: 'Bearer memory-token' },
    })
    expect(options.body).toBeUndefined()
  })

  it('preserves the version and explicit receipt confirmation required by completion', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(Response.json({ id: claimId, status: 'RETURNED', version: 3 }))
    vi.stubGlobal('fetch', fetchMock)
    await claimsApi.complete(claimId, { expected_version: 2, receipt_confirmed: true })
    const [url, options] = fetchMock.mock.calls[0]
    expect(url).toBe(`/api/v1/claims/${claimId}/complete`)
    expect(options.method).toBe('PATCH')
    expect(JSON.parse(options.body)).toEqual({ expected_version: 2, receipt_confirmed: true })
  })

  it('surfaces a stale-version conflict without retrying or leaking the upstream message', async () => {
    const fetchMock = vi.fn().mockResolvedValue(errorResponse(409, 'CLAIM_VERSION_CONFLICT'))
    vi.stubGlobal('fetch', fetchMock)
    const error = await claimsApi
      .approve(claimId, { expected_version: 1 })
      .catch((value: unknown) => value)
    expect(error).toBeInstanceOf(ApiError)
    expect(error).toMatchObject({
      status: 409,
      code: 'CLAIM_VERSION_CONFLICT',
      requestId: 'request-123',
    })
    expect((error as ApiError).message).toContain('tải lại')
    expect((error as ApiError).message).not.toContain('Private upstream')
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  it('clears the active in-memory session when the server rejects its token', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(errorResponse(401, 'UNAUTHENTICATED')))
    setSession('expired-token', actorId, Date.now() + 60_000)
    await expect(claimsApi.list()).rejects.toMatchObject({ status: 401 })
    expect(getSessionSnapshot()).toMatchObject({ token: null, actorId: null, expired: true })
  })

  it('does not clear a newer session after a delayed unauthorized response', async () => {
    let finishRequest: (response: Response) => void = () => undefined
    vi.stubGlobal(
      'fetch',
      vi.fn().mockImplementation(
        () =>
          new Promise<Response>((resolve) => {
            finishRequest = resolve
          }),
      ),
    )
    setSession('old-token', actorId, Date.now() + 60_000)
    const pending = claimsApi.list()
    setSession('new-token', actorId, Date.now() + 60_000)
    finishRequest(errorResponse(401, 'UNAUTHENTICATED'))
    await expect(pending).rejects.toBeInstanceOf(ApiError)
    expect(getSessionSnapshot().token).toBe('new-token')
  })

  it('does not activate an explicitly supplied token before server validation', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(errorResponse(401, 'UNAUTHENTICATED')))
    await expect(apiRequest('/api/v1/claims/me', { token: 'unverified' })).rejects.toMatchObject({
      status: 401,
    })
    expect(getSessionSnapshot().token).toBeNull()
  })

  it('keeps account restrictions distinct from session expiry', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(errorResponse(403, 'ACCOUNT_FORBIDDEN')))
    setSession('restricted-token', actorId, Date.now() + 60_000)
    await expect(claimsApi.list()).rejects.toMatchObject({ status: 403, code: 'ACCOUNT_FORBIDDEN' })
    expect(getSessionSnapshot().expired).toBe(false)
  })

  it('converts a proxy HTML error to a safe API error', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(new Response('<html>upstream unavailable</html>', { status: 502 })),
    )
    await expect(claimsApi.list()).rejects.toMatchObject({ status: 502, code: 'HTTP_ERROR' })
  })

  it('reports transport failure and preserves cancellation', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))
    await expect(claimsApi.list()).rejects.toMatchObject({ status: 0, code: 'NETWORK_ERROR' })
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new DOMException('Aborted', 'AbortError')))
    await expect(claimsApi.list()).rejects.toMatchObject({ name: 'AbortError' })
  })
})
