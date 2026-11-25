import { clearSession, getSessionSnapshot } from './session-store'
import type { ErrorDetail } from './types'

const messages: Record<string, string> = {
  UNAUTHENTICATED: 'Phiên đăng nhập không hợp lệ hoặc đã hết hạn. Vui lòng kết nối lại.',
  ACCOUNT_FORBIDDEN: 'Tài khoản này hiện không được phép truy cập yêu cầu nhận đồ.',
  POST_NOT_FOUND: 'Không tìm thấy tin hoặc bạn không có quyền truy cập tin này.',
  POST_TYPE_NOT_FOUND: 'Chỉ có thể gửi yêu cầu nhận đồ cho tin nhặt được.',
  SELF_CLAIM_FORBIDDEN: 'Bạn không thể gửi yêu cầu nhận đồ cho tin của chính mình.',
  DUPLICATE_ACTIVE_CLAIM: 'Bạn đã có một yêu cầu đang xử lý cho tin này.',
  POST_ALREADY_ASSIGNED: 'Đồ vật đã được xác nhận cho một yêu cầu khác.',
  POST_NOT_CLAIMABLE: 'Tin này hiện không nhận thêm yêu cầu nhận đồ.',
  CLAIM_NOT_FOUND: 'Không tìm thấy yêu cầu hoặc bạn không có quyền xem yêu cầu này.',
  CLAIM_ACTION_FORBIDDEN: 'Bạn không có quyền thực hiện thao tác này.',
  CLAIM_STATE_CONFLICT: 'Trạng thái yêu cầu đã thay đổi. Vui lòng tải lại trước khi tiếp tục.',
  CLAIM_VERSION_CONFLICT: 'Yêu cầu vừa được cập nhật. Vui lòng tải lại để xem phiên bản mới nhất.',
  EVIDENCE_REQUIRED: 'Yêu cầu cần có bằng chứng sở hữu hợp lệ trước khi được chấp nhận.',
  RETURN_NOT_READY: 'Chưa có xác nhận bàn giao hợp lệ. Bạn chưa thể xác nhận đã nhận đồ.',
  VALIDATION_ERROR: 'Thông tin chưa hợp lệ. Vui lòng kiểm tra các trường được đánh dấu.',
  INTERNAL_ERROR: 'Máy chủ chưa thể xử lý yêu cầu. Vui lòng thử lại sau.',
  HTTP_ERROR: 'Yêu cầu hiện không khả dụng. Vui lòng kiểm tra kết nối và thử lại.',
  NETWORK_ERROR: 'Không kết nối được với máy chủ. Vui lòng kiểm tra kết nối và thử lại.',
  REQUEST_TIMEOUT: 'Máy chủ phản hồi quá chậm. Vui lòng thử lại.',
  INVALID_RESPONSE: 'Máy chủ trả về dữ liệu không hợp lệ. Vui lòng thử lại sau.',
  INVALID_CREDENTIALS: 'Email hoặc mật khẩu chưa đúng.',
  EMAIL_ALREADY_REGISTERED: 'Email này đã được đăng ký.',
  POST_OWNER_REQUIRED: 'Chỉ chủ tin mới có thể thực hiện thao tác này.',
  POST_STATE_CONFLICT: 'Trạng thái hiện tại của tin không cho phép thao tác này.',
  POST_HAS_ACTIVE_CLAIM: 'Tin đang có yêu cầu nhận đồ nên chưa thể sửa hoặc xóa.',
  POST_HAS_ACTIVE_RETURN: 'Tin đang có phiên trao trả cần hoàn tất.',
  INVALID_IMAGE: 'Vui lòng chọn ảnh PNG, JPEG hoặc WebP hợp lệ.',
  IMAGE_TOO_LARGE: 'Ảnh phải có dung lượng không quá 5 MiB.',
  IMAGE_LIMIT: 'Mỗi tin có thể lưu tối đa 5 ảnh.',
  IMAGE_NOT_FOUND: 'Không tìm thấy ảnh bài đăng.',
  EMPTY_IMAGE: 'Tệp ảnh trống. Hãy chọn ảnh khác.',
  AI_IMAGE_REQUIRED: 'Hãy chọn một ảnh để tìm đồ tương tự.',
  AI_MESSAGE_TOO_LARGE: 'Tin nhắn vượt quá độ dài cho phép.',
  AI_DISABLED: 'Tính năng AI này đang tắt.',
  AI_NOT_CONFIGURED: 'Tính năng này cần cấu hình OpenAI trên máy chủ.',
  AI_TIMEOUT: 'OpenAI phản hồi chậm. Vui lòng thử lại.',
  AI_PROVIDER_ERROR: 'Không nhận được phản hồi từ OpenAI. Vui lòng thử lại.',
  AI_INVALID_OUTPUT: 'AI trả về kết quả chưa hợp lệ. Vui lòng thử lại.',
  AI_RATE_LIMIT: 'Đã đạt giới hạn yêu cầu AI. Vui lòng thử lại sau.',
  AI_BUSY: 'AI đang xử lý yêu cầu khác. Vui lòng thử lại sau.',
  AI_MODEL_UNAVAILABLE: 'Mô hình AI local chưa sẵn sàng. Hãy kiểm tra bộ cài và tệp mô hình.',
  AI_CONVERSATION_NOT_FOUND: 'Phiên trò chuyện đã hết hạn. Hãy bắt đầu cuộc trò chuyện mới.',
  MATCHES_NOT_READY: 'Chưa có gợi ý mới nhất. Hãy tính lại gợi ý cho tin này.',
  POST_NOT_MATCHABLE: 'Tin này hiện chưa đủ điều kiện để tính gợi ý.',
  DUPLICATE_OPEN_REPORT: 'Bạn đã gửi một báo cáo đang xử lý cho tin này.',
  ADMIN_REQUIRED: 'Bạn cần quyền quản trị để truy cập.',
  EVIDENCE_FILE_NOT_FOUND: 'Bằng chứng này không có ảnh để tải.',
  RETURN_STATE_CONFLICT: 'Phiên trao trả đã thay đổi. Vui lòng tải lại.',
}

