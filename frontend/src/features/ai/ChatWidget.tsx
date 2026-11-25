import { useEffect, useRef, useState, type Dispatch, type SetStateAction } from 'react'
import * as Dialog from '@radix-ui/react-dialog'
import { ImagePlus, MapPin, MessageCircle, Send, X } from 'lucide-react'
import { useMutation } from '@tanstack/react-query'
import { Link, useLocation } from 'react-router-dom'
import { ApiFeedback } from '../../components/ui/live'
import { imageTypes, maxImageSize } from '../../components/ui/live-format'
import { useSession } from '../auth/session'
import { AICard } from './AICards'
import {
  aiApi,
  type ChatAction,
  type ChatCompare,
  type ChatMap,
  type ChatReply,
  type ChatReview,
} from './api'

const questions = [
  'Tôi đăng tin mất đồ thế nào?',
  'Tìm giúp tôi ví đen gần thư viện.',
  'Có gợi ý nào cho tin mất đồ của tôi?',
]
const actions: Record<ChatAction, [string, string]> = {
  create_lost: ['/dang-tin?loai=lost', 'Đăng tin mất đồ'],
  create_found: ['/dang-tin?loai=found', 'Đăng tin nhặt được đồ'],
  explore: ['/kham-pha', 'Mở trang khám phá'],
  guide: ['/huong-dan', 'Xem hướng dẫn'],
}

const followUps = [
  { topic: 'why', label: 'Vì sao phù hợp?', question: 'Vì sao tin số 1 phù hợp?' },
  { topic: 'location', label: 'Vị trí', question: 'Địa điểm của tin số 1 ở đâu?' },
  { topic: 'time', label: 'Thời gian', question: 'Tin số 1 ghi thời điểm nào?' },
] as const

function MapLink({ place }: { place: ChatMap }) {
  const params = new URLSearchParams({ api: '1' })
  if (place.origin) {
    params.set('origin', place.origin)
    params.set('destination', place.destination)
  } else {
    params.set('query', place.destination)
  }
  const path = place.origin ? 'dir' : 'search'
  return (
    <a
      className="button button-secondary ai-chat-map"
      href={`https://www.google.com/maps/${path}/?${params}`}
      target="_blank"
      rel="noreferrer"
    >
      <MapPin size={16} aria-hidden="true" />
      {place.origin ? 'Xem chỉ đường' : 'Xem bản đồ'}
    </a>
  )
}

export function ChatWidget() {
  const { token, actorId } = useSession()
  return <ChatWindow key={actorId ?? 'guest'} signedIn={Boolean(token)} />
}

type Turn = { question: string; answer: ChatReply }
type ChatOptions = {
  item?: string
  review?: ChatReview
  compare?: ChatCompare
  image?: File
  typed?: boolean
}

