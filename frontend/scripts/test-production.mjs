/* global process, console */
import { chromium, expect } from '@playwright/test'
import { preview } from 'vite'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const server = await preview({
  root,
  preview: { host: '127.0.0.1', port: 15176, strictPort: true },
})
let browser
try {
  browser = await chromium.launch({
    headless: true,
    ...(process.env.PLAYWRIGHT_CHANNEL
      ? { channel: process.env.PLAYWRIGHT_CHANNEL }
      : process.platform === 'win32'
        ? { channel: 'chrome' }
        : {}),
  })
  const context = await browser.newContext()
  const page = await context.newPage()
  await page.goto('http://127.0.0.1:15176/dang-nhap')
  await expect(page.getByRole('heading', { name: 'Chào mừng bạn trở lại' })).toBeVisible()
  await expect(page.getByText('Kết nối phiên phát triển', { exact: true })).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Đăng nhập', exact: true })).toBeEnabled()
  console.log(
    'PASS built production login enables credentials and excludes development token import.',
  )
} finally {
  if (browser) await browser.close()
  await new Promise((resolve, reject) =>
    server.httpServer.close((error) => (error ? reject(error) : resolve())),
  )
}
