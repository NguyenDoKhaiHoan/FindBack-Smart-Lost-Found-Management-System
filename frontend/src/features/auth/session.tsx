import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  useSyncExternalStore,
  type ReactNode,
} from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { apiRequest, ApiError } from '../../lib/api/client'
import {
  clearSession,
  getRefreshToken,
  getSessionSnapshot,
  setSession,
  subscribeSession,
} from '../../lib/api/session-store'
import { readSessionClaims } from '../../lib/api/session-claims'
import type { ClaimPage } from '../../lib/api/types'
import { identityApi, type Credentials } from '../../lib/api/system'

interface SessionContextValue {
  token: string | null
  actorId: string | null
  connect: (token: string) => Promise<void>
  signIn: (credentials: Credentials) => Promise<void>
  disconnect: () => void
  isConnecting: boolean
  error: string | null
  expired: boolean
}

const SessionContext = createContext<SessionContextValue | null>(null)

export function SessionProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient()
  const snapshot = useSyncExternalStore(subscribeSession, getSessionSnapshot, getSessionSnapshot)
  const { token, expiresAt, actorId } = snapshot
  const [isConnecting, setIsConnecting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const connection = useRef<AbortController | null>(null)

  useEffect(() => {
    let actor = getSessionSnapshot().actorId
    return subscribeSession(() => {
      const nextActor = getSessionSnapshot().actorId
      if (nextActor === actor) return
      actor = nextActor
      // Remove private evidence and outstanding queries on every identity change.
      void queryClient.cancelQueries()
      queryClient.clear()
    })
  }, [queryClient])

  useEffect(() => {
    if (!token || !expiresAt) return
    const refresh = getRefreshToken(token)
    const controller = new AbortController()
    let timer: ReturnType<typeof setTimeout>
    const expire = () => clearSession(true, token)
    const checkExpiry = async () => {
      if (getSessionSnapshot().token !== token) return
      if (!refresh) return expire()
      try {
        const pair = await identityApi.refresh(refresh, controller.signal)
        const claims = readSessionClaims(pair.access_token)
        if (claims.actorId !== actorId) return expire()
        if (!controller.signal.aborted && getSessionSnapshot().token === token) {
          setSession(pair.access_token, actorId, claims.expiresAt, pair.refresh_token)
        }
      } catch (cause) {
        if (controller.signal.aborted) return
        if (cause instanceof ApiError && cause.status === 401) return expire()
        timer = setTimeout(expire, Math.max(0, expiresAt - Date.now()))
      }
    }
    timer = setTimeout(checkExpiry, Math.max(0, expiresAt - Date.now() - (refresh ? 30_000 : 0)))
    return () => {
      controller.abort()
      clearTimeout(timer)
    }
  }, [token, expiresAt, actorId])

  useEffect(
    () => () => {
      connection.current?.abort()
    },
    [],
  )

  const disconnect = useCallback(() => {
    connection.current?.abort()
    connection.current = null
    setIsConnecting(false)
    setError(null)
    clearSession()
  }, [])

  const connect = useCallback(async (input: string) => {
    connection.current?.abort()
    const controller = new AbortController()
    connection.current = controller
    setIsConnecting(true)
    setError(null)
    // Switching identity immediately removes the prior user's sensitive data.
    clearSession()
    try {
      const token = input.trim()
      const claims = readSessionClaims(token)
      await apiRequest<ClaimPage>('/api/v1/claims/me?page_size=1', {
        token,
        signal: controller.signal,
      })
      if (controller.signal.aborted) return
      // Recheck expiry after network validation; decoding never grants authorization.
      readSessionClaims(token)
      setSession(token, claims.actorId, claims.expiresAt)
    } catch (cause) {
      if (controller.signal.aborted) return
      const message =
        cause instanceof ApiError ? cause.message : 'Không thể kết nối phiên. Vui lòng thử lại.'
      setError(message)
      throw cause
    } finally {
      if (connection.current === controller) {
        connection.current = null
        setIsConnecting(false)
      }
    }
  }, [])

  const signIn = useCallback(async (credentials: Credentials) => {
    connection.current?.abort()
    const controller = new AbortController()
    connection.current = controller
    setIsConnecting(true)
    setError(null)
    clearSession()
    try {
      const pair = await identityApi.login(credentials, controller.signal)
      const claims = readSessionClaims(pair.access_token)
      if (controller.signal.aborted) return
      setSession(pair.access_token, claims.actorId, claims.expiresAt, pair.refresh_token)
    } finally {
      if (connection.current === controller) {
        connection.current = null
        setIsConnecting(false)
      }
    }
  }, [])

  return (
    <SessionContext.Provider
      value={{
        token: snapshot.token,
        actorId: snapshot.actorId,
        expired: snapshot.expired,
        connect,
        signIn,
        disconnect,
        isConnecting,
        error,
      }}
    >
      {children}
    </SessionContext.Provider>
  )
}

// eslint-disable-next-line react-refresh/only-export-components -- The provider and its public hook share one private context.
export function useSession(): SessionContextValue {
  const session = useContext(SessionContext)
  if (!session) throw new Error('useSession must be used inside SessionProvider')
  return session
}
