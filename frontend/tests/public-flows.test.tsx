import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { App } from '../src/app/App'
import { SessionProvider } from '../src/features/auth/session'
import { clearSession, setSession } from '../src/lib/api/session-store'

const postId = '11111111-1111-4111-8111-111111111111'
const actorId = '22222222-2222-4222-8222-222222222222'
const category = { id: '33333333-3333-4333-8333-333333333333', name: 'Ví và túi xách' }
const otherCategory = { id: '44444444-4444-4444-8444-444444444444', name: 'Khác' }
const item = {
  id: postId,
  type: 'FOUND',
  title: 'Ví xanh',
  category,
  location: { code: 'VN-HN', name: 'Hà Nội' },
  event_time: '2026-11-17T08:00:00Z',
  status: 'OPEN',
}
const user = {
  id: actorId,
  full_name: 'Bạn thử',
  email: 'user@example.com',
  phone: null,
  avatar_url: null,
  role: 'USER',
}
const request = vi.fn()
let cache: QueryClient
let postImages: { id: string; file_path: string }[]

function setup(path: string) {
  cache = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={cache}>
      <SessionProvider>
        <MemoryRouter initialEntries={[path]}>
          <App />
        </MemoryRouter>
      </SessionProvider>
    </QueryClientProvider>,
  )
  return userEvent.setup()
}

beforeEach(() => {
  clearSession()
  postImages = []
  request.mockReset()
  request.mockImplementation(async (path: string) => {
    if (path === '/api/v1/categories') return Response.json([category, otherCategory])
    if (path.startsWith('/api/v1/search?'))
      return Response.json({ items: [item], pagination: { total: 1, page: 1, total_pages: 1 } })
    if (path === `/api/v1/posts/${postId}`)
      return Response.json({
        ...item,
        location: item.location.name,
        images: postImages,
        user_id: actorId,
        description: 'Mô tả công khai của tin',
      })
    if (path === `/api/v1/users/${actorId}`)
      return Response.json({ id: actorId, full_name: user.full_name, avatar_url: null })
    if (path === '/api/v1/users/me') return Response.json(user)
    throw new Error(`Unexpected request ${path}`)
  })
  vi.stubGlobal('fetch', request)
  vi.spyOn(window, 'scrollTo').mockImplementation(() => undefined)
})

afterEach(() => {
  cache.clear()
  clearSession()
  vi.unstubAllGlobals()
})

