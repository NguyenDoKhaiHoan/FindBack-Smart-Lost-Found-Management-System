import { ChevronLeft, ChevronRight } from 'lucide-react'
import { ApiError } from '../../lib/api'

export function ApiFeedback({
  pending,
  error,
  retry,
}: {
  pending?: boolean
  error?: Error | null
  retry?: () => void
}) {
  if (error)
    return (
      <div className="error-state" role="alert">
        <p>
          {error instanceof ApiError ? error.message : 'Không tải được dữ liệu. Vui lòng thử lại.'}
        </p>
        {retry && (
          <button className="text-link" type="button" onClick={retry}>
            Thử lại
          </button>
        )}
      </div>
    )
  return pending ? (
    <p className="muted" role="status">
      Đang tải…
    </p>
  ) : null
}

export function Pagination({
  page,
  pages,
  onPage,
}: {
  page: number
  pages: number
  onPage: (page: number) => void
}) {
  if (pages < 2 && page <= 1) return null
  return (
    <nav className="live-actions" aria-label="Phân trang">
      <button
        className="button button-secondary"
        type="button"
        disabled={page <= 1}
        onClick={() => onPage(page - 1)}
      >
        <ChevronLeft size={16} /> Trang trước
      </button>
      <span>
        Trang {page}
        {pages >= page ? ` / ${pages}` : ''}
      </span>
      <button
        className="button button-secondary"
        type="button"
        disabled={page >= pages}
        onClick={() => onPage(page + 1)}
      >
        Trang sau <ChevronRight size={16} />
      </button>
    </nav>
  )
}
