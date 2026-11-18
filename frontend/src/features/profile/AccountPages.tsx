import { useState, type FormEvent } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { ArrowRight, ClipboardCheck, HandHeart, Search, ShieldCheck } from 'lucide-react'
import { EmptyState, PageHeading, SafetyNote } from '../../components/ui/shared'
import { ApiFeedback, Pagination } from '../../components/ui/live'
import { formatDate } from '../../components/ui/live-format'
import { ApiError } from '../../lib/api'
import {
  identityApi,
  notificationsApi,
  postsApi,
  type Match,
  type Notification,
  type User,
} from '../../lib/api/system'
import { useAccount } from '../auth/useAccount'
import { useSession } from '../auth/session'
import { PostCard } from '../posts/PostCard'

export function DashboardPage() {
  const account = useAccount()
  const { actorId } = useSession()
  const mine = useQuery({
    queryKey: ['posts', 'mine', actorId, 1],
    queryFn: ({ signal }) => postsApi.mine(1, signal),
  })
  const unread = useQuery({
    queryKey: ['notifications', actorId, 1, false],
    queryFn: ({ signal }) => notificationsApi.list(1, false, signal),
  })
  return (
    <>
      <PageHeading
        title={
          account.data?.full_name ? `Xin chào, ${account.data.full_name}` : 'Không gian cá nhân'
        }
      />
      <ApiFeedback
        pending={account.isPending}
        error={account.error}
        retry={() => void account.refetch()}
      />
      <div className="dashboard-actions">
        <Link className="panel" to="/tin-cua-toi">
          <h2>Tin của tôi</h2>
          <p>{mine.data ? `${mine.data.total} tin` : 'Quản lý tin của bạn'}</p>
          <ArrowRight size={18} />
        </Link>
        <Link className="panel" to="/yeu-cau">
          <h2>Yêu cầu xác minh</h2>
          <p>Xem yêu cầu đã gửi và cần xử lý.</p>
          <ArrowRight size={18} />
        </Link>
        <Link className="panel" to="/thong-bao">
          <h2>Thông báo</h2>
          <p>{unread.data ? `${unread.data.pagination.total} chưa đọc` : 'Theo dõi cập nhật'}</p>
          <ArrowRight size={18} />
        </Link>
      </div>
      <div className="live-actions">
        <Link className="button button-primary" to="/dang-tin">
          Đăng tin
        </Link>
        <Link className="button button-secondary" to="/goi-y">
          Xem gợi ý
        </Link>
      </div>
      <SafetyNote />
    </>
  )
}

export function ProfilePage() {
  const account = useAccount()
  return (
    <>
      <PageHeading title="Hồ sơ cá nhân" />
      <ApiFeedback
        pending={account.isPending}
        error={account.error}
        retry={() => void account.refetch()}
      />
      {account.data && <ProfileForm key={account.data.id} user={account.data} />}
    </>
  )
}

function ProfileForm({ user }: { user: User }) {
  const client = useQueryClient()
  const change = useMutation({
    mutationFn: identityApi.update,
    onSuccess: (updated) => {
      client.setQueryData(['account', 'profile', user.id], updated)
      void client.invalidateQueries({ queryKey: ['public-profile', user.id] })
    },
  })
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    const value = (name: string) => String(form.get(name) ?? '').trim()
    change.mutate({
      full_name: value('full_name'),
      phone: value('phone') || null,
      avatar_url: value('avatar_url') || null,
    })
  }
  return (
    <form className="panel live-stack" onSubmit={submit}>
      <label className="field">
        Họ và tên
        <input name="full_name" required maxLength={100} defaultValue={user.full_name ?? ''} />
      </label>
      <label className="field">
        Email
        <input type="email" readOnly value={user.email ?? ''} />
      </label>
      <label className="field">
        Số điện thoại
        <input type="tel" name="phone" maxLength={32} defaultValue={user.phone ?? ''} />
      </label>
      <label className="field">
        URL ảnh đại diện
        <input type="url" name="avatar_url" maxLength={2048} defaultValue={user.avatar_url ?? ''} />
      </label>
      <ApiFeedback error={change.error} />
      {change.isSuccess && <p role="status">Đã cập nhật hồ sơ.</p>}
      <div className="live-actions">
        <button className="button button-primary" type="submit" disabled={change.isPending}>
          Lưu thay đổi
        </button>
      </div>
    </form>
  )
}

