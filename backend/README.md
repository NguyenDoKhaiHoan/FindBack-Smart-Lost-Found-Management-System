# Backend FindBack – Smart Lost & Found Management System

Backend được phát triển bằng **Python 3.11**, **FastAPI**, **SQLAlchemy 2.x Async**, **asyncpg**, **PostgreSQL 16**, **Alembic** và **pytest** theo kiến trúc **Modular Monolith**.

---

## 1. Kiến trúc Modular Monolith

Dự án áp dụng cấu trúc phân tầng nghiêm ngặt:
`Router → Service → Repository → PostgreSQL (asyncpg)`

```text
backend/
├── alembic/                      # Async Alembic migrations
│   ├── versions/                 # Migration version scripts
│   └── env.py                    # Async migration engine runner
├── app/
│   ├── api/                      # (Dành cho routing tổng quát)
│   ├── core/                     # Cấu hình Settings, Dependencies, Auth adapter
│   ├── db/                       # Base, Async Engine, SessionLocal, Models registry
│   ├── shared/                   # Custom HTTP Exceptions (NotFoundError, ForbiddenError, etc.)
│   └── modules/
│       ├── identity/             # Shared User persistence model & Auth (TV1)
│       ├── posts/                # Posts, Categories & Images persistence models (TV2)
│       │   ├── models/           # Category, Post, PostImage SQLAlchemy models
│       │   └── repositories/     # PostRepository (query, search, row-level locking)
│       ├── matching/             # Categories & Matching engine (TV3)
│       ├── claims_returns/       # Claims & Returns workflow (TV4)
│       └── notifications_admin/  # Notifications & Admin moderation (TV5 - KAN-31)
│           ├── models/           # Notification SQLAlchemy model
│           ├── schemas/          # Pydantic v2 schemas (contract KAN-30)
│           ├── repositories/     # Async database access layer
│           ├── services/         # Business logic & inter-module event contract
│           └── routers/          # FastAPI HTTP endpoints
├── tests/
│   ├── conftest.py               # Async fixtures (test_engine, db_session, client, test_users)
│   ├── api/                      # API endpoint tests (test_notifications.py)
│   └── unit/                     # Unit tests for services & repositories
├── alembic.ini                   # Alembic configuration
├── pytest.ini                    # Pytest configuration (asyncio_mode = auto)
└── requirements.txt              # Dependency manifest
```

---

## 2. Cài đặt và môi trường phát triển

### 2.1. Cài đặt Python Dependencies

Khuyến nghị sử dụng Python 3.11 trong virtual environment:

```bash
cd backend
python -m venv .venv

# Kích hoạt trên Windows PowerShell:
.venv\Scripts\Activate.ps1

# Cài đặt thư viện:
pip install -r requirements.txt
```

### 2.2. Cấu hình biến môi trường (`.env`)

Sao chép từ file mẫu tại thư mục gốc repository:

```bash
cp ../.env.example ../.env
```

Nội dung `.env` chuẩn kết nối PostgreSQL async:

```env
ENVIRONMENT=development
DEBUG=true
PROJECT_NAME="FindBack"
API_V1_STR="/api/v1"

# Database Configuration (PostgreSQL 16)
POSTGRES_SERVER=localhost
POSTGRES_PORT=5432
POSTGRES_USER=findback
POSTGRES_PASSWORD=findback_secret
POSTGRES_DB=findback

# Async SQLAlchemy Database URL
DATABASE_URL=postgresql+asyncpg://findback:findback_secret@localhost:5432/findback
TEST_DATABASE_URL=postgresql+asyncpg://findback:findback_secret@localhost:5432/findback_test
```

---

## 3. Khởi chạy Database & Migration

### 3.1. Khởi chạy PostgreSQL Container

Sử dụng Docker Compose tại thư mục `infra/docker/`:

```bash
docker compose -f ../infra/docker/compose.yaml up -d
```

### 3.2. Chạy Migration Alembic

Áp dụng toàn bộ migration vào cơ sở dữ liệu:

```bash
cd backend
python -m alembic upgrade head
```

Kiểm tra trạng thái migration:

```bash
python -m alembic current
```

Rollback migration (nếu cần):

```bash
python -m alembic downgrade -1
```

---

## 4. Khởi chạy Backend Server

Khởi chạy máy chủ phát triển với Uvicorn:

```bash
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
# Lưu ý: nếu cổng 8000 đang được sử dụng bởi dịch vụ khác, có thể đổi sang --port 8001
```

