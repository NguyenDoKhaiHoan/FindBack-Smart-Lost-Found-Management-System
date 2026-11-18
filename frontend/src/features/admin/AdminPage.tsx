import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { ApiFeedback, Pagination } from '../../components/ui/live'
import { EmptyState, PageHeading } from '../../components/ui/shared'
import { moderationApi, type ReportStatus, type Statistics } from '../../lib/api/system'
import { useAccount } from '../auth/useAccount'

const labels: Record<keyof Statistics, string> = {
  users: 'Tài khoản',
  posts: 'Tin đăng',
  public_posts: 'Tin công khai',
  hidden_posts: 'Tin đã ẩn',
  claims: 'Yêu cầu xác minh',
  completed_returns: 'Lượt trao trả hoàn tất',
  pending_reports: 'Báo cáo đang xử lý',
  resolved_reports: 'Báo cáo đã giải quyết',
}
const reportLabels: Record<ReportStatus, string> = {
  PENDING: 'Chờ xử lý',
  REVIEWING: 'Đang xem xét',
  RESOLVED: 'Đã giải quyết',
  DISMISSED: 'Đã bác bỏ',
}

export function AdminPage() {
  const account = useAccount()
  return (
    <div className="container page-container">
      <PageHeading title="Quản trị FindBack" />
      <ApiFeedback
        pending={account.isPending}
        error={account.error}
        retry={() => void account.refetch()}
      />
      {account.data &&
        (account.data.role === 'ADMIN' ? (
          <AdminWorkspace />
        ) : (
          <EmptyState
            title="Bạn không có quyền quản trị"
            action={
              <Link className="button button-secondary" to="/">
                Về trang chủ
              </Link>
            }
          >
            Khu vực này dành cho tài khoản quản trị.
          </EmptyState>
        ))}
    </div>
  )
}

function AdminWorkspace() {
  const stats = useQuery({
    queryKey: ['admin', 'statistics'],
    queryFn: ({ signal }) => moderationApi.stats(signal),
  })
  return (
    <div className="live-stack">
      <section aria-label="Thống kê quản trị">
        <ApiFeedback
          pending={stats.isPending}
          error={stats.error}
          retry={() => void stats.refetch()}
        />
        {stats.data && (
          <dl className="live-stats">
            {Object.entries(labels).map(([key, text]) => (
              <div className="panel" key={key}>
                <dt>{text}</dt>
                <dd>{stats.data[key as keyof Statistics]}</dd>
              </div>
            ))}
          </dl>
        )}
      </section>
      <ReportsPanel />
      <PostsPanel />
    </div>
  )
}

function ReportsPanel() {
  const [page, setPage] = useState(1)
  const [status, setStatus] = useState('')
  const queryClient = useQueryClient()
  const reports = useQuery({
    queryKey: ['admin', 'reports', page, status],
    queryFn: ({ signal }) => moderationApi.reports(page, status, signal),
  })
  const review = useMutation({
    mutationFn: ({
      id,
      next,
      note,
    }: {
      id: string
      next: Exclude<ReportStatus, 'PENDING'>
      note: string
    }) => moderationApi.review(id, next, note),
    onSuccess: async () => {
      if (status && reports.data?.items.length === 1 && page > 1) setPage(page - 1)
      await queryClient.invalidateQueries({ queryKey: ['admin'] })
    },
  })
  return (
    <section className="panel live-stack">
      <h2>Báo cáo vi phạm</h2>
      <label className="field">
        Trạng thái báo cáo
        <select
          value={status}
          onChange={(event) => {
            setStatus(event.target.value)
            setPage(1)
          }}
        >
          <option value="">Tất cả</option>
          {Object.entries(reportLabels).map(([key, label]) => (
            <option key={key} value={key}>
              {label}
            </option>
          ))}
        </select>
      </label>
      <ApiFeedback
        pending={reports.isPending}
        error={reports.error}
        retry={() => void reports.refetch()}
      />
      {reports.data?.items.length === 0 && <p className="muted">Không có báo cáo phù hợp.</p>}
      {reports.data?.items.map((report) => (
        <article key={report.id} className="live-admin-row live-stack">
          <div>
            <h3>{reportLabels[report.status]}</h3>
            <p className="preserve-lines">{report.reason}</p>
            <Link className="text-link" to={`/do-vat/${report.post_id}`}>
              Xem tin được báo cáo
            </Link>
          </div>
          {report.resolution_note && <p>Ghi chú xử lý: {report.resolution_note}</p>}
          {(report.status === 'PENDING' || report.status === 'REVIEWING') && (
            <form
              className="live-stack"
              key={report.status}
              onSubmit={(event) => {
                event.preventDefault()
                const data = new FormData(event.currentTarget)
                const next = data.get('status') as Exclude<ReportStatus, 'PENDING'>
                const note = String(data.get('note')).trim()
                if (note) review.mutate({ id: report.id, next, note })
              }}
            >
              <label className="field">
                Kết quả xử lý
                <select name="status">
                  {report.status === 'PENDING' && <option value="REVIEWING">Đang xem xét</option>}
                  <option value="RESOLVED">Đã giải quyết</option>
                  <option value="DISMISSED">Bác bỏ</option>
                </select>
              </label>
              <label className="field">
                Ghi chú xử lý
                <textarea name="note" maxLength={2000} required rows={2} />
              </label>
              {review.variables?.id === report.id && <ApiFeedback error={review.error} />}
              <button className="button button-primary" disabled={review.isPending} type="submit">
                Lưu xử lý
              </button>
            </form>
          )}
        </article>
      ))}
      {reports.data && <Pagination page={page} pages={reports.data.total_pages} onPage={setPage} />}
    </section>
  )
}

