import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { ClaimsPage, ClaimDetailPage, CreateClaimPage } from './ClaimsPages'
import { ApiError, type ClaimDetail } from '../../lib/api'

const state = vi.hoisted(() => ({
  actorId: 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
  list: vi.fn(),
  detail: vi.fn(),
  create: vi.fn(),
  approve: vi.fn(),
  reject: vi.fn(),
  complete: vi.fn(),
}))
vi.mock('../auth/session', () => ({
  useSession: () => ({ actorId: state.actorId, token: 'test-session' }),
}))
vi.mock('../../lib/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../lib/api')>()),
  claimsApi: {
    list: state.list,
    detail: state.detail,
    create: state.create,
    approve: state.approve,
    reject: state.reject,
    complete: state.complete,
  },
}))

const CLAIM_ID = '11111111-1111-4111-8111-111111111111'
const POST_ID = '22222222-2222-4222-8222-222222222222'
const CLAIMANT = 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'
const REVIEWER = 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb'
function claim(overrides: Partial<ClaimDetail> = {}): ClaimDetail {
  return {
    id: CLAIM_ID,
    found_post_id: POST_ID,
    claimant_id: CLAIMANT,
    status: 'PENDING',
    version: 3,
    created_at: '2026-11-17T08:00:00Z',
    updated_at: '2026-11-17T08:00:00Z',
    decided_by: null,
    decided_at: null,
    rejection_reason: null,
    returned_by: null,
    returned_at: null,
    return_summary: null,
    evidence: [
      {
        id: 'evidence-1',
        private_content: 'Private test fixture: a distinct blue stitch inside.',
        created_at: '2026-11-17T08:00:00Z',
      },
    ],
    ...overrides,
  }
}
function setup(path: string) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/yeu-cau" element={<ClaimsPage />} />
          <Route path="/yeu-cau/moi" element={<CreateClaimPage />} />
          <Route path="/yeu-cau/:id" element={<ClaimDetailPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
  return userEvent.setup()
}

beforeEach(() => {
  vi.clearAllMocks()
  state.actorId = CLAIMANT
  state.detail.mockResolvedValue(claim())
  state.list.mockResolvedValue({ items: [], page: 1, page_size: 10, has_next: false })
})

