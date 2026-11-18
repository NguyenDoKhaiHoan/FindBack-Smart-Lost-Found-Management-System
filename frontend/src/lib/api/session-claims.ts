import { ApiError } from './client'

/** Display/session hints only. These decoded claims do not grant authorization. */
export function readSessionClaims(token: string): { actorId: string; expiresAt: number } {
  try {
    const parts = token.split('.')
    if (parts.length !== 3) throw new Error('Invalid token')
    const encoded = parts[1].replace(/-/g, '+').replace(/_/g, '/')
    const payload: unknown = JSON.parse(
      atob(encoded.padEnd(Math.ceil(encoded.length / 4) * 4, '=')),
    )
    if (
      typeof payload !== 'object' ||
      payload === null ||
      !('sub' in payload) ||
      !('exp' in payload)
    )
      throw new Error('Invalid claims')
    if (
      typeof payload.sub !== 'string' ||
      !/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(payload.sub)
    )
      throw new Error('Invalid subject')
    if (
      typeof payload.exp !== 'number' ||
      !Number.isFinite(payload.exp) ||
      payload.exp * 1000 <= Date.now()
    )
      throw new Error('Expired')
    return { actorId: payload.sub, expiresAt: payload.exp * 1000 }
  } catch {
    throw new ApiError(401, 'UNAUTHENTICATED')
  }
}