const postStatus = { OPEN: 'Đang mở', CLOSED: 'Đã đóng', HIDDEN: 'Đã ẩn' }

export function MyPostsPage() {
  const { actorId } = useSession()
  const [page, setPage] = useState(1)
  const [confirm, setConfirm] = useState<string | null>(null)
  const cache = useQueryClient()
  const mine = useQuery({
    queryKey: ['posts', 'mine', actorId, page],
    queryFn: ({ signal }) => postsApi.mine(page, signal),
  })
  const remove = useMutation({
    mutationFn: postsApi.remove,
    onSuccess: async () => {
      setConfirm(null)
      if (mine.data?.items.length === 1 && page > 1) setPage(page - 1)
      await Promise.all([
        cache.invalidateQueries({ queryKey: ['posts'] }),
        cache.invalidateQueries({ queryKey: ['matches'] }),
      ])
    },
  })
  return (
    <>
      <PageHeading
        title="Tin của tôi"
        action={
          <Link className="button button-primary" to="/dang-tin">
            Đăng tin
          </Link>
        }
      />
      <ApiFeedback pending={mine.isPending} error={mine.error} retry={() => void mine.refetch()} />
      <ApiFeedback error={remove.error} />
      {mine.data?.items.length === 0 && (
        <EmptyState title="Chưa có tin">Tin bạn đăng sẽ xuất hiện tại đây.</EmptyState>
      )}
      <div className="live-stack">
        {mine.data?.items.map((post) => (
          <article className="panel live-row" key={post.id}>
            <div>
              <h2>
                {post.status === 'HIDDEN' ? (
                  (post.title ?? 'Tin về đồ vật')
                ) : (
                  <Link to={`/do-vat/${post.id}`}>{post.title ?? 'Tin về đồ vật'}</Link>
                )}
              </h2>
              <p className="muted">
                {postStatus[post.status]} · {formatDate(post.event_time)}
              </p>
            </div>
            {post.status === 'OPEN' && (
              <div className="live-actions">
                <Link className="text-link" to={`/tin-cua-toi/${post.id}/sua`}>
                  Sửa tin
                </Link>
                <Link className="text-link" to={`/goi-y?tin=${post.id}`}>
                  Xem gợi ý
                </Link>
                {confirm === post.id ? (
                  <>
                    <button
                      className="button button-secondary"
                      disabled={remove.isPending}
                      onClick={() => remove.mutate(post.id)}
                    >
                      Xác nhận xóa
                    </button>
                    <button className="text-link" onClick={() => setConfirm(null)}>
                      Giữ tin
                    </button>
                  </>
                ) : (
                  <button className="text-link" onClick={() => setConfirm(post.id)}>
                    Xóa tin
                  </button>
                )}
              </div>
            )}
          </article>
        ))}
      </div>
      {mine.data && <Pagination page={page} pages={mine.data.total_pages} onPage={setPage} />}
    </>
  )
}

