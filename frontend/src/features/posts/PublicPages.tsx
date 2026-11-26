import { useRef, useState, type FormEvent } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useLocation, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { ArrowUpRight, Box, MapPin } from 'lucide-react'
import { EmptyState, PageHeading, SafetyNote, SearchBar } from '../../components/ui/shared'
import { ApiFeedback, Pagination } from '../../components/ui/live'
import {
  formatDate,
  imageTypes,
  localDateTime,
  maxImageSize,
} from '../../components/ui/live-format'
import { apiAssetUrl } from '../../lib/api/client'
import {
  identityApi,
  moderationApi,
  postsApi,
  type Category,
  type Post,
  type PostInput,
  type PostType,
} from '../../lib/api/system'
import { useSession } from '../auth/session'
import { ImageSearch, SuggestedMatches } from '../ai/AISearch'
import { PostDraftAssistant } from '../ai/PostDraftAssistant'
import type { Draft } from '../ai/api'
import type { HotspotPin } from '../hotspots/api'
import { HotspotPinEditor } from '../hotspots/HotspotPinEditor'
import { regions as locations } from '../hotspots/geography'
import { PostCard } from './PostCard'

const colors = [
  ['BLACK', 'Đen'],
  ['WHITE', 'Trắng'],
  ['GRAY', 'Xám'],
  ['RED', 'Đỏ'],
  ['ORANGE', 'Cam'],
  ['YELLOW', 'Vàng'],
  ['GREEN', 'Xanh lá'],
  ['BLUE', 'Xanh dương'],
  ['PURPLE', 'Tím'],
  ['PINK', 'Hồng'],
  ['BROWN', 'Nâu'],
  ['OTHER', 'Màu khác'],
]

function timeBound(value: string) {
  const date = new Date(`${value}T00:00:00`)
  return value && !Number.isNaN(date.getTime()) ? date.toISOString() : undefined
}

