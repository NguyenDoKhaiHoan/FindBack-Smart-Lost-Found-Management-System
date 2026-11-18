/* global process, console, setTimeout, clearTimeout, document, Buffer */
import assert from 'node:assert/strict'
import { spawn } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import path from 'node:path'
import { chromium, expect } from '@playwright/test'
import { createServer } from 'vite'

const frontend = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const backend = path.resolve(frontend, '../backend')
const python = path.join(
  backend,
  '.venv',
  process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python',
)
const live = spawn(python, [path.join(frontend, 'scripts/live-api-server.py')], {
  cwd: backend,
  windowsHide: true,
  stdio: ['pipe', 'pipe', 'pipe'],
})
const exited = new Promise((resolve) => live.once('exit', resolve))
live.stderr.on('data', () => undefined)
let server
let browser
const base = 'http://127.0.0.1:15174'
const foundTitle = 'Ví xanh E2E nhặt được'
const lostTitle = 'Ví xanh E2E thất lạc'
const claimText = 'Đường chỉ xanh ở mặt trong của ví'
const privatePhotoText = 'Ảnh chụp đường chỉ ở mặt trong'
const runtimeErrors = []

try {
  const fixtures = await new Promise((resolve, reject) => {
    let buffer = ''
    const timeout = setTimeout(() => reject(new Error('Disposable backend did not start')), 30_000)
    live.once('error', reject)
    live.once('exit', (code) => reject(new Error(`Disposable backend exited (${code})`)))
    live.stdout.on('data', (chunk) => {
      buffer += chunk
      const newline = buffer.indexOf('\n')
      if (newline === -1) return
      clearTimeout(timeout)
      try {
        resolve(JSON.parse(buffer.slice(0, newline)))
      } catch {
        reject(new Error('Unexpected disposable fixture output'))
      }
    })
  })
  server = await createServer({
    root: frontend,
    logLevel: 'error',
    define: {
      'import.meta.env.VITE_ENABLE_DEV_SESSION': '"true"',
      'import.meta.env.VITE_API_BASE_URL': '""',
    },
    server: {
      host: '127.0.0.1',
      port: 15174,
      strictPort: true,
      proxy: { '/api': { target: 'http://127.0.0.1:18000', changeOrigin: true } },
    },
  })
  await server.listen()
  browser = await chromium.launch({
    headless: true,
    ...(process.env.PLAYWRIGHT_CHANNEL
      ? { channel: process.env.PLAYWRIGHT_CHANNEL }
      : process.platform === 'win32'
        ? { channel: 'chrome' }
        : {}),
  })
  const newPage = async () => {
    const page = await browser.newPage({
      viewport: { width: 1440, height: 1000 },
      timezoneId: 'Asia/Bangkok',
    })
    page.on('pageerror', (error) => runtimeErrors.push(error.message))
    return page
  }
  const owner = await newPage()
  const claimant = await newPage()
  const admin = await newPage()
  const createAccount = async (page, email, name) => {
    await page.goto(`${base}/dang-ky`)
    await page.getByLabel('Họ và tên').fill(name)
    await page.getByLabel('Email').fill(email)
    await page.getByLabel('Mật khẩu').fill('FindBack!2026')
    await page.getByRole('button', { name: 'Tạo tài khoản' }).click()
    await expect(page.getByRole('heading', { name: `Xin chào, ${name}` })).toBeVisible()
  }
  await createAccount(owner, 'owner-e2e@example.com', 'Chủ tin kiểm thử')
  await createAccount(claimant, 'claimant-e2e@example.com', 'Người nhận kiểm thử')
  await owner.getByRole('link', { name: 'Hồ sơ cá nhân' }).click()
  await owner.getByLabel('Số điện thoại').fill('0900000001')
  await owner.getByRole('button', { name: 'Lưu thay đổi' }).click()
  await expect(owner.getByText('Đã cập nhật hồ sơ.')).toBeVisible()
  const canvas = await owner.evaluate(() => {
    const canvas = document.createElement('canvas')
    canvas.width = 8
    canvas.height = 8
    const ctx = canvas.getContext('2d')
    ctx.fillStyle = '#155b99'
    ctx.fillRect(0, 0, 8, 8)
    return canvas.toDataURL('image/png').split(',')[1]
  })
  const image = { name: 'wallet.png', mimeType: 'image/png', buffer: Buffer.from(canvas, 'base64') }

  async function postThroughUi(page, title, kind, withPhoto = false) {
    await page.locator('header').getByRole('link', { name: 'Đăng tin' }).click()
    await page.getByLabel('Loại tin').selectOption(kind)
    await page.getByLabel('Tiêu đề').fill(title)
    await page.getByLabel('Danh mục').selectOption({ label: 'Ví và túi xách' })
    await page.getByLabel('Khu vực').selectOption('VN-HN')
    await page.getByLabel('Địa điểm').fill('Cổng thư viện Hà Nội')
    await page.getByLabel('Thời điểm mất hoặc nhặt được').fill('2026-11-17T08:00')
    await page.getByLabel('Mô tả công khai').fill('Ví màu xanh nhãn FindBack gần thư viện')
    await page.getByLabel('Màu sắc').selectOption('BLUE')
    if (withPhoto) await page.getByLabel('Thêm ảnh').setInputFiles(image)
    await page.getByRole('button', { name: 'Đăng tin', exact: true }).click()
    await expect(page.getByRole('heading', { name: title })).toBeVisible()
  }
  await postThroughUi(owner, foundTitle, 'FOUND', true)
  await expect(owner.getByRole('img', { name: `Ảnh 1 của ${foundTitle}` })).toBeVisible()
  await expect
    .poll(() =>
      owner
        .getByRole('img', { name: `Ảnh 1 của ${foundTitle}` })
        .evaluate((img) => img.naturalWidth),
    )
    .toBe(8)
  await expect(owner.getByText('Người đăng: Chủ tin kiểm thử')).toBeVisible()
  await owner.getByRole('link', { name: 'Sửa tin' }).click()
  await owner.getByLabel('Địa điểm').fill('Cổng phụ thư viện Hà Nội')
  await owner.getByRole('button', { name: 'Lưu thay đổi' }).click()
  await expect(owner.getByText('Cổng phụ thư viện Hà Nội', { exact: true })).toBeVisible()
  await postThroughUi(claimant, lostTitle, 'LOST')
  await claimant.getByRole('link', { name: 'Xem gợi ý tương ứng' }).click()
  await claimant.getByRole('button', { name: 'Tính lại gợi ý' }).click()
  await expect(claimant.getByRole('link', { name: foundTitle })).toBeVisible()
  await claimant
    .getByRole('link', { name: /Chi tiết gợi ý/ })
    .first()
    .click()
  await expect(claimant.getByRole('heading', { name: /điểm tương đồng/ })).toBeVisible()
  await claimant.getByRole('link', { name: /Ví xanh E2E nhặt được/ }).click()
  await claimant.getByRole('link', { name: 'Đây là đồ của tôi' }).click()
  await expect(claimant.getByLabel(/Mã tin nhặt được/)).not.toHaveValue('')
  await claimant.getByLabel(/Bằng chứng sở hữu/).fill(claimText)
  await claimant.getByRole('button', { name: 'Gửi yêu cầu nhận đồ' }).click()
  await expect(claimant.getByText(claimText)).toBeVisible()
  await claimant.getByText('Bổ sung bằng chứng', { exact: true }).click()
  await claimant.getByLabel('Mô tả bổ sung').fill(privatePhotoText)
  await claimant.getByLabel('Ảnh bằng chứng riêng tư').setInputFiles(image)
  await claimant.getByRole('button', { name: 'Gửi bằng chứng bổ sung' }).click()
  await expect(claimant.getByText(privatePhotoText)).toBeVisible()
  console.log('PASS đăng ký, đăng tin, ảnh, tính gợi ý, gửi claim và bổ sung bằng chứng qua web')

  await owner.locator('header').getByRole('link', { name: 'Thông báo' }).click()
  await expect(owner.getByRole('heading', { name: 'Yêu cầu nhận đồ mới' })).toBeVisible()
  await owner.getByRole('link', { name: 'Xem chi tiết' }).first().click()
  await expect(owner.getByText(privatePhotoText)).toBeVisible()
  const privateDownload = owner.getByRole('article').filter({ hasText: privatePhotoText })
  const download = owner.waitForEvent('download')
  await privateDownload.getByRole('button', { name: 'Tải ảnh bằng chứng nếu có' }).click()
  assert.match((await download).suggestedFilename(), /^bang-chung\./)
  await owner.getByRole('button', { name: 'Chấp thuận yêu cầu' }).click()
  await owner.getByRole('dialog').getByRole('checkbox').check()
  await owner.getByRole('dialog').getByRole('button', { name: 'Chấp thuận yêu cầu' }).click()
  await owner.getByLabel('Ghi chú trao trả').fill('Gặp tại quầy bảo vệ.')
  await owner.getByRole('button', { name: 'Lập phiên trao trả' }).click()
  await owner.getByLabel('Tôi đã trực tiếp giao đồ cho người nhận.').check()
  await owner.getByRole('button', { name: 'Ghi nhận đã bàn giao' }).click()
  await expect(owner.getByText('Đã ghi nhận bàn giao. Chờ người nhận xác nhận.')).toBeVisible()

  await claimant.getByRole('button', { name: 'Cập nhật trạng thái' }).click()
  await expect(claimant.getByText(/Gặp tại quầy bảo vệ/)).toBeVisible()
  await claimant.getByRole('button', { name: 'Tôi đã nhận lại đồ' }).click()
  await claimant.getByRole('dialog').getByRole('checkbox').check()
  await claimant.getByRole('dialog').getByRole('button', { name: 'Xác nhận đã nhận đồ' }).click()
  await expect(claimant.getByText('Quá trình xác minh và trao trả đã hoàn tất.')).toBeVisible()
  await owner.locator('header').getByRole('link', { name: 'Thông báo' }).click()
  const completed = owner.getByRole('article').filter({ hasText: 'Trao trả đã được xác nhận' })
  await completed.getByRole('button', { name: 'Đánh dấu đã đọc' }).click()
  await expect(completed.getByText(/Đã đọc/)).toBeVisible()
  console.log('PASS chủ tin duyệt, lập lịch, bàn giao, người nhận xác nhận và đọc thông báo')

  const explore = (page) =>
    page
      .getByRole('navigation', { name: 'Điều hướng chính' })
      .getByRole('link', { name: 'Khám phá đồ thất lạc' })
      .click()
  await explore(owner)
  await owner.getByRole('searchbox').fill(lostTitle)
  await owner.getByRole('button', { name: 'Tìm kiếm' }).click()
  await owner.getByRole('link', { name: /Ví xanh E2E thất lạc/ }).click()
  await owner.getByText('Báo cáo vi phạm', { exact: true }).click()
  await owner.getByLabel('Lý do báo cáo').fill('Báo cáo kiểm thử tích hợp')
  await owner.getByRole('button', { name: 'Gửi báo cáo' }).click()
  await expect(owner.getByText('Đã gửi báo cáo.', { exact: true })).toBeVisible()

  await admin.goto(`${base}/dang-nhap`)
  await admin.getByText('Kết nối phiên phát triển', { exact: true }).click()
  await admin.getByLabel('JWT truy cập').fill(fixtures.tokens.admin)
  await admin.getByRole('button', { name: 'Xác thực với backend' }).click()
  await admin.getByRole('link', { name: 'Quản trị', exact: true }).click()
  const report = admin.getByRole('article').filter({ hasText: 'Báo cáo kiểm thử tích hợp' })
  await report.getByLabel('Kết quả xử lý').selectOption('RESOLVED')
  await report.getByLabel('Ghi chú xử lý').fill('Kiểm tra xong')
  await report.getByRole('button', { name: 'Lưu xử lý' }).click()
  await expect(report.getByRole('heading', { name: 'Đã giải quyết' })).toBeVisible()
  const moderated = admin
    .getByRole('article')
    .filter({ has: admin.getByRole('heading', { name: lostTitle, exact: true }) })
  await moderated.getByLabel('Lý do ẩn tin').fill('Ẩn tin trong kịch bản kiểm thử')
  await moderated.getByRole('button', { name: 'Ẩn tin' }).click()
  await expect(moderated.getByText(/Đã ẩn/)).toBeVisible()
  await explore(admin)
  await admin.getByRole('searchbox').fill(lostTitle)
  await admin.getByRole('button', { name: 'Tìm kiếm' }).click()
  await expect(admin.getByRole('heading', { name: 'Chưa tìm thấy món đồ phù hợp' })).toBeVisible()
  const disposableTitle = 'Tin dùng để kiểm tra xóa'
  await postThroughUi(owner, disposableTitle, 'LOST')
  await owner.locator('header').getByRole('link', { name: 'Cá nhân' }).click()
  await owner
    .getByRole('navigation', { name: 'Điều hướng cá nhân' })
    .getByRole('link', { name: 'Tin của tôi' })
    .click()
  const disposable = owner.getByRole('article').filter({ hasText: disposableTitle })
  await disposable.getByRole('button', { name: 'Xóa tin', exact: true }).click()
  await disposable.getByRole('button', { name: 'Xác nhận xóa' }).click()
  await expect(disposable).toHaveCount(0)
  assert.deepEqual(runtimeErrors, [])
  console.log('PASS báo cáo, xử lý báo cáo, kiểm duyệt và ẩn tin khỏi tìm kiếm')
  console.log('PASS lưu hồ sơ, sửa tin và xóa tin qua web')
} finally {
  if (browser) await browser.close()
  if (server) await server.close()
  live.stdin.end()
  let timer
  await Promise.race([
    exited,
    new Promise((resolve) => {
      timer = setTimeout(resolve, 6000)
    }),
  ])
  clearTimeout(timer)
  if (live.exitCode === null) live.kill()
}