export class ApiError extends Error {
  readonly status: number
  readonly code: string
  readonly requestId: string | null
  readonly details: ErrorDetail[]

  constructor(
    status: number,
    code: string,
    requestId: string | null = null,
    details: ErrorDetail[] = [],
  ) {
    super(messages[code] ?? 'Đã xảy ra lỗi khi xử lý yêu cầu. Vui lòng thử lại.')
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.requestId = requestId
    this.details = details
  }
}

interface RequestOptions {
  method?: 'GET' | 'POST' | 'PATCH' | 'DELETE'
  body?: unknown
  signal?: AbortSignal
  timeoutMs?: number
  /** Used only while validating a user-supplied development token. */
  token?: string
  auth?: boolean
  response?: 'blob'
}

const baseUrl = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '')
export const apiAssetUrl = (path: string) => `${baseUrl}${path}`

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}

function hasTimedOut(signal?: AbortSignal) {
  return signal?.aborted && isRecord(signal.reason) && signal.reason.name === 'TimeoutError'
}

export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const token = options.auth === false ? null : (options.token ?? getSessionSnapshot().token)
  const headers: Record<string, string> = {
    Accept: options.response === 'blob' ? '*/*' : 'application/json',
  }
  const form = options.body instanceof FormData ? options.body : null
  if (token) headers.Authorization = `Bearer ${token}`
  if (options.body !== undefined && !form) headers['Content-Type'] = 'application/json'
  const deadline =
    options.timeoutMs === undefined ? undefined : AbortSignal.timeout(options.timeoutMs)
  const signal =
    deadline && options.signal
      ? AbortSignal.any([options.signal, deadline])
      : (deadline ?? options.signal)
  let response: Response
  try {
    response = await fetch(`${baseUrl}${path}`, {
      method: options.method ?? 'GET',
      headers,
      body: form ?? (options.body === undefined ? undefined : JSON.stringify(options.body)),
      signal,
      cache: 'no-store',
      credentials: 'omit',
      redirect: 'error',
    })
  } catch (error) {
    if (hasTimedOut(signal)) throw new ApiError(0, 'REQUEST_TIMEOUT')
    if (signal?.aborted || (isRecord(error) && error.name === 'AbortError')) throw error
    throw new ApiError(0, 'NETWORK_ERROR')
  }

  if (response.status === 401 && token && options.token === undefined) clearSession(true, token)
  if (response.status === 204) return undefined as T
  if (response.ok && options.response === 'blob') return (await response.blob()) as T
  let payload: unknown
  try {
    payload = await response.json()
  } catch {
    if (hasTimedOut(signal)) throw new ApiError(0, 'REQUEST_TIMEOUT')
    throw new ApiError(response.status, response.ok ? 'INVALID_RESPONSE' : 'HTTP_ERROR')
  }
  if (!response.ok) {
    const error = isRecord(payload) && isRecord(payload.error) ? payload.error : null
    const details = Array.isArray(error?.details)
      ? error.details.filter(
          (detail): detail is ErrorDetail =>
            isRecord(detail) &&
            typeof detail.field === 'string' &&
            typeof detail.issue === 'string',
        )
      : []
    throw new ApiError(
      response.status,
      typeof error?.code === 'string' ? error.code : 'HTTP_ERROR',
      typeof error?.request_id === 'string'
        ? error.request_id
        : response.headers.get('X-Request-ID'),
      details,
    )
  }
  return payload as T
}
