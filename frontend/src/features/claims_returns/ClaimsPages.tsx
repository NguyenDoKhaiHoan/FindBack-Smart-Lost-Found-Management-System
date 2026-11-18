import { useState, type FormEvent } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import * as Dialog from '@radix-ui/react-dialog'
import {
  ArrowLeft,
  ArrowRight,
  Check,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  CircleCheck,
  ClipboardCheck,
  Clock3,
  FileCheck2,
  FileText,
  Handshake,
  Inbox,
  LoaderCircle,
  LockKeyhole,
  Plus,
  RefreshCw,
  ShieldCheck,
  X,
  XCircle,
} from 'lucide-react'
import {
  ApiError,
  claimsApi,
  type ClaimDetail,
  type ClaimRelation,
  type ClaimStatus,
  type ClaimSummary,
} from '../../lib/api'
import { useSession } from '../auth/session'
import { ClaimEvidenceForm, EvidenceFile, ReturnActions } from './ClaimWorkflow'
import './claims.css'

const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i
const dateFormatter = new Intl.DateTimeFormat('vi-VN', { dateStyle: 'medium', timeStyle: 'short' })
const shortDateFormatter = new Intl.DateTimeFormat('vi-VN', { dateStyle: 'medium' })
const statusLabels: Record<ClaimStatus, string> = {
  PENDING: 'Chờ xác minh',
  APPROVED: 'Đã chấp thuận',
  REJECTED: 'Đã từ chối',
  RETURNED: 'Đã nhận lại đồ',
}
const returnLabels = {
  ARRANGED: 'Đã sắp xếp trao trả',
  HANDED_OVER: 'Đã bàn giao',
  CONFIRMED: 'Đã xác nhận nhận đồ',
}

function formatDate(value: string, short = false) {
  const date = new Date(value)
  return Number.isNaN(date.getTime())
    ? 'Chưa có thời gian'
    : (short ? shortDateFormatter : dateFormatter).format(date)
}

function errorMessage(error: unknown) {
  return error instanceof ApiError ? error.message : 'Không thể kết nối lúc này. Vui lòng thử lại.'
}

export function ClaimStatusBadge({ status }: { status: ClaimStatus }) {
  const Icon =
    status === 'RETURNED'
      ? CheckCircle2
      : status === 'REJECTED'
        ? XCircle
        : status === 'APPROVED'
          ? ShieldCheck
          : Clock3
  return (
    <span className={`claim-status claim-status-${status.toLowerCase()}`}>
      <Icon size={13} aria-hidden="true" />
      {statusLabels[status]}
    </span>
  )
}

function ClaimLoading() {
  return (
    <div className="claims-loading" role="status" aria-label="Đang tải yêu cầu">
      <span className="sr-only">Đang tải yêu cầu…</span>
      {[1, 2, 3].map((key) => (
        <div className="skeleton" key={key} />
      ))}
    </div>
  )
}

