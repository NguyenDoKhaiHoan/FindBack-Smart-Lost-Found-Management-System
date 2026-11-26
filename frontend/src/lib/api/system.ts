import { apiRequest } from './client'
import type { ClaimDetail, ReturnSummary } from './types'

const api = '/api/v1'
const idPath = (id: string) => encodeURIComponent(id)
function query(values: Record<string, string | number | boolean | undefined>) {
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(values)) {
    if (value !== undefined && value !== '') params.set(key, String(value))
  }
  return params.size ? `?${params}` : ''
}

export interface Credentials {
  email: string
  password: string
}
export interface Tokens {
  access_token: string
  refresh_token: string
  token_type: 'bearer'
}
export interface PublicUser {
  id: string
  full_name: string | null
  avatar_url: string | null
}
export interface User extends PublicUser {
  email: string | null
  phone: string | null
  role: 'USER' | 'ADMIN'
}
const authTimeoutMs = 12_000

export const identityApi = {
  register: (body: Credentials & { full_name: string }) =>
    apiRequest<User>(`${api}/auth/register`, {
      method: 'POST',
      body,
      auth: false,
      timeoutMs: authTimeoutMs,
    }),
  login: (body: Credentials, signal?: AbortSignal) =>
    apiRequest<Tokens>(`${api}/auth/login`, {
      method: 'POST',
      body,
      auth: false,
      signal,
      timeoutMs: authTimeoutMs,
    }),
  refresh: (refresh_token: string, signal: AbortSignal) =>
    apiRequest<Tokens>(`${api}/auth/refresh`, {
      method: 'POST',
      body: { refresh_token },
      auth: false,
      signal,
    }),
  me: (signal?: AbortSignal, token?: string) =>
    apiRequest<User>(`${api}/users/me`, { signal, token }),
  update: (body: { full_name: string; phone: string | null; avatar_url: string | null }) =>
    apiRequest<User>(`${api}/users/me`, { method: 'PATCH', body }),
  publicProfile: (id: string, signal?: AbortSignal) =>
    apiRequest<PublicUser>(`${api}/users/${idPath(id)}`, { auth: false, signal }),
}

export type PostType = 'LOST' | 'FOUND'
export type PostStatus = 'OPEN' | 'CLOSED' | 'HIDDEN'
export interface Category {
  id: string
  name: string
}
export interface PostListItem {
  id: string
  user_id: string
  type: PostType
  title: string | null
  location: string | null
  category_id: string | null
  event_time: string | null
  status: PostStatus
  created_at: string
}
export interface Post extends PostListItem {
  item_name?: string | null
  description: string | null
  location_code: string | null
  color_code: string | null
  brand: string | null
  material: string | null
  images: { id: string; file_path: string }[]
}
export interface PostInput {
  category_id: string
  item_name?: string | null
  title: string
  description: string
  location: string
  location_code: string
  event_time: string
  color_code: string | null
  brand: string | null
  material: string | null
}
export interface Page<T> {
  items: T[]
  page: number
  total: number
  total_pages: number
}
interface Pagination {
  page: number
  total: number
  total_pages: number
}
interface NestedPage<T> {
  items: T[]
  pagination: Pagination
}
export interface SearchPost {
  id: string
  type: PostType
  title: string
  description: string
  category: Category
  location: { code: string; name: string }
  event_time: string
  status: 'OPEN' | 'CLOSED'
}
export interface Match {
  id: string
  candidate: SearchPost
  score: number
  explanation: string
  score_details: Record<string, { points: number; max_points: number }>
}
export const postsApi = {
  categories: (signal?: AbortSignal) =>
    apiRequest<Category[]>(`${api}/categories`, { auth: false, signal }),
  latest: (signal?: AbortSignal) =>
    apiRequest<Page<PostListItem>>(`${api}/posts?page_size=6`, { auth: false, signal }),
  mine: (page: number, signal?: AbortSignal) =>
    apiRequest<Page<PostListItem>>(`${api}/users/me/posts${query({ page, page_size: 20 })}`, {
      signal,
    }),
  detail: (id: string, signal?: AbortSignal) =>
    apiRequest<Post>(`${api}/posts/${idPath(id)}`, { auth: false, signal }),
  create: (body: PostInput & { type: PostType }) =>
    apiRequest<Post>(`${api}/posts`, { method: 'POST', body }),
  update: (id: string, body: PostInput) =>
    apiRequest<Post>(`${api}/posts/${idPath(id)}`, { method: 'PATCH', body }),
  remove: (id: string) => apiRequest<void>(`${api}/posts/${idPath(id)}`, { method: 'DELETE' }),
  upload: (id: string, file: File) => {
    const body = new FormData()
    body.set('file', file)
    return apiRequest<{ image: Post['images'][number] }>(`${api}/posts/${idPath(id)}/images`, {
      method: 'POST',
      body,
    })
  },
  search: (params: Record<string, string | number | undefined>, signal?: AbortSignal) =>
    apiRequest<NestedPage<SearchPost>>(`${api}/search${query(params)}`, { auth: false, signal }),
  matches: (post_id: string, page: number, signal?: AbortSignal) =>
    apiRequest<NestedPage<Match>>(`${api}/matches${query({ post_id, page })}`, {
      auth: false,
      signal,
    }),
  recalculate: (post_id: string) =>
    apiRequest<NestedPage<Match>>(`${api}/matches/recalculate`, {
      method: 'POST',
      body: { post_id },
    }),
  match: (id: string, post_id: string, signal?: AbortSignal) =>
    apiRequest<Match>(`${api}/matches/${idPath(id)}${query({ post_id })}`, { auth: false, signal }),
}