function PostsPanel() {
  const [page, setPage] = useState(1)
  const [status, setStatus] = useState('')
  const queryClient = useQueryClient()
  const posts = useQuery({
    queryKey: ['admin', 'posts', page, status],
    queryFn: ({ signal }) => moderationApi.posts(page, status, signal),
  })
  const hide = useMutation({
    mutationFn: ({ id, reason }: { id: string; reason: string }) => moderationApi.hide(id, reason),
    onSuccess: async () => {
      if (status === 'OPEN' && posts.data?.items.length === 1 && page > 1) setPage(page - 1)
      await Promise.all(
        ['admin', 'posts', 'matches'].map((key) =>
          queryClient.invalidateQueries({ queryKey: [key] }),
        ),
      )
    },
  })
  return (
    <section className="panel live-stack">
      <h2>Kiểm duyệt tin đăng</h2>
      <label className="field">
        Trạng thái tin
        <select
          value={status}
          onChange={(event) => {
            setStatus(event.target.value)
            setPage(1)
          }}
        >
          <option value="">Tất cả</option>
          <option value="OPEN">Đang mở</option>
          <option value="HIDDEN">Đã ẩn</option>
          <option value="CLOSED">Đã đóng</option>
        </select>
      </label>
      <ApiFeedback
        pending={posts.isPending}
        error={posts.error}
        retry={() => void posts.refetch()}
      />
      {posts.data?.items.length === 0 && <p className="muted">Không có tin phù hợp.</p>}
      {posts.data?.items.map((post) => (
        <article key={post.id} className="live-admin-row live-stack">
          <h3>{post.title ?? 'Tin về đồ vật'}</h3>
          {post.description && <p className="preserve-lines">{post.description}</p>}
          {post.status === 'HIDDEN' && (
            <p>Đã ẩn{post.moderation_reason && ` · ${post.moderation_reason}`}</p>
          )}
          {post.status === 'CLOSED' && <p>Đã đóng</p>}
          {post.status === 'OPEN' && (
            <form
              className="live-stack"
              onSubmit={(event) => {
                event.preventDefault()
                const reason = String(new FormData(event.currentTarget).get('reason')).trim()
                if (reason) hide.mutate({ id: post.id, reason })
              }}
            >
              <label className="field">
                Lý do ẩn tin
                <textarea name="reason" maxLength={2000} required rows={2} />
              </label>
              {hide.variables?.id === post.id && <ApiFeedback error={hide.error} />}
              <button className="button button-secondary" disabled={hide.isPending} type="submit">
                Ẩn tin
              </button>
            </form>
          )}
        </article>
      ))}
      {posts.data && (
        <Pagination page={page} pages={posts.data.pagination.total_pages} onPage={setPage} />
      )}
    </section>
  )
}
