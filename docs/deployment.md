# Triển khai FindBack trên Vercel

GitHub Actions chạy lint và kiểm thử backend, đồng thời chạy lint, kiểm thử và build frontend. Dự án Vercel hiện có kết nối GitHub và tự build khi có push. Nhánh được đặt trong **Production → Branch Tracking** sẽ cập nhật tên miền chính. [Tích hợp GitHub của Vercel](https://vercel.com/docs/git/vercel-for-github)

## Triển khai từ GitHub Actions sau khi kiểm thử

Để GitHub Actions triển khai production sau khi cả hai job đạt, thêm biến cấp repository `VERCEL_CLI_DEPLOY=true` tại **Settings → Secrets and variables → Actions → Variables** và thực hiện các bước bên dưới. Job triển khai dùng nhánh `hoan` mặc định. Có thể đổi nhánh bằng biến cấp repository `PRODUCTION_BRANCH`. Pull request chạy hai job kiểm tra.

1. Trong dự án Vercel hiện có, kiểm tra **Root Directory** là `frontend`, **Framework Preset** là **Vite** và **Output Directory** là `dist`. Workflow chạy Vercel CLI từ thư mục gốc repo. [Cấu hình build Vercel](https://vercel.com/docs/builds/configure-a-build)
2. Trong GitHub, vào **Settings → Environments → New environment**, tạo môi trường `production`. Thêm ba **Environment secrets** dưới đây. Lấy `projectId` và `orgId` bằng cách chạy `npx vercel@66.6.0 link` ở thư mục gốc và chọn dự án hiện có. Kết quả nằm trong `.vercel/project.json`. [Vercel và GitHub Actions](https://vercel.com/kb/guide/how-can-i-use-github-actions-with-vercel)

   | Secret | Giá trị |
   | --- | --- |
   | `VERCEL_TOKEN` | Access token có quyền trên dự án Vercel |
   | `VERCEL_ORG_ID` | `orgId` của dự án Vercel |
   | `VERCEL_PROJECT_ID` | `projectId` của dự án Vercel |

3. Đặt **Production Branch** của dự án Vercel thành nhánh triển khai và bật tự gán tên miền production. Nếu Vercel đang kết nối trực tiếp với GitHub, đặt **Ignored Build Step → Only build pre-production** trong **Build and Deployment** để Vercel tiếp tục tạo preview và giao việc cập nhật production cho workflow. [Cấu hình Ignored Build Step](https://vercel.com/docs/project-configuration/project-settings#ignored-build-step)
4. Đẩy commit chứa workflow lên nhánh triển khai. Mở tab **Actions → FindBack CI/CD** để theo dõi. Job deploy hiển thị URL bản triển khai và Vercel cập nhật tên miền production sau khi hoàn tất.

## Kết nối API production

FastAPI cần một dịch vụ riêng có PostgreSQL. Sau khi có URL API công khai, thêm `VITE_API_BASE_URL` trong **Vercel → Settings → Environment Variables** cho môi trường Production, ví dụ `https://api.example.com`. Trên backend, thêm tên miền frontend vào `CORS_ORIGINS`. Website hiện tại phục vụ frontend trên Vercel. Workflow này kiểm tra mã backend bằng SQLite và triển khai frontend.

Trên dịch vụ backend, chạy `uv run --locked alembic upgrade head` khi triển khai phiên bản có migration. Cấu hình `DATABASE_URL`, `JWT_SECRET_KEY` và khóa OpenAI ở dịch vụ backend. Các tính năng dùng mô hình CPU cần nhóm phụ thuộc `ai` và dung lượng cho trọng số.

## Kiểm tra sau khi triển khai

- Mở trang chủ và tải trực tiếp một đường dẫn như `/kham-pha` để kiểm tra điều hướng SPA.
- Khi đã kết nối FastAPI, kiểm tra `/api/v1/health` trên tên miền backend và thử đăng nhập từ website.
- Nếu cần quay lại phiên bản trước, revert thay đổi qua nhánh triển khai. Workflow sẽ kiểm tra và triển khai commit revert.
