# Backend FindBack

Backend đang được khởi tạo với SQLAlchemy 2.x, PostgreSQL và Alembic. Hiện đã có model `users` và migration ban đầu; chưa có entrypoint FastAPI hay API nghiệp vụ.

## Cấu trúc một module

```text
app/modules/<module>/
├── routers/         # HTTP endpoint, dependency và chuyển tiếp đến service
├── schemas/         # Pydantic request/response; tách dữ liệu công khai/riêng tư
├── services/        # Use case, quyền nghiệp vụ, state machine, transaction
├── repositories/    # Truy vấn và ghi dữ liệu bằng session được truyền vào
└── models/          # SQLAlchemy models thuộc module
```

| Module | Chủ trì | Dữ liệu phụ trách |
| --- | --- | --- |
| `identity` | TV1 | users |
| `posts` | TV2 | posts, post_images |
| `matching` | TV3 | categories, matches |
| `claims_returns` | TV4 | claims, claim_evidence, returns |
| `notifications_admin` | TV5 | notifications, reports; điều phối audit_logs |

`audit_logs` phục vụ mọi module; TV5 điều phối cấu trúc và nơi ghi log, từng service chịu trách nhiệm phát sinh sự kiện cho hành động của mình. Đây là quy ước tổ chức đề xuất, cần thống nhất khi thiết kế schema.

## Thư mục dùng chung

- `app/api/`: tập hợp router và dependency HTTP dùng chung.
- `app/core/`: đọc cấu hình, JWT/RBAC, logging; không chứa nghiệp vụ riêng của một module.
- `app/db/`: engine, session, metadata và cơ sở transaction.
- `app/shared/`: exception và tiện ích có nhiều module sử dụng; tránh gom mọi logic vào đây.
- `alembic/versions/`: migration có thứ tự; migration `0001_create_users` tạo bảng người dùng.
- `tests/unit/<module>/`, `tests/integration/`, `tests/api/`: xem [kế hoạch kiểm thử](../docs/testing.md).

## Cài đặt và migration

Từ thư mục `backend`, tạo môi trường ảo và cài dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Cấu hình database và JWT

Từ repository root, tạo `.env` từ template rồi cập nhật URL PostgreSQL và secret JWT (không commit `.env`):

```powershell
Copy-Item .env.example .env
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Dán kết quả lệnh tạo secret vào `JWT_SECRET_KEY` trong `.env`. Backend đọc `.env` ở repository root; biến môi trường đã export sẽ được ưu tiên hơn giá trị trong file.

Từ thư mục `backend`, áp dụng migrations (nếu đang ở repository root, chuyển vào `backend` trước):

```powershell
# Chỉ cần nếu shell hiện đang ở repository root
Set-Location backend
python -m alembic upgrade head
```

Khi cập nhật model ở các lần sau, tạo migration rồi kiểm tra nội dung trước khi áp dụng:

```powershell
python -m alembic revision --autogenerate -m "describe schema change"
python -m alembic upgrade head
```

Quay lui một revision trong môi trường phù hợp:

```powershell
python -m alembic downgrade -1
```

## Chạy FastAPI

Sau khi cấu hình database/JWT và migrate, chạy từ thư mục gốc repository (nếu shell vẫn ở `backend`, chuyển về root trước):

```powershell
# Chỉ cần nếu shell hiện đang ở backend
Set-Location ..
python -m uvicorn app.main:app --reload --app-dir backend
```

Mở `http://127.0.0.1:8000/docs` để xem OpenAPI UI. Các endpoint Identity gồm `POST /api/v1/auth/register`, `POST /api/v1/auth/login`, `GET /api/v1/users/me` và `PATCH /api/v1/users/me`. Đăng nhập trả bearer token; dùng nút **Authorize** trong `/docs` để thử hai endpoint `/users/me`.

## Chạy kiểm thử

Từ thư mục `backend`, cài dependency kiểm thử và chạy toàn bộ test:

```powershell
pip install -r requirements-dev.txt
python -m pytest tests
```

Integration test sử dụng SQLite in-memory riêng cho từng test case, không cần kết nối PostgreSQL và tự xóa schema/dữ liệu sau khi chạy.

### Thử GET/PATCH profile trong Swagger

1. Gọi `POST /api/v1/auth/register` để tạo user, sau đó `POST /api/v1/auth/login` bằng email/password.
2. Sao chép giá trị `access_token` từ response login.
3. Nhấn **Authorize** trong Swagger UI và nhập `Bearer <access_token>` (hoặc dán token nếu hộp thoại tự thêm tiền tố Bearer), rồi xác nhận.
4. Gọi `GET /api/v1/users/me` để đọc profile; response chỉ có `id`, `email`, `full_name`, `phone`, `avatar_url`, `role`, `created_at`.
5. Gọi `PATCH /api/v1/users/me` với một phần các trường được phép, ví dụ:

```json
{
  "full_name": "Nguyen Van A",
  "phone": "0900000000",
  "avatar_url": "https://example.com/avatar.png"
}
```

Chỉ `full_name`, `phone`, `avatar_url` được cập nhật; gửi trường khác sẽ bị từ chối. Có thể đặt `phone` hoặc `avatar_url` thành `null` để xóa giá trị. Cả hai endpoint profile yêu cầu bearer token hợp lệ.

`DATABASE_URL` ưu tiên hơn URL placeholder trong `alembic.ini`. Các quan hệ đến posts, claims và notifications chưa được ánh xạ cho đến khi model tương ứng được triển khai. Mật khẩu mới được hash bằng bcrypt; hash Argon2 cũ được nâng cấp sang bcrypt sau lần đăng nhập thành công tiếp theo.

## Các bước tiếp theo

1. Chốt phiên bản Python và khai báo dependency/lockfile.
2. Hoàn thiện cấu hình FastAPI và mount routers của các module còn lại.
3. Khởi tạo session PostgreSQL và bổ sung migrations cho các module còn lại.
4. Định nghĩa schemas và triển khai từng use case.
5. Bổ sung fixture, test và lệnh chạy được kiểm chứng vào README này.

Không phục vụ bằng chứng sở hữu bằng static/public route. Đường dẫn upload trong `.env.example` là đề xuất local, không phải cơ chế bảo vệ đã triển khai.
