import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { SessionProvider, useSession } from '../../features/auth/session'
import { clearSession, getSessionSnapshot, setSession } from './session-store'
import { claimsApi } from './index'

const actorId = '8ea5ac28-20b6-4c1d-8da7-fb639db74cd2'
const tokenFor = (expiresInSeconds = 3600) =>
  `header.${btoa(JSON.stringify({ sub: actorId, exp: Math.floor(Date.now() / 1000) + expiresInSeconds }))}.signature`

function SessionControls({ token }: { token: string }) {
  const session = useSession()
  return (
    <>
      <output aria-label="session">
        {session.actorId ?? (session.expired ? 'expired' : 'anonymous')}
      </output>
      <output aria-label="error">{session.error}</output>
      <button
        onClick={() => {
          void session.connect(token).catch(() => undefined)
        }}
      >
        Connect
      </button>
      <button onClick={session.disconnect}>Disconnect</button>
    </>
  )
}

function setup(token: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={client}>
      <SessionProvider>
        <SessionControls token={token} />
      </SessionProvider>
    </QueryClientProvider>,
  )
  return client
}

afterEach(() => {
  cleanup()
  clearSession()
  vi.unstubAllGlobals()
  vi.useRealTimers()
})

describe('session provider privacy boundary', () => {
  it('waits for server validation before exposing an authenticated identity', async () => {
    let complete: (value: Response) => void = () => undefined
    vi.stubGlobal(
      'fetch',
      vi.fn().mockImplementation(
        () =>
          new Promise<Response>((resolve) => {
            complete = resolve
          }),
      ),
    )
    setup(tokenFor())
    fireEvent.click(screen.getByRole('button', { name: 'Connect' }))
    expect(screen.getByLabelText('session').textContent).toBe('anonymous')
    expect(getSessionSnapshot().token).toBeNull()
    await act(async () => {
      complete(Response.json({ items: [], page: 1, page_size: 1, has_next: false }))
    })
    expect(screen.getByLabelText('session').textContent).toBe(actorId)
  })

  it('keeps a rejected identity anonymous and presents the safe server error', async () => {
    vi.stubGlobal(
      'fetch',
      vi
        .fn()
        .mockResolvedValue(
          Response.json(
            { error: { code: 'UNAUTHENTICATED', request_id: 'test-request', details: [] } },
            { status: 401 },
          ),
        ),
    )
    setup(tokenFor())
    fireEvent.click(screen.getByRole('button', { name: 'Connect' }))
    await waitFor(() => expect(screen.getByLabelText('error').textContent).toContain('hết hạn'))
    expect(screen.getByLabelText('session').textContent).toBe('anonymous')
    expect(getSessionSnapshot().token).toBeNull()
  })

  it('removes private query data on disconnect', () => {
    const client = setup(tokenFor())
    act(() => setSession('active-token', actorId, Date.now() + 60_000))
    client.setQueryData(['claims', actorId, 'private-detail'], { evidence: 'private test fixture' })
    fireEvent.click(screen.getByRole('button', { name: 'Disconnect' }))
    expect(client.getQueryCache().getAll()).toHaveLength(0)
    expect(screen.getByLabelText('session').textContent).toBe('anonymous')
  })

  it('removes private query data when a request receives 401', async () => {
    const client = setup(tokenFor())
    act(() => setSession('active-token', actorId, Date.now() + 60_000))
    client.setQueryData(['claims', actorId, 'private-detail'], { evidence: 'private test fixture' })
    vi.stubGlobal(
      'fetch',
      vi
        .fn()
        .mockResolvedValue(Response.json({ error: { code: 'UNAUTHENTICATED' } }, { status: 401 })),
    )
    await act(async () => {
      await claimsApi.list().catch(() => undefined)
    })
    expect(client.getQueryCache().getAll()).toHaveLength(0)
    expect(screen.getByLabelText('session').textContent).toBe('expired')
  })

  it('expires an idle session and erases cached evidence', () => {
    vi.useFakeTimers()
    const client = setup(tokenFor())
    act(() => setSession('active-token', actorId, Date.now() + 2_000))
    client.setQueryData(['claims', actorId, 'private-detail'], { evidence: 'private test fixture' })
    act(() => vi.advanceTimersByTime(2_001))
    expect(client.getQueryCache().getAll()).toHaveLength(0)
    expect(screen.getByLabelText('session').textContent).toBe('expired')
  })
})
