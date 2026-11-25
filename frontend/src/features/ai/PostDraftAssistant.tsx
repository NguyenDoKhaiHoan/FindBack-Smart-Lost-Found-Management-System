import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { Sparkles } from 'lucide-react'
import { ApiFeedback } from '../../components/ui/live'
import type { Category } from '../../lib/api/system'
import { aiApi, type Draft } from './api'
import './ai.css'

export function PostDraftAssistant({
  file,
  categories,
  colors,
  disabled,
  apply,
}: {
  file: File
  categories: Category[]
  colors: string[][]
  disabled: boolean
  apply: (draft: Draft) => void
}) {
  const [draft, setDraft] = useState<Draft | null>(null)
  const [applied, setApplied] = useState(false)
  const generate = useMutation({
    mutationFn: () => aiApi.draft(file),
    onSuccess: (data) => {
      setDraft(data)
      setApplied(false)
    },
  })

  return (
    <section className="ai-section ai-draft" aria-label="Bản nháp từ ảnh">
      <button
        type="button"
        className="button button-secondary"
        disabled={disabled || generate.isPending}
        onClick={() => generate.mutate()}
      >
        <Sparkles size={17} aria-hidden="true" /> Tạo mô tả bằng AI
      </button>
      <p className="muted">FindBack gửi ảnh đầu tiên bạn chọn đến OpenAI để tạo bản nháp.</p>
      <ApiFeedback pending={generate.isPending} error={generate.error} />
      {draft && (
        <fieldset className="live-fields" disabled={disabled || generate.isPending}>
          <legend>Bản nháp từ ảnh</legend>
          <p>{draft.confidence_note}</p>
          <label className="field">
            Tiêu đề gợi ý
            <input
              maxLength={255}
              value={draft.title}
              onKeyDown={(event) => {
                if (event.key === 'Enter') event.preventDefault()
              }}
              onChange={(event) => setDraft({ ...draft, title: event.target.value })}
            />
          </label>
          <label className="field">
            Danh mục gợi ý
            <select
              value={draft.category_id ?? ''}
              onChange={(event) => setDraft({ ...draft, category_id: event.target.value || null })}
            >
              <option value="">Bỏ qua danh mục</option>
              {categories.map((category) => (
                <option key={category.id} value={category.id}>
                  {category.name}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            Màu sắc gợi ý
            <select
              value={draft.color ?? ''}
              onChange={(event) => setDraft({ ...draft, color: event.target.value || null })}
            >
              <option value="">Bỏ qua màu sắc</option>
              {colors.map(([code, name]) => (
                <option key={code} value={code}>
                  {name}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            Mô tả gợi ý
            <textarea
              rows={4}
              maxLength={10000}
              value={draft.description}
              onChange={(event) => setDraft({ ...draft, description: event.target.value })}
            />
          </label>
          <button
            type="button"
            className="button button-secondary"
            onClick={() => {
              apply(draft)
              setApplied(true)
            }}
            disabled={!draft.title.trim() || !draft.description.trim()}
          >
            Áp dụng vào biểu mẫu
          </button>
          {applied && <p role="status">Đã điền bản nháp. Bạn có thể sửa tiếp trong biểu mẫu.</p>}
        </fieldset>
      )}
    </section>
  )
}