function ClaimError({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  return (
    <div className="claims-error" role="alert">
      <p>{errorMessage(error)}</p>
      {error instanceof ApiError && error.requestId && (
        <p className="claim-code">Mã hỗ trợ: {error.requestId}</p>
      )}
      {onRetry && (
        <button type="button" className="button button-secondary" onClick={onRetry}>
          <RefreshCw size={15} aria-hidden="true" />
          Thử lại
        </button>
      )}
    </div>
  )
}

export function ClaimsPage() {
  const { actorId, token } = useSession()
  const [relation, setRelation] = useState<ClaimRelation>('claimant')
  const [status, setStatus] = useState<ClaimStatus | ''>('')
  const [page, setPage] = useState(1)
  const query = useQuery({
    queryKey: ['claims', actorId, 'list', relation, status, page],
    queryFn: ({ signal }) =>
      claimsApi.list({ relation, ...(status ? { status } : {}), page, page_size: 10 }, signal),
    enabled: Boolean(token),
  })

  function changeRelation(next: ClaimRelation) {
    setRelation(next)
    setPage(1)
  }

  return (
    <div className="page-container claims-page">
      <header className="claims-header">
        <div>
          <span className="eyebrow">CÙNG ĐƯA ĐỒ VẬT TRỞ VỀ</span>
          <h1>Yêu cầu nhận đồ</h1>
          <p>
            Theo dõi việc xác minh và trao trả. Mỗi yêu cầu là một bước gần hơn với món đồ của bạn.
          </p>
        </div>
        <Link className="button button-primary" to="/yeu-cau/moi">
          <Plus size={18} aria-hidden="true" />
          Tạo yêu cầu
        </Link>
      </header>
      <section className="panel" aria-label="Danh sách yêu cầu">
        <div className="claims-toolbar">
          <div className="claim-tabs" role="group" aria-label="Mối liên hệ với yêu cầu">
            {(
              [
                ['claimant', 'Tôi đã gửi'],
                ['reviewer', 'Cần tôi xem xét'],
                ['all', 'Tất cả liên quan'],
              ] as const
            ).map(([value, label]) => (
              <button
                type="button"
                aria-pressed={relation === value}
                key={value}
                onClick={() => changeRelation(value)}
              >
                {label}
              </button>
            ))}
          </div>
          <label className="claim-filter">
            Trạng thái
            <select
              value={status}
              onChange={(event) => {
                setStatus(event.target.value as ClaimStatus | '')
                setPage(1)
              }}
            >
              <option value="">Tất cả trạng thái</option>
              {Object.entries(statusLabels).map(([value, label]) => (
                <option value={value} key={value}>
                  {label}
                </option>
              ))}
            </select>
          </label>
        </div>
        {query.isPending && <ClaimLoading />}
        {query.isError && (
          <div className="claim-section">
            <ClaimError error={query.error} onRetry={() => void query.refetch()} />
          </div>
        )}
        {query.isSuccess && query.data.items.length === 0 && (
          <div className="claims-empty">
            <Inbox aria-hidden="true" />
            <h2>{status ? 'Chưa có yêu cầu phù hợp' : 'Chưa có yêu cầu nào'}</h2>
            <p>
              {relation === 'reviewer'
                ? 'Yêu cầu nhận đồ trên tin của bạn sẽ xuất hiện tại đây để bạn xem xét.'
                : 'Khi tìm thấy món đồ có thể thuộc về mình, hãy gửi bằng chứng để người giữ đồ xác minh.'}
            </p>
            {relation !== 'reviewer' && (
              <Link className="button button-secondary" to="/yeu-cau/moi">
                Gửi yêu cầu nhận đồ
                <ArrowRight size={16} aria-hidden="true" />
              </Link>
            )}
          </div>
        )}
        {query.isSuccess && query.data.items.length > 0 && (
          <table className="claims-table">
            <caption className="sr-only">Yêu cầu nhận đồ có liên quan đến bạn</caption>
            <thead>
              <tr>
                <th scope="col">Yêu cầu</th>
                <th scope="col">Mối liên hệ</th>
                <th scope="col">Trạng thái</th>
                <th scope="col">Ngày gửi</th>
                <th scope="col">
                  <span className="sr-only">Mở chi tiết</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {query.data.items.map((claim) => (
                <tr key={claim.id}>
                  <td>
                    <Link className="claim-link" to={`/yeu-cau/${claim.id}`}>
                      <span className="claim-item-icon">
                        <FileCheck2 size={20} aria-hidden="true" />
                      </span>
                      <span>
                        Yêu cầu #{claim.id.slice(0, 8)}
                        <span className="claim-code">
                          Tin nhặt được · {claim.found_post_id.slice(0, 8)}
                        </span>
                      </span>
                    </Link>
                  </td>
                  <td>{claim.claimant_id === actorId ? 'Tôi đã gửi' : 'Trên tin của tôi'}</td>
                  <td>
                    <ClaimStatusBadge status={claim.status} />
                  </td>
                  <td>
                    <time dateTime={claim.created_at}>{formatDate(claim.created_at, true)}</time>
                  </td>
                  <td>
                    <Link
                      to={`/yeu-cau/${claim.id}`}
                      aria-label={`Xem yêu cầu ${claim.id.slice(0, 8)}`}
                    >
                      <ArrowRight size={18} aria-hidden="true" />
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {query.isSuccess && (
          <nav className="claims-pagination" aria-label="Phân trang yêu cầu">
            <span>Trang {query.data.page}</span>
            <div>
              <button
                className="button button-secondary"
                type="button"
                disabled={page === 1 || query.isFetching}
                onClick={() => setPage((value) => Math.max(1, value - 1))}
              >
                <ChevronLeft size={16} aria-hidden="true" />
                Trước
              </button>
              <button
                className="button button-secondary"
                type="button"
                disabled={!query.data.has_next || query.isFetching}
                onClick={() => setPage((value) => value + 1)}
              >
                Sau
                <ChevronRight size={16} aria-hidden="true" />
              </button>
            </div>
          </nav>
        )}
      </section>
      <div className="claim-notice claim-private" style={{ marginTop: 24 }}>
        <LockKeyhole size={19} aria-hidden="true" />
        <p>
          Bằng chứng sở hữu chỉ được hiển thị cho người gửi yêu cầu và chủ tin liên quan. Không chia
          sẻ đặc điểm bí mật ở nơi công khai.
        </p>
      </div>
    </div>
  )
}

export function CreateClaimPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [params] = useSearchParams()
  const [postId, setPostId] = useState(() => params.get('tin') ?? '')
  const [evidence, setEvidence] = useState('')
  const [errors, setErrors] = useState<{ postId?: string; evidence?: string }>({})
  const mutation = useMutation({
    mutationFn: claimsApi.create,
    onSuccess: async (claim) => {
      setEvidence('')
      await queryClient.invalidateQueries({ queryKey: ['claims'] })
      navigate(`/yeu-cau/${claim.id}`, { replace: true, state: { claimCreated: true } })
    },
  })

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const next: typeof errors = {}
    if (!UUID_PATTERN.test(postId.trim()))
      next.postId = 'Nhập mã tin nhặt được theo định dạng UUID.'
    const content = evidence.trim()
    if (content.length < 10 || content.length > 5000)
      next.evidence =
        'Bằng chứng cần có từ 10 đến 5.000 ký tự, không tính khoảng trắng ở đầu và cuối.'
    setErrors(next)
    if (Object.keys(next).length === 0)
      mutation.mutate({ found_post_id: postId.trim(), evidence_description: content })
  }

  return (
    <div className="page-container claims-page">
      <Link className="claim-back" to="/yeu-cau">
        <ArrowLeft size={16} aria-hidden="true" />
        Quay lại yêu cầu của tôi
      </Link>
      <header className="claims-header">
        <div>
          <span className="eyebrow">XÁC MINH QUYỀN SỞ HỮU</span>
          <h1>Đây có thể là đồ của bạn?</h1>
          <p>
            Gửi những chi tiết chỉ bạn biết. Người đang giữ đồ sẽ xem xét bằng chứng trước khi trao
            trả.
          </p>
        </div>
      </header>
      <div className="claim-form-layout">
        <form
          className="panel claim-form-panel"
          onSubmit={submit}
          noValidate
          aria-busy={mutation.isPending}
        >
          <h2>Thông tin yêu cầu</h2>
          {mutation.isError && <ClaimError error={mutation.error} />}
          <div className="claim-field">
            <label htmlFor="claim-post-id">
              Mã tin nhặt được <span aria-hidden="true">*</span>
            </label>
            <input
              id="claim-post-id"
              name="found_post_id"
              value={postId}
              onChange={(event) => setPostId(event.target.value)}
              placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
              autoComplete="off"
              spellCheck={false}
              required
              disabled={mutation.isPending}
              aria-invalid={Boolean(errors.postId)}
              aria-describedby={`claim-post-hint${errors.postId ? ' claim-post-error' : ''}`}
            />
            <span className="claim-field-hint" id="claim-post-hint">
              Dùng mã của một tin nhặt được đang tiếp nhận yêu cầu.{' '}
              <Link to="/kham-pha?loai=found">Tìm tin nhặt được</Link>.
            </span>
            {errors.postId && (
              <span role="alert" id="claim-post-error" className="claim-field-error">
                {errors.postId}
              </span>
            )}
          </div>
          <div className="claim-field">
            <label htmlFor="claim-evidence">
              Bằng chứng sở hữu <span aria-hidden="true">*</span>
            </label>
            <textarea
              id="claim-evidence"
              name="evidence_description"
              value={evidence}
              onChange={(event) => setEvidence(event.target.value)}
              placeholder="Mô tả đặc điểm riêng, vật bên trong, dấu hiệu nhận biết hoặc hoàn cảnh thất lạc…"
              autoComplete="off"
              maxLength={5000}
              required
              disabled={mutation.isPending}
              aria-invalid={Boolean(errors.evidence)}
              aria-describedby={`claim-evidence-hint${errors.evidence ? ' claim-evidence-error' : ''}`}
            />
            <div className="claim-field-count">
              {evidence.length.toLocaleString('vi-VN')} / 5.000 ký tự
            </div>
            <span className="claim-field-hint" id="claim-evidence-hint">
              Chỉ người có liên quan đến yêu cầu được đọc nội dung này. Hiện hỗ trợ bằng chứng văn
              bản. Bạn có thể bổ sung ảnh riêng tư sau khi gửi yêu cầu.
            </span>
            {errors.evidence && (
              <span role="alert" id="claim-evidence-error" className="claim-field-error">
                {errors.evidence}
              </span>
            )}
          </div>
          <div className="claim-notice claim-private">
            <ShieldCheck size={19} aria-hidden="true" />
            <p>
              Không gửi mật khẩu, mã OTP hoặc thông tin thanh toán. Hãy cung cấp đủ thông tin để đối
              chiếu mà vẫn bảo vệ dữ liệu của bạn.
            </p>
          </div>
          <div className="claim-form-footer" style={{ marginTop: 24 }}>
            <Link
              className="button button-secondary"
              to="/yeu-cau"
              onClick={(event) => {
                if (mutation.isPending) event.preventDefault()
              }}
              aria-disabled={mutation.isPending}
            >
              Quay lại
            </Link>
            <button className="button button-primary" type="submit" disabled={mutation.isPending}>
              {mutation.isPending ? (
                <LoaderCircle size={17} className="claim-spin" aria-hidden="true" />
              ) : (
                <ArrowRight size={17} aria-hidden="true" />
              )}
              {mutation.isPending ? 'Đang gửi yêu cầu…' : 'Gửi yêu cầu nhận đồ'}
            </button>
          </div>
        </form>
        <aside className="panel claim-help">
          <ShieldCheck size={28} aria-hidden="true" />
          <h2>Một yêu cầu rõ ràng giúp ích gì?</h2>
          <ol>
            <li>Mô tả chi tiết đặc biệt chưa xuất hiện trong tin đăng.</li>
            <li>Cho biết thời gian và nơi bạn có thể đã làm thất lạc đồ.</li>
            <li>
              Chờ người giữ đồ đối chiếu. Yêu cầu được chấp thuận mới có thể tiến hành trao trả.
            </li>
          </ol>
          <div className="claim-notice">
            <p>
              Chỉ gửi yêu cầu khi bạn có căn cứ món đồ thuộc về mình. Không thể gửi yêu cầu nhận đồ
              trên tin của chính bạn.
            </p>
          </div>
        </aside>
      </div>
    </div>
  )
}

type Decision = 'approve' | 'reject' | 'complete'
const decisions = {
  approve: {
    title: 'Chấp thuận yêu cầu?',
    description:
      'Hãy đối chiếu bằng chứng với món đồ bạn đang giữ. Chấp thuận xác nhận người gửi đủ căn cứ sở hữu; bước bàn giao sẽ được thực hiện riêng.',
    button: 'Chấp thuận yêu cầu',
    success: 'Yêu cầu đã được chấp thuận.',
  },
  reject: {
    title: 'Từ chối yêu cầu?',
    description:
      'Nêu lý do ngắn gọn, rõ ràng để người gửi hiểu quyết định. Tránh tiết lộ đặc điểm bí mật của món đồ hoặc bằng chứng của người khác.',
    button: 'Xác nhận từ chối',
    success: 'Yêu cầu đã được từ chối.',
  },
  complete: {
    title: 'Bạn đã nhận lại đồ?',
    description:
      'Chỉ xác nhận sau khi bạn đã trực tiếp nhận lại đúng món đồ. Thao tác này hoàn tất yêu cầu và đóng tin nhặt được liên quan.',
    button: 'Xác nhận đã nhận đồ',
    success: 'Đã xác nhận nhận đồ. Yêu cầu đã hoàn tất.',
  },
}

export function ClaimDetailPage() {
  const { id = '' } = useParams()
  const { actorId, token } = useSession()
  const queryClient = useQueryClient()
  const [decision, setDecision] = useState<Decision | null>(null)
  const [reason, setReason] = useState('')
  const [confirmed, setConfirmed] = useState(false)
  const [success, setSuccess] = useState('')
  const [conflict, setConflict] = useState(false)
  const query = useQuery({
    queryKey: ['claims', actorId, 'detail', id],
    queryFn: ({ signal }) => claimsApi.detail(id, signal),
    enabled: Boolean(token) && UUID_PATTERN.test(id),
  })
  const mutation = useMutation({
    mutationFn: async ({
      action,
      claim,
    }: {
      action: Decision
      claim: ClaimDetail
    }): Promise<ClaimSummary> => {
      if (action === 'approve')
        return claimsApi.approve(claim.id, { expected_version: claim.version })
      if (action === 'reject')
        return claimsApi.reject(claim.id, {
          expected_version: claim.version,
          reason: reason.trim(),
        })
      return claimsApi.complete(claim.id, {
        expected_version: claim.version,
        receipt_confirmed: true,
      })
    },
    onSuccess: async (_, { action }) => {
      setDecision(null)
      setReason('')
      setConfirmed(false)
      setConflict(false)
      setSuccess(decisions[action].success)
      await Promise.all(
        ['claims', 'returns', 'notifications', 'posts', 'matches'].map((key) =>
          queryClient.invalidateQueries({ queryKey: [key] }),
        ),
      )
    },
    onError: async (error) => {
      if (error instanceof ApiError && error.status === 409) {
        setDecision(null)
        setConflict(true)
        setConfirmed(false)
        await queryClient.invalidateQueries({ queryKey: ['claims'] })
      }
    },
  })

  function openDecision(value: Decision) {
    mutation.reset()
    setDecision(value)
    setReason('')
    setConfirmed(false)
    setSuccess('')
    setConflict(false)
  }

  if (!UUID_PATTERN.test(id))
    return (
      <div className="page-container">
        <Link className="claim-back" to="/yeu-cau">
          <ArrowLeft size={16} />
          Về danh sách yêu cầu
        </Link>
        <div className="claims-error" role="alert">
          Mã yêu cầu không hợp lệ. Vui lòng kiểm tra lại đường dẫn.
        </div>
      </div>
    )
  if (query.isPending)
    return (
      <div className="page-container">
        <ClaimLoading />
      </div>
    )
  if (query.isError)
    return (
      <div className="page-container">
        <Link className="claim-back" to="/yeu-cau">
          <ArrowLeft size={16} />
          Về danh sách yêu cầu
        </Link>
        <ClaimError error={query.error} onRetry={() => void query.refetch()} />
      </div>
    )

  const claim = query.data
  const isClaimant = claim.claimant_id === actorId
  const canReview = !isClaimant && claim.status === 'PENDING'
  const canComplete =
    isClaimant && claim.status === 'APPROVED' && claim.return_summary?.status === 'HANDED_OVER'
  const disabledDecision =
    mutation.isPending ||
    (decision === 'reject' ? !reason.trim() || reason.trim().length > 1000 : !confirmed)

  return (
    <div className="page-container claims-page">
      <Link className="claim-back" to="/yeu-cau">
        <ArrowLeft size={16} aria-hidden="true" />
        Quay lại yêu cầu của tôi
      </Link>
      <header className="claims-header">
        <div>
          <span className="eyebrow">HỒ SƠ XÁC MINH</span>
          <h1>Yêu cầu #{claim.id.slice(0, 8)}</h1>
          <p>
            {isClaimant
              ? 'Theo dõi yêu cầu của bạn và xác nhận khi đã nhận lại đồ.'
              : 'Xem xét bằng chứng và hỗ trợ món đồ trở về đúng chủ.'}
          </p>
        </div>
        <ClaimStatusBadge status={claim.status} />
      </header>
      {success && (
        <div className="claims-success" role="status">
          <CircleCheck size={20} aria-hidden="true" />
          {success}
        </div>
      )}
      {conflict && (
        <div className="claims-error" role="alert">
          <p>{errorMessage(mutation.error)}</p>
          <p>
            Thông tin đã được tải lại. Hãy xem lại trạng thái và bằng chứng trước khi quyết định
            tiếp.
          </p>
        </div>
      )}
      <div className="claim-detail-layout">
        <div className="claim-detail-main">
          <section className="panel claim-section">
            <h2>
              <FileText aria-hidden="true" />
              Thông tin yêu cầu
            </h2>
            <dl className="claim-meta">
              <div>
                <dt>Mối liên hệ của bạn</dt>
                <dd>{isClaimant ? 'Người gửi yêu cầu' : 'Chủ tin nhặt được'}</dd>
              </div>
              <div>
                <dt>Ngày gửi</dt>
                <dd>
                  <time dateTime={claim.created_at}>{formatDate(claim.created_at)}</time>
                </dd>
              </div>
              <div className="claim-meta-wide">
                <dt>Mã tin nhặt được</dt>
                <dd className="claim-code">{claim.found_post_id}</dd>
              </div>
              <div className="claim-meta-wide">
                <dt>Mã yêu cầu</dt>
                <dd className="claim-code">{claim.id}</dd>
              </div>
              {claim.return_summary && (
                <div>
                  <dt>Tiến độ trao trả</dt>
                  <dd>{returnLabels[claim.return_summary.status]}</dd>
                </div>
              )}
              <div>
                <dt>Cập nhật gần nhất</dt>
                <dd>
                  <time dateTime={claim.updated_at}>{formatDate(claim.updated_at)}</time>
                </dd>
              </div>
            </dl>
          </section>
          <section className="panel claim-section">
            <h2>
              <LockKeyhole aria-hidden="true" />
              Bằng chứng sở hữu
            </h2>
            <div className="claim-notice claim-private">
              <ShieldCheck size={18} aria-hidden="true" />
              <p>
                Nội dung riêng tư giữa người yêu cầu và chủ tin. Không công khai hoặc chuyển tiếp
                bằng chứng.
              </p>
            </div>
            {claim.evidence.length > 0 ? (
              claim.evidence.map((item) => (
                <article className="claim-evidence" key={item.id}>
                  <p>{item.private_content}</p>
                  <time dateTime={item.created_at}>Được gửi lúc {formatDate(item.created_at)}</time>
                  <EvidenceFile claimId={claim.id} evidenceId={item.id} />
                </article>
              ))
            ) : (
              <p className="claim-field-hint" style={{ marginTop: 18 }}>
                Yêu cầu này chưa có bằng chứng để xem xét.
              </p>
            )}
            {isClaimant && claim.status === 'PENDING' && <ClaimEvidenceForm claim={claim} />}
          </section>
          {claim.rejection_reason && (
            <section className="panel claim-section">
              <h2>
                <XCircle aria-hidden="true" />
                Lý do từ chối
              </h2>
              <p style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere', lineHeight: 1.8 }}>
                {claim.rejection_reason}
              </p>
            </section>
          )}
          <section className="panel claim-section">
            <h2>
              <Clock3 aria-hidden="true" />
              Tiến trình yêu cầu
            </h2>
            <ol className="claim-timeline">
              <li>
                <CheckCircle2 size={19} aria-hidden="true" />
                <span>Đã gửi yêu cầu</span>
                <time dateTime={claim.created_at}>{formatDate(claim.created_at)}</time>
              </li>
              {claim.decided_at && (
                <li>
                  <CheckCircle2 size={19} aria-hidden="true" />
                  <span>
                    {claim.status === 'REJECTED' ? 'Yêu cầu bị từ chối' : 'Yêu cầu được chấp thuận'}
                  </span>
                  <time dateTime={claim.decided_at}>{formatDate(claim.decided_at)}</time>
                </li>
              )}
              {claim.return_summary?.handed_over_at && (
                <li>
                  <CheckCircle2 size={19} aria-hidden="true" />
                  <span>Đã ghi nhận bàn giao</span>
                  <time dateTime={claim.return_summary.handed_over_at}>
                    {formatDate(claim.return_summary.handed_over_at)}
                  </time>
                </li>
              )}
              {claim.returned_at && (
                <li>
                  <CheckCircle2 size={19} aria-hidden="true" />
                  <span>Đã xác nhận nhận lại đồ</span>
                  <time dateTime={claim.returned_at}>{formatDate(claim.returned_at)}</time>
                </li>
              )}
            </ol>
          </section>
        </div>
        <aside className="panel claim-action-panel">
          <h2>{claim.status === 'RETURNED' ? 'Món đồ đã trở về' : 'Bước tiếp theo'}</h2>
          {canReview && (
            <>
              <p>
                Đối chiếu các chi tiết trong bằng chứng với món đồ bạn đang giữ trước khi đưa ra
                quyết định.
              </p>
              <button
                className="button button-primary"
                disabled={query.isFetching || claim.evidence.length === 0}
                onClick={() => openDecision('approve')}
              >
                <Check size={17} aria-hidden="true" />
                Chấp thuận yêu cầu
              </button>
              <button
                className="button button-secondary"
                disabled={query.isFetching}
                onClick={() => openDecision('reject')}
              >
                <X size={17} aria-hidden="true" />
                Từ chối yêu cầu
              </button>
            </>
          )}
          {isClaimant && claim.status === 'PENDING' && (
            <>
              <p>
                Yêu cầu đang chờ chủ tin xem xét. Bạn có thể quay lại trang này để kiểm tra kết quả.
              </p>
              <div className="claim-notice">
                <Clock3 size={18} aria-hidden="true" />
                <p>Không gửi lại yêu cầu khi yêu cầu hiện tại vẫn đang mở.</p>
              </div>
            </>
          )}
          {canComplete && (
            <>
              <p>
                Việc bàn giao đã được ghi nhận. Hãy kiểm tra món đồ và xác nhận khi bạn đã nhận đúng
                đồ của mình.
              </p>
              <button
                className="button button-primary"
                disabled={query.isFetching}
                onClick={() => openDecision('complete')}
              >
                <Handshake size={18} aria-hidden="true" />
                Tôi đã nhận lại đồ
              </button>
            </>
          )}
          {(claim.status === 'APPROVED' || claim.status === 'RETURNED') && (
            <ReturnActions claim={claim} isClaimant={isClaimant} busy={query.isFetching} />
          )}
          {claim.status === 'REJECTED' && (
            <p>
              Yêu cầu này đã kết thúc. Bạn có thể xem lý do từ chối và chỉ gửi yêu cầu mới khi có
              căn cứ bổ sung, nếu tin vẫn tiếp nhận.
            </p>
          )}
          {claim.status === 'RETURNED' && (
            <>
              <p>
                Người gửi đã xác nhận nhận lại đồ. Cảm ơn bạn đã góp phần giúp một món đồ tìm được
                đường về.
              </p>
              <div className="claim-notice claim-private">
                <ClipboardCheck size={19} aria-hidden="true" />
                <p>Quá trình xác minh và trao trả đã hoàn tất.</p>
              </div>
            </>
          )}
          <button
            className="button button-secondary"
            type="button"
            disabled={query.isFetching}
            onClick={() => void query.refetch()}
          >
            <RefreshCw
              size={16}
              className={query.isFetching ? 'claim-spin' : ''}
              aria-hidden="true"
            />
            {query.isFetching ? 'Đang cập nhật…' : 'Cập nhật trạng thái'}
          </button>
        </aside>
      </div>
      <Dialog.Root
        open={decision !== null}
        onOpenChange={(open) => {
          if (!open && !mutation.isPending) setDecision(null)
        }}
      >
        <Dialog.Portal>
          <Dialog.Overlay className="claim-dialog-overlay" />
          <Dialog.Content
            className="claim-dialog"
            onEscapeKeyDown={(event) => {
              if (mutation.isPending) event.preventDefault()
            }}
            onPointerDownOutside={(event) => {
              if (mutation.isPending) event.preventDefault()
            }}
          >
            <Dialog.Title>
              {decision ? decisions[decision].title : 'Xác nhận thao tác'}
            </Dialog.Title>
            <Dialog.Description className="claim-dialog-description">
              {decision ? decisions[decision].description : ''}
            </Dialog.Description>
            {mutation.isError && !conflict && <ClaimError error={mutation.error} />}
            {decision === 'reject' ? (
              <div className="claim-field">
                <label htmlFor="claim-rejection-reason">Lý do từ chối</label>
                <textarea
                  id="claim-rejection-reason"
                  value={reason}
                  onChange={(event) => setReason(event.target.value)}
                  maxLength={1000}
                  disabled={mutation.isPending}
                  placeholder="Nhập lý do để người gửi có thể hiểu quyết định…"
                  required
                />
                <span className="claim-field-count">{reason.length} / 1.000 ký tự</span>
              </div>
            ) : (
              <label className="claim-checkbox">
                <input
                  type="checkbox"
                  checked={confirmed}
                  onChange={(event) => setConfirmed(event.target.checked)}
                  disabled={mutation.isPending}
                />
                {decision === 'complete'
                  ? 'Tôi xác nhận đã trực tiếp nhận lại đúng món đồ của mình.'
                  : 'Tôi đã xem xét bằng chứng và xác nhận đủ căn cứ sở hữu.'}
              </label>
            )}
            <div className="claim-dialog-footer">
              <Dialog.Close asChild>
                <button className="button button-secondary" disabled={mutation.isPending}>
                  Quay lại
                </button>
              </Dialog.Close>
              <button
                className="button button-primary"
                disabled={disabledDecision}
                onClick={() => {
                  if (decision) mutation.mutate({ action: decision, claim })
                }}
              >
                {mutation.isPending && (
                  <LoaderCircle size={16} className="claim-spin" aria-hidden="true" />
                )}
                {mutation.isPending
                  ? 'Đang xử lý…'
                  : decision
                    ? decisions[decision].button
                    : 'Xác nhận'}
              </button>
            </div>
            <Dialog.Close asChild>
              <button
                className="claim-dialog-close"
                aria-label="Đóng hộp thoại"
                disabled={mutation.isPending}
              >
                <X size={18} aria-hidden="true" />
              </button>
            </Dialog.Close>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </div>
  )
}
