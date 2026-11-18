/** Tokens are deliberately confined to memory. Never use browser storage here. */
export interface SessionSnapshot {
  token: string | null
  actorId: string | null
  expiresAt: number | null
  expired: boolean
}

let snapshot: SessionSnapshot = { token: null, actorId: null, expiresAt: null, expired: false }
let refreshToken: string | null = null
const listeners = new Set<() => void>()

export const getSessionSnapshot = () => snapshot
export const subscribeSession = (listener: () => void) => {
  listeners.add(listener)
  return () => {
    listeners.delete(listener)
  }
}

export const getRefreshToken = (token: string) => (snapshot.token === token ? refreshToken : null)

export function setSession(token: string, actorId: string, expiresAt: number, refresh?: string) {
  refreshToken = refresh ?? null
  snapshot = { token, actorId, expiresAt, expired: false }
  listeners.forEach((listener) => listener())
}

export function clearSession(expired = false, expectedToken?: string) {
  // A late response from an old session must never disconnect a new session.
  if (expectedToken !== undefined && expectedToken !== snapshot.token) return
  refreshToken = null
  snapshot = { token: null, actorId: null, expiresAt: null, expired }
  listeners.forEach((listener) => listener())
}
