# Frontend FindBack

Frontend dự kiến dùng React. Bộ khung chưa có `package.json`, dependency, entrypoint hoặc công cụ build; chưa chạy được bằng npm. Vite/TypeScript là lựa chọn có thể cân nhắc, chưa được chốt trong tài liệu phân tích.

| Thư mục | Mục đích |
| --- | --- |
| `src/app/` | Khởi tạo ứng dụng, điều hướng, providers, route guards |
| `src/features/auth/` | Đăng ký, đăng nhập, phiên đăng nhập |
| `src/features/profile/` | Hồ sơ người dùng |
| `src/features/posts/` | Danh sách, chi tiết, tạo/sửa tin LOST/FOUND |
| `src/features/search_matching/` | Bộ lọc, gợi ý và tiêu chí matching |
| `src/features/claims_returns/` | Gửi claim, bằng chứng, xác minh, trao trả |
| `src/features/notifications/` | Thông báo trong ứng dụng |
| `src/features/admin/` | Báo cáo, kiểm duyệt, thống kê |
| `src/components/ui/` | Thành phần UI dùng chung |
| `src/hooks/`, `src/lib/` | Hook, HTTP client và tiện ích dùng chung |
| `src/assets/`, `src/styles/` | Tài nguyên và style |
| `public/` | Tài nguyên công khai được đóng gói cùng frontend |
| `tests/unit/`, `tests/e2e/` | Kiểm thử giao diện và luồng người dùng |

Trong từng feature, chỉ thêm `components/`, `pages/`, `api/`, `hooks/` khi triển khai cần đến. Không đặt ảnh upload, bằng chứng hoặc secret vào `public/`, `assets/` hay biến môi trường frontend.

Backend phải kiểm tra quyền cho mọi thao tác; route guard phía frontend chỉ hỗ trợ trải nghiệm. Cần chốt cách quản lý token/cookie và bảo vệ phiên trước khi triển khai auth.

Khi khởi tạo React, bổ sung dependency, lockfile, scripts chạy/build/test, cấu hình API URL và hướng dẫn môi trường vào README này.
