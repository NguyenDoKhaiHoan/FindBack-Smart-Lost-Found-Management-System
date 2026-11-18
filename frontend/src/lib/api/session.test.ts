import { afterEach, describe, expect, it, vi } from 'vitest'
import { clearSession, getSessionSnapshot, setSession, subscribeSession } from './session-store'
import { readSessionClaims } from './session-claims'

const actorId = '8ea5ac28-20b6-4c1d-8da7-fb639db74cd2'
const tokenFor = (payload: unknown) =>
  `header.${btoa(JSON.stringify(payload)).replace(/=/g, '').replace(/\+/g, '-').replace(/\//g, '_')}.signature`

afterEach(() => {
  clearSession()
  vi.restoreAllMocks()
})

describe('memory-only session lifecycle', () => {
  it('reads subject and expiry as hints without accepting role claims', () => {
    const expires = Math.floor(Date.now() / 1000) + 3600
    expect(readSessionClaims(tokenFor({ sub: actorId, exp: expires, role: 'ADMIN' }))).toEqual({
      actorId,
      expiresAt: expires * 1000,
    })
    expect(getSessionSnapshot().token).toBeNull()
  })

  it.each([
    'not-a-jwt',
    tokenFor({ sub: actorId, exp: 1 }),
    tokenFor({ sub: 'not-a-uuid', exp: 9999999999 }),
    tokenFor({ sub: actorId, exp: '9999999999' }),
    tokenFor({ exp: 9999999999 }),
  ])('rejects malformed or expired session input', (token) => {
    expect(() => readSessionClaims(token)).toThrow('Phiên đăng nhập không hợp lệ')
  })

  it('notifies subscribers when private session data must be cleared', () => {
    const listener = vi.fn()
    const unsubscribe = subscribeSession(listener)
    setSession('memory-only', actorId, Date.now() + 60_000)
    clearSession()
    expect(listener).toHaveBeenCalledTimes(2)
    expect(getSessionSnapshot()).toEqual({
      token: null,
      actorId: null,
      expiresAt: null,
      expired: false,
    })
    unsubscribe()
  })
})
