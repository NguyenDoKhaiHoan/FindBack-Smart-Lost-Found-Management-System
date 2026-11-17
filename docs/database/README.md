# Kiến trúc Cơ sở dữ liệu FindBack

Tài liệu này mô tả kiến trúc cơ sở dữ liệu thực thi của hệ thống **FindBack – Smart Lost & Found Management System**, được quản lý thông qua **Alembic** migrations và **SQLAlchemy 2.x Async**.

---

## 1. Quyết định Kiến trúc: Chuẩn hóa Định danh UUID

Trước đây, file phác thảo `findback.sql` sử dụng kiểu dữ liệu `BIGINT GENERATED ALWAYS AS IDENTITY` kết hợp trigger đồng bộ trong database (`notify_workflow`).

Trong quá trình triển khai kiến trúc **Modular Monolith hiện đại** cho dự án FindBack, toàn bộ hệ thống đã chuyển sang chuẩn hóa sử dụng **UUID (RFC 4122)** làm khóa chính (`PRIMARY KEY`) cho tất cả các thực thể:
1. **Phân tán & Độc lập**: Các module (`claims_returns`, `posts`, `notifications_admin`) có thể sinh ID client-side / service-side trước khi ghi xuống DB, tối ưu cho kiến trúc event-driven và outbox pattern.
2. **Bảo mật**: Khóa chính UUID ngăn chặn tấn công liệt kê tài nguyên (resource enumeration / ID harvesting) thường gặp với Auto-increment BIGINT.
3. **Loại bỏ Trigger ngầm**: Nghiệp vụ tạo thông báo được điều phối qua Application Service Layer (`NotificationService`) với cơ chế kiểm tra deduplication (`event_id`), không phụ thuộc vào SQL trigger ngầm, tránh tình trạng duplicate notifications hoặc che giấu lỗi giao dịch.

---

## 2. Chi tiết Schema hiện tại (Revision: `20261117_01`)

### 2.1. Bảng `users` (Shared Identity Model)

Lưu trữ thông tin định danh và trạng thái tài khoản người dùng:

| Cột | Kiểu dữ liệu | Ràng buộc | Mô tả |
| --- | --- | --- | --- |
| `id` | `UUID` | `PRIMARY KEY` | Định danh người dùng |
| `email` | `VARCHAR(255)` | `NOT NULL, UNIQUE` | Email đăng nhập, đã chuẩn hóa chữ thường |
| `password_hash` | `VARCHAR(255)` | `NOT NULL` | Mật khẩu đã hash (Argon2 / Bcrypt) |
| `role` | `VARCHAR(30)` | `NOT NULL, CHECK (role IN ('USER', 'ADMIN'))` | Vai trò hệ thống |
| `status` | `VARCHAR(30)` | `NOT NULL, CHECK (status IN ('ACTIVE', 'SUSPENDED', 'DISABLED'))` | Trạng thái tài khoản |
| `created_at` | `TIMESTAMPTZ` | `NOT NULL, DEFAULT NOW()` | Thời điểm tạo |
| `updated_at` | `TIMESTAMPTZ` | `NOT NULL, DEFAULT NOW()` | Thời điểm cập nhật cuối |

### 2.2. Bảng `notifications` (Module Notifications / Admin)

Lưu trữ thông báo gửi tới người dùng:

| Cột | Kiểu dữ liệu | Ràng buộc | Mô tả |
| --- | --- | --- | --- |
| `id` | `UUID` | `PRIMARY KEY` | Định danh thông báo |
| `recipient_id` | `UUID` | `NOT NULL, FOREIGN KEY (users.id) ON DELETE CASCADE` | ID người nhận |
| `event_id` | `UUID` | `NULL, UNIQUE` | ID của sự kiện phát sinh (dùng cho Idempotency / Deduplication) |
| `event_type` | `VARCHAR(50)` | `NOT NULL` | Loại sự kiện (CLAIM_CREATED, POST_RESOLVED, v.v.) |
| `title` | `VARCHAR(255)` | `NOT NULL` | Tiêu đề thông báo |
| `message` | `TEXT` | `NOT NULL` | Nội dung thông báo |
| `resource_type` | `VARCHAR(50)` | `NULL` | Loại tài nguyên liên kết (`CLAIM`, `POST`, `RETURN`, `REPORT`) |
| `resource_id` | `UUID` | `NULL` | ID tài nguyên liên kết |
| `metadata_json` | `JSONB` | `NULL` | Dữ liệu mở rộng đã được làm sạch bảo mật |
| `is_read` | `BOOLEAN` | `NOT NULL, DEFAULT FALSE` | Trạng thái đã đọc |
| `read_at` | `TIMESTAMPTZ` | `NULL` | Thời điểm đánh dấu đã đọc |
| `created_at` | `TIMESTAMPTZ` | `NOT NULL, DEFAULT NOW()` | Thời điểm tạo thông báo |

### 2.3. Các chỉ mục tối ưu hóa (Indexes)

1. `ix_notifications_recipient_created`: `(recipient_id, created_at DESC)`
   - Tối ưu hóa truy vấn phân trang thông báo của người dùng theo thứ tự mới nhất (`GET /api/v1/notifications?page=1&limit=20`).
2. `ix_notifications_recipient_read`: `(recipient_id, is_read)`
   - Tối ưu hóa lọc thông báo chưa đọc (`GET /api/v1/notifications?is_read=false`).
3. `ix_notifications_event_id`: `UNIQUE (event_id)`
   - Đảm bảo tính Idempotent: một sự kiện nghiệp vụ chỉ được sinh ra tối đa 1 thông báo duy nhất.

---

## 3. Lịch sử Migration (Alembic)

Các migration được đặt tại `backend/alembic/versions/`:

- **Revision `20261117_01_initial_users_notifications`**:
  - Tạo bảng `users` với các Check Constraint `role`, `status`.
  - Tạo bảng `notifications` với FK `users.id`, Unique Constraint `event_id`, và các Composite Indexes.
  - Hỗ trợ đầy đủ cả `upgrade` (head) và `downgrade` (base).

---

## 4. Hướng dẫn tích hợp cho các module khác

- **Module Identity (TV1)**: Mở rộng thêm bảng hồ sơ (profiles, social_auth) hoặc thêm cột vào `users` thông qua migration mới kế thừa `20261117_01`.
- **Module Posts (TV2)**: Sử dụng khóa chính UUID cho `posts.id`. Khi có sự kiện `POST_RESOLVED` hoặc `POST_HIDDEN`, gọi `NotificationService.create_notification` với `resource_type="POST"` và `resource_id=post.id`.
- **Module Claims & Returns (TV4)**: Sử dụng UUID cho `claims.id` và `returns.id`. Khi claim được tạo/phê duyệt, gọi `NotificationService.create_notification` kèm `event_id` để đảm bảo không bị nhân đôi thông báo.
