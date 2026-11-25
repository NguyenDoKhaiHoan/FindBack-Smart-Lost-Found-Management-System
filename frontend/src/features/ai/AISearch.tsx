import { useEffect, useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { ImagePlus, Sparkles } from 'lucide-react'
import { ApiFeedback } from '../../components/ui/live'
import { imageTypes, maxImageSize } from '../../components/ui/live-format'
import type { PostType } from '../../lib/api/system'
import { AICard } from './AICards'
import { aiApi } from './api'

export function SuggestedMatches({ id }: { id: string }) {
  const query = useQuery({
    queryKey: ['posts', 'ai-matches', id],
    queryFn: () => aiApi.matches(id),
    retry: false,
    staleTime: 60_000,
  })
  return (
    <section className="panel ai-section" aria-label="Đồ vật có thể trùng khớp">
      <h2>
        <Sparkles size={20} aria-hidden="true" /> Đồ vật có thể trùng khớp
      </h2>
      <p className="muted">Điểm tương đồng chỉ dùng để tham khảo khi tìm đồ.</p>
      <ApiFeedback
        pending={query.isPending}
        error={query.error}
        retry={() => void query.refetch()}
      />
      {query.data?.matching_mode === 'details' && (
        <p className="muted">Kết quả được đối chiếu theo từ khóa và thông tin tin đăng.</p>
      )}
      {query.data?.indexing_pending && (
        <p role="status">
          Đang cập nhật chỉ mục.{' '}
          <button
            type="button"
            className="text-link"
            disabled={query.isFetching}
            onClick={() => void query.refetch()}
          >
            Kiểm tra thêm tin
          </button>
        </p>
      )}
      {query.data && !query.data.indexing_pending && !query.data.matches.length && (
        <p>Chưa có tin phù hợp.</p>
      )}
      <div className="ai-card-grid">
        {query.data?.matches.map((match) => (
          <AICard key={match.item_id} item={match}>
            <strong className="ai-score">
              {Math.round(match.similarity_score * 100)}/100 tương đồng
            </strong>
            <ul>
              {match.matching_reasons.map((reason) => (
                <li key={reason}>{reason}</li>
              ))}
            </ul>
          </AICard>
        ))}
      </div>
    </section>
  )
}

interface ImageRequest {
  source: File | string
  type: PostType | ''
  category: string
}

export function ImageSearch({
  type,
  category,
  postImage,
}: {
  type: PostType | ''
  category: string
  postImage: string | null
}) {
  const [file, setFile] = useState<File | null>(null)
  const [preview, setPreview] = useState('')
  const [error, setError] = useState('')
  const search = useMutation({
    mutationFn: ({ source, type, category }: ImageRequest) => aiApi.images(source, type, category),
  })
  useEffect(() => {
    if (preview) return () => URL.revokeObjectURL(preview)
  }, [preview])
  const source = file || postImage
  const sameRequest =
    search.variables?.source === source &&
    search.variables.type === type &&
    search.variables.category === category
  const result = sameRequest ? search.data : undefined
  return (
    <details className="panel ai-section ai-image-search" open={postImage ? true : undefined}>
      <summary>
        <ImagePlus size={20} aria-hidden="true" /> Tìm đồ bằng hình ảnh
      </summary>
      <form
        className="ai-image-form"
        onSubmit={(event) => {
          event.preventDefault()
          if (source && !error && !search.isPending) search.mutate({ source, type, category })
        }}
      >
        <label className="field">
          Chọn ảnh JPEG, PNG hoặc WebP (tối đa 5 MiB)
          <input
            type="file"
            accept={imageTypes.join(',')}
            disabled={search.isPending}
            onChange={(event) => {
              const selected = event.currentTarget.files?.[0] ?? null
              const invalid =
                selected && (!imageTypes.includes(selected.type) || selected.size > maxImageSize)
              setFile(invalid ? null : selected)
              setPreview(selected && !invalid ? URL.createObjectURL(selected) : '')
              setError(invalid ? 'Chọn ảnh JPEG, PNG hoặc WebP hợp lệ, tối đa 5 MiB.' : '')
              search.reset()
            }}
          />
        </label>
        {file && preview && <img className="ai-preview" src={preview} alt="Ảnh dùng để tìm kiếm" />}
        {!file && postImage && <p>Đang dùng ảnh từ tin bạn vừa xem.</p>}
        {error && (
          <p role="alert" className="error-state">
            {error}
          </p>
        )}
        <button
          className="button button-secondary"
          type="submit"
          disabled={!source || !!error || search.isPending}
        >
          Tìm đồ tương tự
        </button>
      </form>
      <ApiFeedback pending={search.isPending} error={sameRequest ? search.error : null} />
      {result?.detected_item_type && (
        <p role="status">
          Loại đồ nhận diện được: <strong>{result.detected_item_type}</strong>
        </p>
      )}
      {result?.indexing_pending && (
        <p role="status">Đang cập nhật ảnh. Tìm lại để kiểm tra thêm ảnh.</p>
      )}
      {result && !result.indexing_pending && !result.results.length && (
        <p>Chưa thấy kết quả đủ gần. Hãy thử ảnh chụp rõ món đồ hoặc đổi bộ lọc.</p>
      )}
      <div className="ai-card-grid">
        {result?.results.map((item) => (
          <AICard key={item.item_id} item={item}>
            <strong className="ai-score">
              {item.image_similarity >= 0.92
                ? 'Ảnh rất giống'
                : item.same_item_type
                  ? 'Cùng loại đồ vật'
                  : 'Ảnh tương tự'}
            </strong>
          </AICard>
        ))}
      </div>
    </details>
  )
}