export function MatchesPage() {
  const { actorId } = useSession()
  const [params, setParams] = useSearchParams()
  const [postPage, setPostPage] = useState(1)
  const [page, setPage] = useState(1)
  const selected = params.get('tin') || ''
  const cache = useQueryClient()
  const mine = useQuery({
    queryKey: ['posts', 'mine', actorId, postPage],
    queryFn: ({ signal }) => postsApi.mine(postPage, signal),
  })
  const matches = useQuery({
    queryKey: ['matches', selected, page],
    enabled: Boolean(selected),
    queryFn: ({ signal }) => postsApi.matches(selected, page, signal),
  })
  const recalc = useMutation({
    mutationFn: postsApi.recalculate,
    onSuccess: (data, id) => {
      cache.setQueryData(['matches', id, 1], data)
      void cache.invalidateQueries({ queryKey: ['matches', id] })
      if (id === selected) setPage(1)
    },
  })
  const eligible = mine.data?.items.filter((post) => post.status === 'OPEN') ?? []
  const status = matches.error
  return (
    <>
      <PageHeading
        title="Gợi ý phù hợp"
        description="Chọn một tin đang mở để tìm các tin tương ứng."
      />
      <ApiFeedback pending={mine.isPending} error={mine.error} retry={() => void mine.refetch()} />
      {mine.data?.total === 0 && (
        <EmptyState
          title="Bạn chưa có tin để so khớp"
          action={
            <Link className="button button-primary" to="/dang-tin">
              Đăng tin
            </Link>
          }
        >
          Bạn có thể tính gợi ý sau khi đăng tin.
        </EmptyState>
      )}
      {mine.data && mine.data.total > 0 && (
        <div className="panel live-stack">
          <label className="field">
            Tin cần so khớp
            <select
              value={selected}
              onChange={(event) => {
                recalc.reset()
                setPage(1)
                setParams(event.target.value ? { tin: event.target.value } : {})
              }}
            >
              <option value="">Chọn tin</option>
              {selected && !eligible.some((post) => post.id === selected) && (
                <option value={selected}>Tin đã chọn</option>
              )}
              {eligible.map((post) => (
                <option key={post.id} value={post.id}>
                  {post.title ?? 'Tin về đồ vật'}
                </option>
              ))}
            </select>
          </label>
          <Pagination page={postPage} pages={mine.data.total_pages} onPage={setPostPage} />
          {selected && (
            <button
              className="button button-primary"
              disabled={recalc.isPending}
              onClick={() => recalc.mutate(selected)}
            >
              {recalc.isPending ? 'Đang tính…' : 'Tính lại gợi ý'}
            </button>
          )}
        </div>
      )}
      {selected && (
        <ApiFeedback
          pending={matches.isPending}
          error={status}
          retry={
            status instanceof ApiError && status.code === 'MATCHES_NOT_READY'
              ? undefined
              : () => void matches.refetch()
          }
        />
      )}
      <ApiFeedback error={recalc.error} />
      {matches.data?.items.length === 0 && (
        <EmptyState title="Chưa có gợi ý phù hợp">
          Hãy tính lại khi có thêm tin hoặc khi nội dung thay đổi.
        </EmptyState>
      )}
      <div className="live-stack">
        {matches.data?.items.map((match) => (
          <article className="panel live-row" key={match.id}>
            <div>
              <h2>
                <Link to={`/do-vat/${match.candidate.id}`}>{match.candidate.title}</Link>
              </h2>
              <p>
                {match.candidate.location.name} · {formatDate(match.candidate.event_time)}
              </p>
            </div>
            <Link className="text-link" to={`/goi-y/${match.id}?tin=${selected}`}>
              {match.score} điểm · Chi tiết gợi ý
            </Link>
          </article>
        ))}
      </div>
      {matches.data && (
        <Pagination page={page} pages={matches.data.pagination.total_pages} onPage={setPage} />
      )}
    </>
  )
}

export function MatchDetailPage() {
  const { id = '' } = useParams()
  const [params] = useSearchParams()
  const post = params.get('tin') || ''
  const match = useQuery({
    queryKey: ['matches', 'detail', id, post],
    queryFn: ({ signal }) => postsApi.match(id, post, signal),
  })
  return (
    <>
      <Link className="back-link" to={post ? `/goi-y?tin=${post}` : '/goi-y'}>
        ← Quay lại gợi ý
      </Link>
      <PageHeading title="Chi tiết gợi ý" />
      <ApiFeedback
        pending={match.isPending}
        error={match.error}
        retry={() => void match.refetch()}
      />
      {match.data && <MatchInfo match={match.data} />}
    </>
  )
}

function MatchInfo({ match }: { match: Match }) {
  const post = match.candidate
  return (
    <div className="live-stack">
      <PostCard
        id={post.id}
        title={post.title}
        type={post.type}
        category={post.category.name}
        location={post.location.name}
        time={post.event_time}
      />
      <div className="panel">
        <h2>{match.score} điểm tương đồng</h2>
        <p>{match.explanation}</p>
      </div>
    </div>
  )
}

function notificationLink(item: Notification) {
  if (item.resource_type === 'CLAIM' && item.resource_id) return `/yeu-cau/${item.resource_id}`
  if (item.resource_type === 'POST') return '/tin-cua-toi'
  return null
}

