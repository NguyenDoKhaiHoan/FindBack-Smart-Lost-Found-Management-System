export function formatDate(value: string | null | undefined) {
  return value
    ? new Date(value).toLocaleString('vi-VN', { dateStyle: 'medium', timeStyle: 'short' })
    : 'Chưa có thời gian'
}

export function localDateTime(value: string | null | undefined) {
  if (!value) return ''
  const date = new Date(value)
  return new Date(date.getTime() - date.getTimezoneOffset() * 60_000).toISOString().slice(0, 16)
}

export const imageTypes = ['image/jpeg', 'image/png', 'image/webp']
export const maxImageSize = 5 * 1024 * 1024
