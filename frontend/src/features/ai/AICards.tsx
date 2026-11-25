import { useState, type ReactNode } from 'react'
import { Box } from 'lucide-react'
import { Link } from 'react-router-dom'
import { formatDate } from '../../components/ui/live-format'
import { apiAssetUrl } from '../../lib/api/client'
import type { AIItem } from './api'
import './ai.css'

export function AICard({
  item,
  children,
  select,
  onNavigate,
}: {
  item: AIItem
  children?: ReactNode
  select?: () => void
  onNavigate?: () => void
}) {
  return (
    <article className="ai-card">
      <AIPhoto key={item.image_url} src={item.image_url} />
      <div className="ai-card-details">
        <strong>{item.title || 'Tin về đồ vật'}</strong>
        <span>
          {item.type === 'FOUND' ? 'Nhặt được' : 'Thất lạc'}
          {item.location ? ` · ${item.location}` : ''}
        </span>
        {item.event_time && <span>{formatDate(item.event_time)}</span>}
        {children}
        <Link className="text-link" to={`/do-vat/${item.item_id}`} onClick={onNavigate}>
          Xem chi tiết
        </Link>
        {select && (
          <button type="button" className="button button-secondary ai-select" onClick={select}>
            Tìm gợi ý cho tin này
          </button>
        )}
      </div>
    </article>
  )
}

function AIPhoto({ src }: { src: string | null }) {
  const [failed, setFailed] = useState(false)
  return src && !failed ? (
    <img src={apiAssetUrl(src)} alt="" loading="lazy" onError={() => setFailed(true)} />
  ) : (
    <div className="ai-card-placeholder">
      <Box size={24} aria-hidden="true" />
    </div>
  )
}