export function NotificationsPage() {
  const { actorId } = useSession()
  const [page, setPage] = useState(1)
  const [onlyUnread, setOnlyUnread] = useState(false)
  const cache = useQueryClient()
  const rows = useQuery({
    queryKey: ['notifications', actorId, page, onlyUnread ? false : undefined],
    queryFn: ({ signal }) => notificationsApi.list(page, onlyUnread ? false : undefined, signal),
    refetchInterval: 20_000,
  })
  const mark = useMutation({
    mutationFn: notificationsApi.read,
    onSuccess: async () => {
      if (onlyUnread && rows.data?.items.length === 1 && page > 1) setPage(page - 1)
      await cache.invalidateQueries({ queryKey: ['notifications'] })
    },
  })
  return (
    <>
      <PageHeading title="Thông báo" />
      <label className="live-actions">
        <input
          type="checkbox"
          checked={onlyUnread}
          onChange={(event) => {
            setOnlyUnread(event.target.checked)
            setPage(1)
          }}
        />{' '}
        Chỉ hiện chưa đọc
      </label>
      <ApiFeedback pending={rows.isPending} error={rows.error} retry={() => void rows.refetch()} />
      <ApiFeedback error={mark.error} />
      {rows.data?.items.length === 0 && (
        <EmptyState title="Chưa có thông báo">Các cập nhật của bạn sẽ xuất hiện ở đây.</EmptyState>
      )}
      <div className="live-stack">
        {rows.data?.items.map((item) => {
          const link = notificationLink(item)
          return (
            <article key={item.id} className="panel live-row">
              <div>
                <h2>{item.title}</h2>
                {item.message !== item.title && <p>{item.message}</p>}
                <p className="muted">
                  {formatDate(item.created_at)} · {item.is_read ? 'Đã đọc' : 'Chưa đọc'}
                </p>
              </div>
              <div className="live-actions">
                {link && (
                  <Link className="text-link" to={link}>
                    Xem chi tiết
                  </Link>
                )}
                {!item.is_read && (
                  <button
                    className="button button-secondary"
                    disabled={mark.isPending}
                    onClick={() => mark.mutate(item.id)}
                  >
                    Đánh dấu đã đọc
                  </button>
                )}
              </div>
            </article>
          )
        })}
      </div>
      {rows.data && (
        <Pagination page={page} pages={rows.data.pagination.total_pages} onPage={setPage} />
      )}
    </>
  )
}

export function GuidePage() {
  return (
    <div className="container page-container narrow">
      <PageHeading
        eyebrow="Tìm lại với sự an tâm"
        title="Cùng nhau trao trả an toàn"
        description="Một vài nguyên tắc nhỏ để bảo vệ bạn và món đồ."
      />
      <div className="guide-grid">
        {[
          {
            icon: Search,
            title: 'Mô tả vừa đủ, giữ lại đặc điểm riêng',
            text: 'Công khai loại đồ, màu sắc và khu vực. Giữ lại dấu hiệu đặc biệt, số seri hoặc nội dung bên trong để xác minh chủ sở hữu.',
          },
          {
            icon: ShieldCheck,
            title: 'Bằng chứng chỉ dành cho người liên quan',
            text: 'Gửi đặc điểm riêng trong yêu cầu xác minh. Không đăng ảnh căn cước, thông tin ngân hàng hoặc mã truy cập lên bảng tin.',
          },
          {
            icon: HandHeart,
            title: 'Hẹn gặp ở nơi công cộng',
            text: 'Chọn nơi có bảo vệ hoặc nhiều người qua lại. Không chuyển tiền hay cung cấp mật khẩu để nhận lại đồ.',
          },
          {
            icon: ClipboardCheck,
            title: 'Chỉ xác nhận sau khi đã nhận đồ',
            text: 'Kiểm tra món đồ khi gặp mặt. Chỉ xác nhận hoàn tất khi bạn thực sự đã nhận lại tài sản.',
          },
        ].map((tip, i) => (
          <article className="panel guide-card" key={tip.title}>
            <span className="step-icon">
              <tip.icon size={25} />
            </span>
            <span className="step-number">0{i + 1}</span>
            <h2>{tip.title}</h2>
            <p>{tip.text}</p>
          </article>
        ))}
      </div>
      <Link className="button button-primary" to="/kham-pha">
        Bắt đầu tìm kiếm
        <ArrowRight size={17} />
      </Link>
    </div>
  )
}