function ChatWindow({ signedIn }: { signedIn: boolean }) {
  const [open, setOpen] = useState(false)
  const [turns, setTurns] = useState<Turn[]>([])
  const location = useLocation()

  return (
    <Dialog.Root open={open} onOpenChange={setOpen}>
      <Dialog.Trigger className="ai-chat-trigger" aria-label="Mở FindBack AI Assistant">
        <MessageCircle size={24} aria-hidden="true" />
      </Dialog.Trigger>
      <Dialog.Portal>
        <Dialog.Overlay className="ai-chat-overlay" />
        <Dialog.Content className="ai-chat-dialog">
          <header>
            <Dialog.Title>FindBack AI Assistant</Dialog.Title>
            <Dialog.Close className="icon-button" aria-label="Đóng trợ lý">
              <X size={20} />
            </Dialog.Close>
          </header>
          <Dialog.Description className="ai-chat-description">
            {signedIn
              ? 'Mô tả món đồ, gửi ảnh hoặc hỏi về FindBack.'
              : 'Đăng nhập để hỏi trợ lý và xem gợi ý cho tin của bạn.'}
          </Dialog.Description>
          {signedIn ? (
            <ChatThread close={() => setOpen(false)} turns={turns} setTurns={setTurns} />
          ) : (
            <div className="ai-chat-guest">
              <Dialog.Close asChild>
                <Link
                  to="/dang-nhap"
                  state={{ from: location.pathname + location.search }}
                  className="button button-primary"
                >
                  Đăng nhập
                </Link>
              </Dialog.Close>
            </div>
          )}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}

function ChatThread({
  close,
  turns,
  setTurns,
}: {
  close: () => void
  turns: Turn[]
  setTurns: Dispatch<SetStateAction<Turn[]>>
}) {
  const [message, setMessage] = useState('')
  const [attachment, setAttachment] = useState<{ file: File; preview: string } | null>(null)
  const [attachmentError, setAttachmentError] = useState('')
  const log = useRef<HTMLDivElement>(null)
  const imageInput = useRef<HTMLInputElement>(null)
  const conversation = turns.at(-1)?.answer.conversation_id ?? null
  const send = useMutation({
    mutationFn: ({ text, item, review, compare, image }: { text: string } & ChatOptions) =>
      image
        ? aiApi.chatImage(image, conversation)
        : aiApi.chat(text, conversation, item, review, compare),
    onSuccess: (answer, { text, image, typed }) => {
      setTurns((previous) => [...previous, { question: text, answer }].slice(-20))
      if (typed) setMessage('')
      if (image) setAttachment(null)
    },
  })
  const preview = attachment?.preview
  useEffect(() => {
    if (preview) return () => URL.revokeObjectURL(preview)
  }, [preview])
  useEffect(() => {
    if (log.current) log.current.scrollTop = log.current.scrollHeight
  }, [turns, send.isPending, send.isError])

  function submit(text: string, options: ChatOptions = {}) {
    if (text.trim() && !send.isPending) send.mutate({ text: text.trim(), ...options })
  }

  return (
    <>
      <div className="ai-chat-log" ref={log} role="log" aria-label="Cuộc trò chuyện">
        {!turns.length && (
          <div className="ai-chat-questions">
            {questions.map((question) => (
              <button
                type="button"
                className="button button-secondary"
                key={question}
                disabled={send.isPending}
                onClick={() => submit(question)}
              >
                {question}
              </button>
            ))}
          </div>
        )}
        {turns.map(({ question, answer }, index) => (
          <div className="ai-chat-turn" key={index}>
            <p className="ai-chat-user">{question}</p>
            <p className="ai-chat-reply">{answer.reply}</p>
            {answer.map_place && <MapLink place={answer.map_place} />}
            {answer.related_items.map((item, itemIndex) => (
              <AICard
                key={item.item_id}
                item={item}
                onNavigate={close}
                select={
                  answer.can_select_item && !send.isPending
                    ? () =>
                        submit(`Xem gợi ý cho ${(item.title || 'tin này').slice(0, 240)}`, {
                          item: item.item_id,
                        })
                    : undefined
                }
              >
                {answer.related_items.length > 1 && (
                  <span>Tin số {item.result_number ?? itemIndex + 1}</span>
                )}
                {Boolean(item.reasons?.length) && (
                  <ul>
                    {item.reasons?.slice(0, 3).map((reason) => (
                      <li key={reason}>{reason}</li>
                    ))}
                  </ul>
                )}
              </AICard>
            ))}
            {answer.can_review_items && index === turns.length - 1 && (
              <div className="ai-chat-followups" aria-label="Hỏi tiếp về kết quả">
                {followUps
                  .filter(
                    (entry) =>
                      entry.topic !== 'why' || Boolean(answer.related_items[0]?.reasons?.length),
                  )
                  .map(({ topic, label, question }) => (
                    <button
                      key={topic}
                      type="button"
                      className="button button-secondary"
                      disabled={send.isPending}
                      onClick={() => submit(question, { review: { topic, number: 1 } })}
                    >
                      {answer.related_items.length > 1 ? `${label} · Tin 1` : label}
                    </button>
                  ))}
                {answer.related_items.length > 1 && (
                  <button
                    type="button"
                    className="button button-secondary"
                    disabled={send.isPending}
                    onClick={() =>
                      submit('So sánh hai tin đầu.', { compare: { first: 1, second: 2 } })
                    }
                  >
                    So sánh 2 tin đầu
                  </button>
                )}
              </div>
            )}
            {answer.action && (
              <Link className="text-link" to={actions[answer.action][0]} onClick={close}>
                {actions[answer.action][1]}
              </Link>
            )}
          </div>
        ))}
        {send.isPending && <p className="ai-chat-user">{send.variables?.text}</p>}
        <ApiFeedback pending={send.isPending} error={send.error} />
      </div>
      <form
        className="ai-chat-form"
        onSubmit={(event) => {
          event.preventDefault()
          submit(message, { typed: true })
        }}
      >
        <input
          type="file"
          ref={imageInput}
          aria-label="Ảnh để tìm đồ"
          accept={imageTypes.join(',')}
          hidden
          onChange={(event) => {
            const file = event.currentTarget.files?.[0]
            event.currentTarget.value = ''
            if (!file) return
            if (!imageTypes.includes(file.type) || file.size > maxImageSize) {
              setAttachmentError('Chọn ảnh JPG, PNG hoặc WebP tối đa 5 MB.')
              return
            }
            setAttachmentError('')
            setAttachment({ file, preview: URL.createObjectURL(file) })
          }}
        />
        {attachment && (
          <div className="ai-chat-attachment">
            <img src={attachment.preview} alt="Ảnh đã chọn" />
            <button
              type="button"
              className="button button-secondary"
              disabled={send.isPending}
              onClick={() => {
                setAttachmentError('')
                submit('Tìm đồ bằng ảnh', { image: attachment.file })
              }}
            >
              Tìm bằng ảnh
            </button>
            <button
              type="button"
              className="icon-button"
              aria-label="Bỏ ảnh đã chọn"
              disabled={send.isPending}
              onClick={() => {
                setAttachment(null)
                setAttachmentError('')
              }}
            >
              <X size={18} aria-hidden="true" />
            </button>
          </div>
        )}
        {attachmentError && (
          <p className="ai-chat-attachment-error" role="alert">
            {attachmentError}
          </p>
        )}
        <button
          type="button"
          className="button button-secondary ai-chat-attach"
          aria-label="Chọn ảnh để tìm đồ"
          title="Chọn ảnh để tìm đồ"
          disabled={send.isPending}
          onClick={() => imageInput.current?.click()}
        >
          <ImagePlus size={19} aria-hidden="true" />
        </button>
        <label className="field">
          <span className="sr-only">Tin nhắn</span>
          <input
            value={message}
            maxLength={500}
            placeholder="Hỏi về món đồ của bạn…"
            disabled={send.isPending}
            onChange={(event) => setMessage(event.target.value)}
          />
        </label>
        <button
          className="button button-primary"
          type="submit"
          aria-label="Gửi tin nhắn"
          disabled={!message.trim() || send.isPending}
        >
          <Send size={18} />
        </button>
      </form>
      <div className="ai-chat-meta">
        <small>Tin nhắn được xử lý qua OpenAI. Giữ riêng thông tin nhạy cảm.</small>
        {Boolean(turns.length) && (
          <button
            type="button"
            className="text-link"
            disabled={send.isPending}
            onClick={() => {
              send.reset()
              setTurns([])
              setMessage('')
              setAttachment(null)
              setAttachmentError('')
            }}
          >
            Cuộc trò chuyện mới
          </button>
        )}
      </div>
    </>
  )
}