Truy cập tài liệu OpenAPI / Swagger UI:
- **Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs) (hoặc port tương ứng)
- **ReDoc**: [http://localhost:8000/redoc](http://localhost:8000/redoc)
- **Health Check**: [http://localhost:8000/health](http://localhost:8000/health) hoặc [http://localhost:8000/api/v1/health](http://localhost:8000/api/v1/health)

---

## 5. Chạy Test Suite

Chạy toàn bộ unit test và integration/API test bằng Pytest:

```bash
cd backend
python -m pytest -v
```

> **Cách ly cơ sở dữ liệu kiểm thử (TEST-01):**
> Test suite tự động kết nối đến database riêng biệt `findback_test` (thông qua cấu hình `TEST_DATABASE_URL`), tự động dọn dẹp (truncate) dữ liệu bảng sau mỗi test, đảm bảo tuyệt đối không làm ảnh hưởng hoặc tích lũy dữ liệu rác trên database phát triển `findback`.

Kiểm tra chi tiết từng file:

```bash
python -m pytest tests/api/test_admin_posts.py -v
python -m pytest tests/api/test_posts_schema.py -v
python -m pytest tests/api/test_notifications.py -v
python -m pytest tests/unit/notifications_admin/test_notification_service.py -v
```

---

## 6. Chi tiết triển khai Module Notifications (KAN-31)

### 6.1. API Endpoints

Tuân thủ nghiêm ngặt đặc tả tại `docs/api/API_CONTRACT_NOTIFICATIONS_ADMIN.md`:

| Phương thức | Endpoint | Mô tả | Quyền truy cập |
| --- | --- | --- | --- |
| `GET` | `/api/v1/notifications` | Lấy danh sách thông báo phân trang của user hiện tại | User đăng nhập (`ACTIVE`) |
| `PATCH` | `/api/v1/notifications/{id}/read` | Đánh dấu thông báo đã đọc (idempotent) | Chủ sở hữu thông báo (`ACTIVE`) |

### 6.2. Cơ chế Xác thực & RBAC (SEC-01 & SEC-02)

- Dependency `get_current_active_user` xác thực chữ ký mật mã JWT (sử dụng `PyJWT`) với thuật toán máy chủ cấu hình cố định (`HS256`), kiểm tra thời hạn hiệu lực (`exp`), và giải mã user UUID từ claim `sub`.
- Tuyệt đối không chấp nhận chuỗi UUID thô và đã loại bỏ hoàn toàn header bypass `X-User-Id`.
- Kiểm tra trạng thái tài khoản: Nếu user không ở trạng thái `ACTIVE` (ví dụ `SUSPENDED` hoặc `DISABLED`), hệ thống trả về HTTP `403 Forbidden`.
- Người dùng chỉ xem được thông báo có `recipient_id == current_user.id`.
- Thao tác đánh dấu đã đọc đối với thông báo không thuộc quyền sở hữu sẽ trả về HTTP `404 Not Found` để chống brute-force và enumerate ID tài nguyên.

### 6.3. Giao diện Event Service nội bộ (`NotificationService`)

Tuân thủ đặc tả tại `docs/api/NOTIFICATION_EVENT_CONTRACT.md`:
- Các module khác (`claims_returns`, `posts`) phát thông báo thông qua phương thức `NotificationService.create_notification(session, data, auto_commit=True)`.
- **Deduplication / Concurrency Idempotency (CONC-01)**: Áp dụng câu lệnh PostgreSQL `INSERT ... ON CONFLICT (event_id) DO NOTHING`, bảo đảm xử lý an toàn đồng thời, không sinh lỗi unhandled `IntegrityError` hay HTTP 500 khi nhiều request đồng thời cùng phát một `event_id`. Hỗ trợ tham gia vào transaction của caller mà không phá vỡ transaction.
- **Deep Allowlist Sanitization (PRIV-01)**: Áp dụng cơ chế Whitelist (Allowlist) kết hợp duyệt đệ quy đa tầng, loại bỏ triệt để token, mật khẩu, api key hoặc bằng chứng riêng tư ở bất kỳ cấp độ nào của cấu trúc metadata.

---

## 7. Chi tiết triển khai Module Admin Post Moderation (KAN-32)

### 7.1. API Endpoints

Tuân thủ nghiêm ngặt đặc tả tại `docs/api/API_CONTRACT_NOTIFICATIONS_ADMIN.md`:

| Phương thức | Endpoint | Mô tả | Quyền truy cập |
| --- | --- | --- | --- |
| `GET` | `/api/v1/admin/posts` | Danh sách bài đăng phân trang, hỗ trợ lọc `status`, `type` và tìm kiếm `q` | Quản trị viên (`ADMIN`) |
| `PATCH` | `/api/v1/admin/posts/{id}/moderation` | Kiểm duyệt bài đăng (hành động `HIDE`, kèm lý do bắt buộc) | Quản trị viên (`ADMIN`) |

### 7.2. Quy tắc nghiệp vụ & Tính nguyên tử (Transaction Atomicity)

- **Quyền hạn**: Sử dụng dependency `get_current_admin_user`, từ chối người dùng thông thường (`USER`) với HTTP `403 Forbidden`.
- **Ràng buộc trạng thái bài đăng**:
  - Không cho phép kiểm duyệt bài đăng đã đóng (`CLOSED`), trả về HTTP `400 Bad Request`.
  - Hỗ trợ hành động `HIDE`, chuyển trạng thái bài đăng sang `HIDDEN`.
  - Ghi nhận `moderated_by` (UUID của Admin), `moderated_at` (thời điểm UTC), và `moderation_reason` (lý do không rỗng).
- **Ghi nhận Audit Log**:
  - Mỗi hành động kiểm duyệt được lưu trữ trong bảng `audit_logs` gồm `actor_id`, `action="HIDE"`, `target_type="POST"`, `target_id`, `reason`, `old_status`, `new_status`.
- **Thông báo cho chủ bài đăng (`POST_HIDDEN`)**:
  - Gọi `NotificationService.create_notification(auto_commit=False)` gửi thông báo cho tác giả bài đăng (`post.user_id`).
  - Sử dụng `event_id` tất định (`uuid.uuid5`) để chống trùng lặp thông báo nếu kiểm duyệt lặp lại.
- **Tính nguyên tử**: Thao tác cập nhật bài đăng, ghi audit log và tạo thông báo nằm chung trong một database transaction. Nếu có bất kỳ bước nào thất bại, toàn bộ transaction được rollback đồng thời.