describe('claims workflow UI', () => {
  it('rejects invalid create input before making a request and sends trimmed private evidence', async () => {
    state.create.mockResolvedValue(claim())
    const user = setup('/yeu-cau/moi')
    await user.click(screen.getByRole('button', { name: 'Gửi yêu cầu nhận đồ' }))
    expect(state.create).not.toHaveBeenCalled()
    expect(screen.getByText('Nhập mã tin nhặt được theo định dạng UUID.')).toBeVisible()
    await user.type(screen.getByLabelText(/Mã tin nhặt được/), POST_ID)
    await user.type(
      screen.getByLabelText(/Bằng chứng sở hữu/),
      '  Distinctive blue stitch inside  ',
    )
    await user.click(screen.getByRole('button', { name: 'Gửi yêu cầu nhận đồ' }))
    await waitFor(() =>
      expect(state.create).toHaveBeenCalledWith(
        { found_post_id: POST_ID, evidence_description: 'Distinctive blue stitch inside' },
        expect.anything(),
      ),
    )
    expect(
      await screen.findByRole('heading', { name: `Yêu cầu #${CLAIM_ID.slice(0, 8)}` }),
    ).toBeVisible()
  })

  it('filters list by relationship and state without requesting unsupported search fields', async () => {
    const user = setup('/yeu-cau')
    await screen.findByText('Chưa có yêu cầu nào')
    await user.click(screen.getByRole('button', { name: 'Cần tôi xem xét' }))
    await user.selectOptions(screen.getByLabelText('Trạng thái'), 'APPROVED')
    await waitFor(() =>
      expect(state.list).toHaveBeenLastCalledWith(
        { relation: 'reviewer', status: 'APPROVED', page: 1, page_size: 10 },
        expect.any(AbortSignal),
      ),
    )
  })

  it('never offers approve or reject controls to the claimant', async () => {
    setup(`/yeu-cau/${CLAIM_ID}`)
    await screen.findByRole('heading', { name: 'Bằng chứng sở hữu' })
    expect(screen.queryByRole('button', { name: 'Chấp thuận yêu cầu' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Từ chối yêu cầu' })).not.toBeInTheDocument()
    expect(screen.getByText(/Private test fixture/)).toBeVisible()
  })

  it('requires reviewed-evidence confirmation and sends the displayed version for approve', async () => {
    state.actorId = REVIEWER
    state.approve.mockResolvedValue(claim({ status: 'APPROVED', version: 4 }))
    const user = setup(`/yeu-cau/${CLAIM_ID}`)
    await user.click(await screen.findByRole('button', { name: 'Chấp thuận yêu cầu' }))
    const dialog = screen.getByRole('dialog')
    const approve = within(dialog).getByRole('button', { name: 'Chấp thuận yêu cầu' })
    expect(approve).toBeDisabled()
    await user.click(within(dialog).getByRole('checkbox'))
    await user.click(approve)
    await waitFor(() =>
      expect(state.approve).toHaveBeenCalledWith(CLAIM_ID, { expected_version: 3 }),
    )
  })

  it('requires a nonblank rejection reason', async () => {
    state.actorId = REVIEWER
    state.reject.mockResolvedValue(claim({ status: 'REJECTED', version: 4 }))
    const user = setup(`/yeu-cau/${CLAIM_ID}`)
    await user.click(await screen.findByRole('button', { name: 'Từ chối yêu cầu' }))
    const dialog = screen.getByRole('dialog')
    const reject = within(dialog).getByRole('button', { name: 'Xác nhận từ chối' })
    expect(reject).toBeDisabled()
    await user.type(within(dialog).getByLabelText('Lý do từ chối'), '  Chi tiết chưa khớp  ')
    await user.click(reject)
    await waitFor(() =>
      expect(state.reject).toHaveBeenCalledWith(CLAIM_ID, {
        expected_version: 3,
        reason: 'Chi tiết chưa khớp',
      }),
    )
  })

  it('does not offer complete until a handed-over return exists', async () => {
    state.detail.mockResolvedValue(claim({ status: 'APPROVED' }))
    setup(`/yeu-cau/${CLAIM_ID}`)
    await screen.findByRole('heading', { name: 'Bằng chứng sở hữu' })
    expect(screen.queryByRole('button', { name: 'Tôi đã nhận lại đồ' })).not.toBeInTheDocument()
    expect(screen.getByText('Chờ chủ tin lập phiên trao trả.')).toBeVisible()
  })

  it('requires explicit receipt confirmation and sends literal true', async () => {
    state.detail.mockResolvedValue(
      claim({
        status: 'APPROVED',
        return_summary: {
          id: 'return-1',
          status: 'HANDED_OVER',
          handed_over_at: '2026-11-17T09:00:00Z',
          confirmed_at: null,
        },
      }),
    )
    state.complete.mockResolvedValue(claim({ status: 'RETURNED', version: 4 }))
    const user = setup(`/yeu-cau/${CLAIM_ID}`)
    await user.click(await screen.findByRole('button', { name: 'Tôi đã nhận lại đồ' }))
    const dialog = screen.getByRole('dialog')
    const complete = within(dialog).getByRole('button', { name: 'Xác nhận đã nhận đồ' })
    expect(complete).toBeDisabled()
    await user.click(within(dialog).getByRole('checkbox'))
    await user.click(complete)
    await waitFor(() =>
      expect(state.complete).toHaveBeenCalledWith(CLAIM_ID, {
        expected_version: 3,
        receipt_confirmed: true,
      }),
    )
  })

  it('refetches after a version conflict and requires a fresh decision rather than replaying', async () => {
    state.actorId = REVIEWER
    state.approve.mockRejectedValue(new ApiError(409, 'CLAIM_VERSION_CONFLICT'))
    const user = setup(`/yeu-cau/${CLAIM_ID}`)
    await user.click(await screen.findByRole('button', { name: 'Chấp thuận yêu cầu' }))
    const dialog = screen.getByRole('dialog')
    await user.click(within(dialog).getByRole('checkbox'))
    await user.click(within(dialog).getByRole('button', { name: 'Chấp thuận yêu cầu' }))
    await screen.findByText(/Thông tin đã được tải lại/)
    await waitFor(() => expect(state.detail).toHaveBeenCalledTimes(2))
    expect(state.approve).toHaveBeenCalledTimes(1)
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('hides private detail after a server authorization failure', async () => {
    state.detail.mockRejectedValue(new ApiError(404, 'CLAIM_NOT_FOUND'))
    setup(`/yeu-cau/${CLAIM_ID}`)
    expect(await screen.findByRole('alert')).toHaveTextContent('Không tìm thấy yêu cầu')
    expect(screen.queryByText(/Private test fixture/)).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Chấp thuận yêu cầu' })).not.toBeInTheDocument()
  })
})
