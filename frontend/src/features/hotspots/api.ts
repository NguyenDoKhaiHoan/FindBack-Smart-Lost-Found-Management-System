import { apiRequest } from '../../lib/api/client'

export type Density = 'low' | 'medium' | 'high' | 'very_high'
export type GroupBy = 'day' | 'week' | 'month'
export type Count = { label: string; count: number }
type Trend = { previous_count: number; change_percent: number }
type Window = { start_date: string; end_date: string }

export interface Point {
  latitude: number
  longitude: number
  event_count: number
  density_level: Density
}

export interface Cluster extends Point {
  cluster_id: string
  location_name: string
  top_categories: Count[]
  peak_time: Count | null
  timeline: Count[]
  trend: Trend | null
}

export interface Analysis {
  period: Window
  previous_period: Window
  is_demo: boolean
  truncated: boolean
  statistics: {
    total_events: number
    total_hotspots: number
    high_density_areas: number
    noise_events: number | null
    top_areas: Count[]
    categories: Count[]
    hours: Count[]
    regions: Count[]
    timeline: Count[]
    trend: Trend | null
  }
  clusters: Cluster[]
  heatmap: Point[]
  insights: string[]
}

export interface ClusterDetail extends Cluster {
  related_posts: { id: string; title: string; event_day: string }[]
}

export interface Filters {
  period: string
  category_id: string
  location_id: string
  zone: string
  start_date: string
  end_date: string
  group_by: GroupBy
}

export interface AlgorithmConfig {
  eps_meters: number
  min_samples: number
  period_days: number
  medium_count: number
  high_count: number
  very_high_count: number
}

export interface HotspotPin {
  hotspot_zone: string
  latitude: number
  longitude: number
}

const prefix = (admin: boolean) => (admin ? '/api/admin/ai/hotspots' : '/api/ai/hotspots')

function query(filters: Filters) {
  const query = new URLSearchParams()
  for (const [name, value] of Object.entries(filters)) {
    if (value) query.set(name, value)
  }
  return `?${query}`
}

export const hotspotApi = {
  analyze: (admin: boolean, filters: Filters, signal: AbortSignal) =>
    apiRequest<Analysis>(prefix(admin) + query(filters), { auth: admin, signal }),
  detail: (admin: boolean, id: string, filters: Filters, signal: AbortSignal) =>
    apiRequest<ClusterDetail>(`${prefix(admin)}/${id}${query(filters)}`, { auth: admin, signal }),
  config: (signal: AbortSignal) =>
    apiRequest<AlgorithmConfig>(`${prefix(true)}/config`, { signal }),
  update: (body: AlgorithmConfig) =>
    apiRequest<AlgorithmConfig>(`${prefix(true)}/config`, { method: 'PATCH', body }),
  recalculate: (filters: Filters) =>
    apiRequest<Analysis>(`${prefix(true)}/recalculate${query(filters)}`, { method: 'POST' }),
  export: (filters: Filters) =>
    apiRequest<Blob>(`${prefix(true)}/export${query(filters)}`, { response: 'blob' }),
  pin: (postId: string, signal: AbortSignal) =>
    apiRequest<HotspotPin | null>(`/api/v1/posts/${encodeURIComponent(postId)}/hotspot-location`, {
      signal,
    }),
}