export interface ReturnInfo extends ReturnSummary {
  claim_id: string
  arranged_at: string | null
  scheduled_at: string | null
  meeting_note: string | null
}
export const returnApi = {
  detail: (id: string, signal?: AbortSignal) =>
    apiRequest<ReturnInfo>(`${api}/returns/${idPath(id)}`, { signal }),
  arrange: (body: {
    claim_id: string
    expected_version: number
    scheduled_at: string | null
    meeting_note: string | null
  }) => apiRequest<ReturnInfo>(`${api}/returns`, { method: 'POST', body }),
  handover: (id: string, expected_version: number) =>
    apiRequest<ReturnInfo>(`${api}/returns/${idPath(id)}/handover`, {
      method: 'PATCH',
      body: { expected_version },
    }),
  evidence: (
    id: string,
    body: {
      expected_version: number
      evidence_description: string
      image_base64?: string
      image_content_type?: string
    },
  ) => apiRequest<ClaimDetail>(`${api}/claims/${idPath(id)}/evidence`, { method: 'POST', body }),
  file: (id: string, evidence: string) =>
    apiRequest<Blob>(`${api}/claims/${idPath(id)}/evidence/${idPath(evidence)}/file`, {
      response: 'blob',
    }),
}

export interface Notification {
  id: string
  title: string
  message: string
  resource_type: string | null
  resource_id: string | null
  is_read: boolean
  created_at: string
}
export const notificationsApi = {
  list: (page: number, is_read?: boolean, signal?: AbortSignal) =>
    apiRequest<NestedPage<Notification>>(`${api}/notifications${query({ page, is_read })}`, {
      signal,
    }),
  read: (id: string) => apiRequest(`${api}/notifications/${idPath(id)}/read`, { method: 'PATCH' }),
}

export type ReportStatus = 'PENDING' | 'REVIEWING' | 'RESOLVED' | 'DISMISSED'
export interface Report {
  id: string
  post_id: string
  reason: string
  status: ReportStatus
  resolution_note: string | null
}
export interface ModerationPost extends PostListItem {
  description: string | null
  moderation_reason: string | null
}
export interface Statistics {
  users: number
  posts: number
  public_posts: number
  hidden_posts: number
  claims: number
  completed_returns: number
  pending_reports: number
  resolved_reports: number
}
export const moderationApi = {
  report: (post_id: string, reason: string) =>
    apiRequest(`${api}/reports`, { method: 'POST', body: { post_id, reason } }),
  stats: (signal?: AbortSignal) => apiRequest<Statistics>(`${api}/admin/statistics`, { signal }),
  posts: (page: number, status: string, signal?: AbortSignal) =>
    apiRequest<NestedPage<ModerationPost>>(`${api}/admin/posts${query({ page, status })}`, {
      signal,
    }),
  hide: (id: string, reason: string) =>
    apiRequest(`${api}/admin/posts/${idPath(id)}/moderation`, {
      method: 'PATCH',
      body: { action: 'HIDE', reason },
    }),
  reports: (page: number, status: string, signal?: AbortSignal) =>
    apiRequest<Page<Report>>(`${api}/admin/reports${query({ page, status })}`, { signal }),
  review: (id: string, status: Exclude<ReportStatus, 'PENDING'>, resolution_note: string) =>
    apiRequest(`${api}/admin/reports/${idPath(id)}`, {
      method: 'PATCH',
      body: { status, resolution_note },
    }),
}