export function ExplorePage() {
  const [params, setParams] = useSearchParams()
  const keyword = params.get('q') || ''
  const category = params.get('danh-muc') || ''
  const kind = params.get('loai') || ''
  const type = kind === 'found' ? 'FOUND' : kind === 'lost' ? 'LOST' : ''
  const location = params.get('dia-diem') || ''
  const sort = params.get('sap-xep') || 'newest'
  const from = params.get('tu-ngay') || ''
  const until = params.get('truoc-ngay') || ''
  const requestedPage = Number(params.get('trang') || 1)
  const page =
    Number.isInteger(requestedPage) && requestedPage > 0 ? Math.min(requestedPage, 10000) : 1
  const filters = {
    q: keyword,
    category_id: category,
    location_code: location,
    type,
    sort,
    event_from: timeBound(from),
    event_to: timeBound(until),
    page,
    page_size: 9,
  }
  const catalog = useQuery({
    queryKey: ['categories'],
    queryFn: ({ signal }) => postsApi.categories(signal),
  })
  const results = useQuery({
    queryKey: ['posts', 'search', filters],
    queryFn: ({ signal }) => postsApi.search(filters, signal),
  })
  function update(key: string, value: string) {
    setParams((previous) => {
      const next = new URLSearchParams(previous)
      if (value) next.set(key, value)
      else next.delete(key)
      if (key !== 'trang') next.delete('trang')
      return next
    })
  }
  return (
    <div className="container page-container">
      <PageHeading
        title="Tìm món đồ của bạn"
        action={
          <Link className="button button-primary" to="/dang-tin">
            Đăng tin <ArrowUpRight size={17} />
          </Link>
        }
      />
      <SearchBar key={keyword} initial={keyword} onSearch={(value) => update('q', value.trim())} />
      <ImageSearch type={type} category={category} postImage={params.get('anh')} />
      <div className="explore-grid live-split">
        <aside className="panel filter-panel">
          <h2>Bộ lọc</h2>
          <label className="field">
            Loại tin
            <select value={kind} onChange={(event) => update('loai', event.target.value)}>
              <option value="">Tất cả</option>
              <option value="lost">Đồ thất lạc</option>
              <option value="found">Đồ nhặt được</option>
            </select>
          </label>
          <label className="field">
            Danh mục
            <select value={category} onChange={(event) => update('danh-muc', event.target.value)}>
              <option value="">Tất cả danh mục</option>
              {catalog.data?.map((row) => (
                <option key={row.id} value={row.id}>
                  {row.name}
                </option>
              ))}
            </select>
          </label>
          <ApiFeedback error={catalog.error} retry={() => void catalog.refetch()} />
          <label className="field">
            Khu vực
            <select value={location} onChange={(event) => update('dia-diem', event.target.value)}>
              <option value="">Tất cả khu vực</option>
              {locations.map(([code, name]) => (
                <option key={code} value={code}>
                  {name}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            Từ ngày
            <input
              type="date"
              value={from}
              onChange={(event) => update('tu-ngay', event.target.value)}
            />
          </label>
          <label className="field">
            Trước ngày
            <input
              type="date"
              value={until}
              onChange={(event) => update('truoc-ngay', event.target.value)}
            />
          </label>
          <button type="button" className="text-link" onClick={() => setParams({})}>
            Xóa bộ lọc
          </button>
        </aside>
        <section className="results-panel" aria-label="Kết quả tìm kiếm">
          <div className="live-actions">
            {results.data && (
              <p className="muted" role="status">
                {results.data.pagination.total} tin phù hợp
              </p>
            )}
            <label className="field">
              Sắp xếp
              <select value={sort} onChange={(event) => update('sap-xep', event.target.value)}>
                <option value="newest">Mới đăng</option>
                <option value="oldest">Cũ nhất</option>
                <option value="event_desc">Thời điểm gần nhất</option>
                <option value="event_asc">Thời điểm xa nhất</option>
              </select>
            </label>
          </div>
          <ApiFeedback
            pending={results.isPending}
            error={results.error}
            retry={() => void results.refetch()}
          />
          {results.data?.items.length === 0 && (
            <EmptyState title="Chưa tìm thấy món đồ phù hợp">
              Thử đổi từ khóa hoặc bộ lọc.
            </EmptyState>
          )}
          {results.data && (
            <>
              <div className="items-grid live-post-grid">
                {results.data.items.map((item) => (
                  <PostCard
                    key={item.id}
                    id={item.id}
                    title={item.title}
                    type={item.type}
                    category={item.category.name}
                    location={item.location.name}
                    time={item.event_time}
                  />
                ))}
              </div>
              <Pagination
                page={page}
                pages={results.data.pagination.total_pages}
                onPage={(value) => update('trang', String(value))}
              />
            </>
          )}
        </section>
      </div>
    </div>
  )
}

export function ItemDetailPage() {
  const { id = '' } = useParams()
  const { actorId, token } = useSession()
  const location = useLocation()
  const row = useQuery({
    queryKey: ['posts', 'detail', id],
    queryFn: ({ signal }) => postsApi.detail(id, signal),
  })
  const authorId = row.data?.user_id
  const author = useQuery({
    queryKey: ['public-profile', authorId],
    enabled: Boolean(authorId),
    queryFn: ({ signal }) => identityApi.publicProfile(authorId!, signal),
  })
  if (!row.data)
    return (
      <div className="container page-container">
        <Link className="back-link" to="/kham-pha">
          ← Quay lại bảng tin
        </Link>
        <ApiFeedback pending={row.isPending} error={row.error} retry={() => void row.refetch()} />
      </div>
    )
  const post = row.data
  const owner = post.user_id === actorId
  return (
    <div className="container page-container">
      <Link className="back-link" to="/kham-pha">
        ← Quay lại bảng tin
      </Link>
      <PageHeading
        eyebrow={post.type === 'FOUND' ? 'Đồ nhặt được' : 'Đồ thất lạc'}
        title={post.title ?? 'Tin về đồ vật'}
      />
      <div className="live-split detail-split">
        <article className="panel live-stack">
          {post.images.length ? (
            <div className="post-photos">
              {post.images.map((image, index) => (
                <DetailPhoto
                  key={image.id}
                  src={apiAssetUrl(image.file_path)}
                  alt={`Ảnh ${index + 1} của ${post.title ?? 'món đồ'}`}
                />
              ))}
            </div>
          ) : (
            <div className="post-photo-empty">
              <Box size={48} aria-hidden="true" />
              <span>Tin này chưa có ảnh</span>
            </div>
          )}
          <h2>Thông tin đồ vật</h2>
          {post.item_name && <p>Tên đồ vật: {post.item_name}</p>}
          <p className="preserve-lines">{post.description ?? 'Chưa có mô tả.'}</p>
          {post.location && (
            <p className="live-actions">
              <MapPin size={16} aria-hidden="true" /> {post.location}
            </p>
          )}
          <p>{formatDate(post.event_time)}</p>
          {post.status === 'OPEN' && post.images.length > 0 && (
            <Link className="text-link" to={`/kham-pha?anh=${post.images[0].id}`}>
              Tìm đồ có ảnh tương tự
            </Link>
          )}
          {author.data?.full_name && <p>Người đăng: {author.data.full_name}</p>}
        </article>
        <aside className="panel live-stack">
          {post.status === 'CLOSED' ? (
            <h2>Tin đã đóng</h2>
          ) : (
            <h2>{owner ? 'Quản lý tin' : 'Bạn nhận ra món đồ này?'}</h2>
          )}
          {post.status === 'OPEN' && owner && (
            <>
              <Link to={`/tin-cua-toi/${post.id}/sua`} className="button button-primary">
                Sửa tin
              </Link>
              <Link to={`/goi-y?tin=${post.id}`} className="button button-secondary">
                Xem gợi ý tương ứng
              </Link>
            </>
          )}
          {post.status === 'OPEN' && !owner && post.type === 'FOUND' && (
            <Link className="button button-primary" to={`/yeu-cau/moi?tin=${post.id}`}>
              Đây là đồ của tôi
            </Link>
          )}
          {!owner &&
            (token ? (
              <ReportForm postId={post.id} />
            ) : (
              <Link className="text-link" to="/dang-nhap" state={{ from: location.pathname }}>
                Đăng nhập để báo cáo tin
              </Link>
            ))}
          <SafetyNote />
        </aside>
      </div>
      {post.status === 'OPEN' && <SuggestedMatches id={post.id} />}
    </div>
  )
}

function DetailPhoto({ src, alt }: { src: string; alt: string }) {
  const [failed, setFailed] = useState(false)
  return failed ? (
    <div className="post-photo-empty">
      <Box size={48} aria-hidden="true" />
      <span>Không tải được ảnh</span>
    </div>
  ) : (
    <img src={src} alt={alt} loading="lazy" onError={() => setFailed(true)} />
  )
}

function ReportForm({ postId }: { postId: string }) {
  const report = useMutation({
    mutationFn: (reason: string) => moderationApi.report(postId, reason),
  })
  return (
    <details>
      <summary>Báo cáo vi phạm</summary>
      {report.isSuccess ? (
        <p role="status">Đã gửi báo cáo.</p>
      ) : (
        <form
          className="live-stack"
          onSubmit={(event) => {
            event.preventDefault()
            const reason = String(new FormData(event.currentTarget).get('reason')).trim()
            if (reason.length >= 3) report.mutate(reason)
          }}
        >
          <label className="field">
            Lý do báo cáo
            <textarea name="reason" required minLength={3} maxLength={2000} rows={3} />
          </label>
          <ApiFeedback error={report.error} />
          <button className="button button-secondary" type="submit" disabled={report.isPending}>
            Gửi báo cáo
          </button>
        </form>
      )}
    </details>
  )
}

export function CreatePostPage() {
  const { id } = useParams()
  const { actorId } = useSession()
  const [search] = useSearchParams()
  const catalog = useQuery({
    queryKey: ['categories'],
    queryFn: ({ signal }) => postsApi.categories(signal),
  })
  const existing = useQuery({
    queryKey: ['posts', 'detail', id],
    enabled: Boolean(id),
    queryFn: ({ signal }) => postsApi.detail(id!, signal),
  })
  const editable = !id || (existing.data?.user_id === actorId && existing.data?.status === 'OPEN')
  return (
    <div className="container page-container narrow">
      <PageHeading
        title={id ? 'Sửa tin' : 'Đăng tin'}
        description="Chỉ đưa thông tin công khai cần thiết để nhận biết món đồ."
      />
      <ApiFeedback
        pending={catalog.isPending || (Boolean(id) && existing.isPending)}
        error={catalog.error ?? existing.error}
      />
      {id && existing.data && !editable && (
        <EmptyState title="Tin này không thể sửa">
          Chỉ tin đang mở của bạn mới có thể sửa.
        </EmptyState>
      )}
      {catalog.data && editable && (
        <PostEditor
          key={id || search.get('loai') || 'new'}
          categories={catalog.data}
          post={existing.data}
          initialType={search.get('loai') === 'found' ? 'FOUND' : 'LOST'}
        />
      )}
    </div>
  )
}

function PostEditor({
  categories,
  post,
  initialType,
}: {
  categories: Category[]
  post?: Post
  initialType: PostType
}) {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const editor = useRef<HTMLFormElement>(null)
  const [type, setType] = useState(post?.type ?? initialType)
  const [locationCode, setLocationCode] = useState(post?.location_code ?? 'OTHER')
  const [pin, setPin] = useState<HotspotPin | null | 'choosing'>()
  const [categoryId, setCategoryId] = useState(post?.category_id ?? '')
  const [customName, setCustomName] = useState(post?.item_name ?? '')
  const otherCategory = categories.find((category) => category.name === 'Khác')
  const isOtherCategory = otherCategory?.id === categoryId
  const [files, setFiles] = useState<File[]>([])
  const [fileSelection, setFileSelection] = useState(0)
  const [savedId, setSavedId] = useState<string | null>(null)
  const [fileError, setFileError] = useState('')
  const limit = 5 - (post?.images.length ?? 0)
  const save = useMutation({
    mutationFn: async ({ body, type }: { body: PostInput; type: PostType }) => {
      const id =
        savedId ??
        (post
          ? (await postsApi.update(post.id, body)).id
          : (await postsApi.create({ ...body, type })).id)
      setSavedId(id)
      void queryClient.invalidateQueries({ queryKey: ['posts'] })
      void queryClient.invalidateQueries({ queryKey: ['hotspots'] })
      const remaining = [...files]
      try {
        while (remaining.length > 0) {
          await postsApi.upload(id, remaining[0])
          remaining.shift()
        }
      } finally {
        setFiles(remaining)
        void queryClient.invalidateQueries({ queryKey: ['posts'] })
      }
      return id
    },
    onSuccess: (id) => navigate(`/do-vat/${id}`, { replace: true }),
  })
  function applyDraft(draft: Draft) {
    if (draft.category_id) setCategoryId(draft.category_id)
    const values = {
      title: draft.title.trim(),
      description: draft.description.trim(),
      color_code: draft.color,
    }
    for (const [name, value] of Object.entries(values)) {
      const field = editor.current?.elements.namedItem(name)
      if (
        value &&
        (field instanceof HTMLInputElement ||
          field instanceof HTMLTextAreaElement ||
          field instanceof HTMLSelectElement)
      ) {
        field.value = value
      }
    }
  }
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (save.isPending || fileError || (type === 'LOST' && pin === 'choosing')) return
    const form = new FormData(event.currentTarget)
    const value = (key: string) => String(form.get(key) ?? '').trim()
    const itemName = isOtherCategory ? value('item_name') : ''
    const pinChange =
      type === 'LOST' && pin !== 'choosing'
        ? pin === null
          ? { hotspot_zone: null, latitude: null, longitude: null }
          : pin
        : undefined
    const body: PostInput = {
      title: value('title'),
      category_id: value('category_id'),
      ...(itemName || post?.item_name ? { item_name: itemName || null } : {}),
      ...pinChange,
      location: value('location'),
      location_code: value('location_code'),
      description: value('description'),
      event_time: value('event_time') ? new Date(value('event_time')).toISOString() : '',
      color_code: value('color_code') || null,
      brand: value('brand') || null,
      material: value('material') || null,
    }
    save.mutate({ body, type })
  }
  return (
    <form className="panel live-stack" onSubmit={submit} ref={editor}>
      <fieldset className="live-fields" disabled={save.isPending || Boolean(savedId)}>
        {!post && (
          <label className="field">
            Loại tin
            <select
              name="type"
              value={type}
              onChange={(event) => {
                setType(event.currentTarget.value === 'FOUND' ? 'FOUND' : 'LOST')
                setPin(undefined)
              }}
            >
              <option value="LOST">Tôi bị mất đồ</option>
              <option value="FOUND">Tôi nhặt được đồ</option>
            </select>
          </label>
        )}
        <label className="field">
          Tiêu đề
          <input name="title" required maxLength={255} defaultValue={post?.title ?? ''} />
        </label>
        <label className="field">
          Danh mục
          <select
            name="category_id"
            required
            value={categoryId}
            onChange={(event) => setCategoryId(event.currentTarget.value)}
          >
            <option value="">Chọn danh mục</option>
            {categories.map((category) => (
              <option key={category.id} value={category.id}>
                {category.name}
              </option>
            ))}
          </select>
        </label>
        {isOtherCategory && (
          <label className="field">
            Tên đồ vật (không bắt buộc)
            <input
              name="item_name"
              maxLength={100}
              placeholder="Ví dụ: Vợt cầu lông"
              value={customName}
              onChange={(event) => setCustomName(event.currentTarget.value)}
            />
          </label>
        )}
        <label className="field">
          Khu vực
          <select
            name="location_code"
            value={locationCode}
            onChange={(event) => setLocationCode(event.currentTarget.value)}
          >
            {locations.map(([code, name]) => (
              <option key={code} value={code}>
                {name}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          Địa điểm
          <input name="location" required maxLength={255} defaultValue={post?.location ?? ''} />
        </label>
        {type === 'LOST' && (
          <HotspotPinEditor postId={post?.id} region={locationCode} onChange={setPin} />
        )}
        <label className="field">
          Thời điểm mất hoặc nhặt được
          <input
            name="event_time"
            required
            type="datetime-local"
            defaultValue={localDateTime(post?.event_time)}
          />
        </label>
        <label className="field">
          Mô tả công khai
          <textarea
            name="description"
            required
            maxLength={10000}
            rows={5}
            defaultValue={post?.description ?? ''}
          />
        </label>
        <label className="field">
          Màu sắc
          <select name="color_code" defaultValue={post?.color_code ?? ''}>
            <option value="">Chọn màu sắc</option>
            {colors.map(([code, name]) => (
              <option key={code} value={code}>
                {name}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          Nhãn hiệu
          <input name="brand" maxLength={100} defaultValue={post?.brand ?? ''} />
        </label>
        <label className="field">
          Chất liệu
          <input name="material" maxLength={100} defaultValue={post?.material ?? ''} />
        </label>
      </fieldset>
      {!savedId && limit > 0 && (
        <label className="field">
          Thêm ảnh
          <input
            type="file"
            accept={imageTypes.join(',')}
            multiple
            disabled={save.isPending}
            onChange={(event) => {
              const selected = Array.from(event.target.files ?? [])
              const invalid =
                selected.length > limit ||
                selected.some((file) => !imageTypes.includes(file.type) || file.size > maxImageSize)
              setFiles(invalid ? [] : selected)
              setFileSelection((previous) => previous + 1)
              setFileError(
                invalid
                  ? `Chọn tối đa ${limit} ảnh JPEG, PNG hoặc WebP, mỗi ảnh tối đa 5 MiB.`
                  : '',
              )
            }}
          />
        </label>
      )}
      {!post && !savedId && files[0] && (
        <PostDraftAssistant
          key={fileSelection}
          file={files[0]}
          categories={categories}
          colors={colors}
          disabled={save.isPending}
          apply={applyDraft}
        />
      )}
      {savedId && !save.isPending && (
        <p role="status">
          Tin đã được lưu. {files.length > 0 && 'Bạn có thể thử tải lại các ảnh còn lại.'}{' '}
          <Link className="text-link" to={`/do-vat/${savedId}`}>
            Mở tin
          </Link>
        </p>
      )}
      {fileError && (
        <p className="error-state" role="alert">
          {fileError}
        </p>
      )}
      <ApiFeedback error={save.error} />
      <div className="live-actions">
        <button
          className="button button-primary"
          disabled={save.isPending || Boolean(fileError) || (type === 'LOST' && pin === 'choosing')}
          type="submit"
        >
          {save.isPending
            ? 'Đang lưu…'
            : savedId
              ? 'Thử lại tải ảnh'
              : post
                ? 'Lưu thay đổi'
                : 'Đăng tin'}
        </button>
      </div>
    </form>
  )
}
