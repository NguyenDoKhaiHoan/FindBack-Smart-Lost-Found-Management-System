import { apiRequest } from './client'
import type {
  ApproveClaimRequest,
  ClaimDetail,
  ClaimPage,
  ClaimQuery,
  ClaimSummary,
  CompleteClaimRequest,
  CreateClaimRequest,
  RejectClaimRequest,
} from './types'

export { ApiError } from './client'
export type * from './types'

const claimsPath = '/api/v1/claims'
const claimPath = (id: string) => `${claimsPath}/${encodeURIComponent(id)}`

export const claimsApi = {
  list(query: ClaimQuery = {}, signal?: AbortSignal) {
    const params = new URLSearchParams()
    if (query.relation) params.set('relation', query.relation)
    if (query.status) params.set('status', query.status)
    if (query.page !== undefined) params.set('page', String(query.page))
    if (query.page_size !== undefined) params.set('page_size', String(query.page_size))
    const suffix = params.size ? `?${params.toString()}` : ''
    return apiRequest<ClaimPage>(`${claimsPath}/me${suffix}`, { signal })
  },
  detail(id: string, signal?: AbortSignal) {
    return apiRequest<ClaimDetail>(claimPath(id), { signal })
  },
  create(body: CreateClaimRequest) {
    return apiRequest<ClaimSummary>(claimsPath, { method: 'POST', body })
  },
  approve(id: string, body: ApproveClaimRequest) {
    return apiRequest<ClaimSummary>(`${claimPath(id)}/approve`, { method: 'PATCH', body })
  },
  reject(id: string, body: RejectClaimRequest) {
    return apiRequest<ClaimSummary>(`${claimPath(id)}/reject`, { method: 'PATCH', body })
  },
  complete(id: string, body: CompleteClaimRequest) {
    return apiRequest<ClaimSummary>(`${claimPath(id)}/complete`, { method: 'PATCH', body })
  },
}
