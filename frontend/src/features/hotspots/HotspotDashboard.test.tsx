import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { Analysis } from './api'
import { PublicHotspotsPage } from './HotspotDashboard'

vi.mock('./HotspotMap', () => ({
  HotspotMap: () => <div aria-label="Bản đồ thử nghiệm" />,
}))

const empty: Analysis = {
  period: { start_date: '2026-11-01', end_date: '2026-11-30' },
  previous_period: { start_date: '2026-10-02', end_date: '2026-10-31' },
  is_demo: true,
  truncated: false,
  statistics: {
    total_events: 0,
    total_hotspots: 0,
    high_density_areas: 0,
    noise_events: null,
    top_areas: [],
    categories: [],
    hours: [],
    regions: [],
    timeline: [],
    trend: null,
  },
  clusters: [],
  heatmap: [],
  insights: [],
}

function show() {
  const cache = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={cache}>
      <MemoryRouter>
        <PublicHotspotsPage />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

afterEach(() => vi.unstubAllGlobals())

describe('public hotspot map', () => {
  it('uses an empty state and preserves the demo label', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (path: string) => Response.json(path.includes('categories') ? [] : empty)),
    )
    show()
    expect(await screen.findByText('Chưa có cụm đủ dữ liệu')).toBeVisible()
    expect(screen.getByText('Dữ liệu giả lập')).toBeVisible()
  })

  it('retries an API failure', async () => {
    let requests = 0
    vi.stubGlobal(
      'fetch',
      vi.fn(async (path: string) => {
        if (path.includes('categories')) return Response.json([])
        if (++requests === 1)
          return Response.json({ error: { code: 'HOTSPOT_BUSY' } }, { status: 503 })
        return Response.json(empty)
      }),
    )
    show()
    await userEvent.click(await screen.findByRole('button', { name: 'Thử lại' }))
    expect(await screen.findByText('Chưa có cụm đủ dữ liệu')).toBeVisible()
    expect(requests).toBe(2)
  })

  it('passes the chosen period and shows related public links', async () => {
    const cluster = {
      cluster_id: 'fc7e60190c716ca09ad973c9',
      location_name: 'Thư viện · Hà Nội',
      latitude: 21,
      longitude: 105.8,
      event_count: 5,
      density_level: 'low',
      top_categories: [],
      peak_time: null,
      timeline: [],
      trend: null,
    }
    const requests = vi.fn(async (path: string) => {
      if (path.includes('categories')) return Response.json([])
      if (path.includes(cluster.cluster_id))
        return Response.json({
          ...cluster,
          related_posts: [{ id: 'item-1', title: 'Mất ví ở thư viện', event_day: '2026-11-20' }],
        })
      if (path.includes('period=7'))
        return Response.json({ ...empty, clusters: [cluster], heatmap: [cluster] })
      return Response.json(empty)
    })
    vi.stubGlobal('fetch', requests)
    show()
    await userEvent.selectOptions(
      await screen.findByRole('combobox', { name: 'Khoảng thời gian' }),
      '7',
    )
    await userEvent.click(await screen.findByRole('button', { name: /Thư viện · Hà Nội/ }))
    expect(await screen.findByRole('link', { name: 'Mất ví ở thư viện' })).toHaveAttribute(
      'href',
      '/do-vat/item-1',
    )
    expect(requests.mock.calls.some(([url]) => url.includes('period=7'))).toBe(true)
  })
})
