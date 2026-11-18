/** Contracts audited against backend/app/modules/claims_returns/schemas/claims.py. */
export type ClaimStatus = 'PENDING' | 'APPROVED' | 'REJECTED' | 'RETURNED'
export type ClaimRelation = 'claimant' | 'reviewer' | 'all'

export interface ClaimQuery {
  relation?: ClaimRelation
  status?: ClaimStatus
  page?: number
  page_size?: number
}

export interface ReturnSummary {
  id: string
  status: 'ARRANGED' | 'HANDED_OVER' | 'CONFIRMED'
  handed_over_at: string | null
  confirmed_at: string | null
}

export interface ClaimSummary {
  id: string
  found_post_id: string
  claimant_id: string
  status: ClaimStatus
  version: number
  created_at: string
  updated_at: string
  decided_by: string | null
  decided_at: string | null
  rejection_reason: string | null
  returned_by: string | null
  returned_at: string | null
  return_summary: ReturnSummary | null
}

export interface ClaimEvidence {
  id: string
  private_content: string
  created_at: string
}

export interface ClaimDetail extends ClaimSummary {
  evidence: ClaimEvidence[]
}

export interface ClaimPage {
  items: ClaimSummary[]
  page: number
  page_size: number
  has_next: boolean
}

export interface CreateClaimRequest {
  found_post_id: string
  evidence_description: string
}

export interface ApproveClaimRequest {
  expected_version: number
}
export interface RejectClaimRequest extends ApproveClaimRequest {
  reason: string
}
export interface CompleteClaimRequest extends ApproveClaimRequest {
  receipt_confirmed: true
}

export interface ErrorDetail {
  field: string
  issue: string
}
