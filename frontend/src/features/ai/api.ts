import { apiRequest } from '../../lib/api/client'
import type { PostType } from '../../lib/api/system'

export interface AIItem {
  item_id: string
  type: PostType
  title: string | null
  location: string | null
  event_time: string | null
  image_url: string | null
}

export interface AIMatch extends AIItem {
  matched_item_id: string
  similarity_score: number
  matching_reasons: string[]
}

export interface ImageMatch extends AIItem {
  image_similarity: number
  same_item_type?: boolean
}

export interface Draft {
  title: string
  category: string | null
  category_id: string | null
  color: string | null
  description: string
  confidence_note: string
}

export type ChatAction = 'create_lost' | 'create_found' | 'explore' | 'guide'

export interface ChatReview {
  topic: 'why' | 'location' | 'time' | 'description'
  number: number
}

export interface ChatCompare {
  first: number
  second: number
}

export interface ChatMap {
  destination: string
  origin?: string | null
}

export interface ChatReply {
  reply: string
  conversation_id: string
  related_items: (AIItem & { reasons?: string[]; result_number?: number | null })[]
  action: ChatAction | null
  can_select_item: boolean
  can_review_items?: boolean
  map_place?: ChatMap | null
}

export const aiApi = {
  matches: (id: string) =>
    apiRequest<{
      matches: AIMatch[]
      indexing_pending: boolean
      matching_mode?: 'semantic' | 'details'
    }>(`/api/ai/matches/${id}`, { auth: false }),
  images: (source: File | string, type: PostType | '', category: string, itemKind?: string) => {
    const body = new FormData()
    if (typeof source === 'string') body.set('image_id', source)
    else body.set('file', source)
    if (type) body.set('type', type)
    if (category) body.set('category_id', category)
    if (itemKind) body.set('item_kind', itemKind)
    return apiRequest<{
      results: ImageMatch[]
      type_results?: AIItem[]
      indexing_pending: boolean
      detected_item_type?: string | null
    }>('/api/ai/image-search', {
      method: 'POST',
      body,
      auth: false,
      timeoutMs: 75_000,
    })
  },
  draft: (file: File) => {
    const body = new FormData()
    body.set('file', file)
    return apiRequest<Draft>('/api/ai/generate-post', { method: 'POST', body })
  },
  chat: (
    message: string,
    conversation_id: string | null,
    selected_item_id?: string,
    review?: ChatReview,
    compare?: ChatCompare,
  ) =>
    apiRequest<ChatReply>('/api/ai/chat', {
      method: 'POST',
      body: { message, conversation_id, selected_item_id, review, compare },
    }),
  chatImage: (file: File, conversation: string | null) => {
    const body = new FormData()
    body.set('file', file)
    if (conversation) body.set('conversation_id', conversation)
    return apiRequest<ChatReply>('/api/ai/chat/image-search', {
      method: 'POST',
      body,
      timeoutMs: 75_000,
    })
  },
}