describe('live public and protected screens', () => {
  it('loads categories and routes filters through the server', async () => {
    const ui = setup('/kham-pha')
    expect(await screen.findByRole('link', { name: /Ví xanh/ })).toBeVisible()
    await ui.selectOptions(screen.getByRole('combobox', { name: 'Danh mục' }), category.id)
    await ui.selectOptions(screen.getByRole('combobox', { name: 'Khu vực' }), 'VN-HN')
    await ui.selectOptions(screen.getByRole('combobox', { name: 'Loại tin' }), 'found')
    await waitFor(() => {
      const searchRequests = request.mock.calls.filter(([path]) =>
        path.startsWith('/api/v1/search?'),
      )
      const [url] = searchRequests.at(-1) ?? []
      expect(url).toContain(`category_id=${category.id}`)
      expect(url).toContain('location_code=VN-HN')
      expect(url).toContain('type=FOUND')
    })
  })

  it('renders the backend empty state with no sample cards', async () => {
    request.mockImplementation(async (path: string) =>
      Response.json(
        path === '/api/v1/categories'
          ? [category]
          : { items: [], pagination: { total: 0, page: 1, total_pages: 0 } },
      ),
    )
    setup('/kham-pha?minh-hoa=1')
    expect(
      await screen.findByRole('heading', { name: 'Chưa tìm thấy món đồ phù hợp' }),
    ).toBeVisible()
    expect(screen.queryByRole('link', { name: /Ví xanh/ })).not.toBeInTheDocument()
  })

  it('shows an available cover when the first image fails to load', async () => {
    postImages = ['old', 'new'].map((id) => ({
      id,
      file_path: `/api/v1/posts/${postId}/images/${id}`,
    }))
    const ui = setup('/kham-pha')
    const card = await screen.findByRole('link', { name: /Ví xanh/ })
    await waitFor(() =>
      expect(card.querySelector('img')).toHaveAttribute('src', postImages[0].file_path),
    )
    fireEvent.error(card.querySelector('img')!)
    expect(card.querySelector('img')).toHaveAttribute('src', postImages[1].file_path)

    await ui.click(card)
    fireEvent.error(await screen.findByRole('img', { name: 'Ảnh 1 của Ví xanh' }))
    expect(screen.getByText('Không tải được ảnh')).toBeVisible()
    expect(screen.getByRole('img', { name: 'Ảnh 2 của Ví xanh' })).toBeVisible()
  })

  it('redirects a guest from claiming a found post to sign-in', async () => {
    const ui = setup(`/do-vat/${postId}`)
    await ui.click(await screen.findByRole('link', { name: 'Đây là đồ của tôi' }))
    expect(await screen.findByRole('heading', { name: 'Chào mừng bạn trở lại' })).toBeVisible()
    expect(screen.getByRole('button', { name: 'Đăng nhập' })).toBeEnabled()
  })

  it('allows registered accounts to open the real posting form', async () => {
    setSession('account-test', actorId, Date.now() + 60000)
    setup('/dang-tin?loai=found')
    expect(await screen.findByRole('option', { name: category.name })).toBeInTheDocument()
    expect(screen.getByRole('combobox', { name: 'Loại tin' })).toHaveValue('FOUND')
    expect(screen.getByRole('main').querySelector('button[type=submit]')).toBeEnabled()
  })

  it('lets users enter a custom item name when posting in Khác', async () => {
    setSession('account-test', actorId, Date.now() + 60000)
    const ui = setup('/dang-tin?loai=found')
    const select = await screen.findByRole('combobox', { name: 'Danh mục' })
    expect(screen.queryByRole('textbox', { name: /Tên đồ vật/ })).not.toBeInTheDocument()
    await ui.selectOptions(select, otherCategory.id)
    const name = screen.getByRole('textbox', { name: /Tên đồ vật/ })
    await ui.type(name, 'Vợt cầu lông')
    await ui.selectOptions(select, category.id)
    expect(name).not.toBeInTheDocument()
    await ui.selectOptions(select, otherCategory.id)
    expect(screen.getByRole('textbox', { name: /Tên đồ vật/ })).toHaveValue('Vợt cầu lông')
  })

  it('sends a custom name and labels keyword matches separately from photos', async () => {
    const defaultRequest = request.getMockImplementation()!
    request.mockImplementation(async (path, config) => {
      if (path !== '/api/ai/image-search') return defaultRequest(path, config)
      expect(config.body.get('item_name')).toBe('Vợt cầu lông')
      expect(config.body.has('item_kind')).toBe(false)
      return Response.json({
        results: [],
        type_results: [{ ...item, item_id: postId, title: 'Nhặt được vợt' }],
        indexing_pending: false,
      })
    })
    const ui = setup('/kham-pha?anh=source-image')
    await ui.selectOptions(await screen.findByRole('combobox', { name: 'Loại đồ vật' }), 'custom')
    const search = screen.getByRole('button', { name: 'Tìm đồ tương tự' })
    expect(search).toBeDisabled()
    await ui.type(screen.getByRole('textbox', { name: 'Tên đồ vật' }), 'Vợt cầu lông')
    await ui.click(search)
    expect(await screen.findByRole('heading', { name: 'Tin khớp tên đồ vật' })).toBeVisible()
    expect(screen.getByText('Nhặt được vợt')).toBeVisible()
  })

  it('verifies the admin role through the account endpoint before requesting admin data', async () => {
    setSession('account-test', actorId, Date.now() + 60000)
    setup('/quan-tri')
    expect(
      await screen.findByRole('heading', { name: 'Bạn không có quyền quản trị' }),
    ).toBeVisible()
    expect(request.mock.calls.some(([url]) => url.startsWith('/api/v1/admin/'))).toBe(false)
  })
})
