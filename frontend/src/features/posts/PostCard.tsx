import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Box, MapPin } from 'lucide-react'
import { formatDate } from '../../components/ui/live-format'
import { postsApi, type Post, type PostType } from '../../lib/api/system'
import { apiAssetUrl } from '../../lib/api/client'

export function PostCard({
  id,
  type,
  title,
  location,
  category,
  time,
}: {
  id: string
  type: PostType
  title: string | null
  location: string | null
  category?: string
  time: string | null
}) {
  const detail = useQuery({
    queryKey: ['posts', 'detail', id],
    queryFn: ({ signal }) => postsApi.detail(id, signal),
  })
  const photos = detail.data?.images ?? []
  const postLocation = detail.data?.location ?? location
  return (
    <Link to={`/do-vat/${id}`} className="item-card">
      <div className={`item-card-image post-card-art ${type === 'FOUND' ? 'art-keys' : 'art-bag'}`}>
        <CardPhoto key={photos[0]?.id} photos={photos} />
        <span className={`item-type ${type === 'FOUND' ? 'found' : 'lost'}`}>
          {type === 'FOUND' ? 'Nhặt được' : 'Tìm đồ thất lạc'}
        </span>
      </div>
      <div className="item-card-body">
        {category && <span className="item-category">{category}</span>}
        <h3>{title || 'Tin về đồ vật'}</h3>
        <div className="item-meta">
          {postLocation && (
            <span>
              <MapPin size={14} aria-hidden="true" />
              {postLocation}
            </span>
          )}
          <span>{formatDate(time)}</span>
        </div>
      </div>
    </Link>
  )
}

function PhotoPlaceholder() {
  return <Box size={45} strokeWidth={1.1} aria-hidden="true" />
}

function CardPhoto({ photos }: { photos: Post['images'] }) {
  const [index, setIndex] = useState(0)
  const photo = photos[index]
  return !photo ? (
    <PhotoPlaceholder />
  ) : (
    <img
      key={photo.id}
      className="post-card-photo"
      src={apiAssetUrl(photo.file_path)}
      alt=""
      loading="lazy"
      onError={() => setIndex(index + 1)}
    />
  )
}
