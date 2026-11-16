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

Đặt `DATABASE_URL` trỏ đến database PostgreSQL đã tạo (không commit thông tin đăng nhập):

```powershell
$env:DATABASE_URL = "postgresql+psycopg://<user>:<password>@localhost:5432/findback"
```

Áp dụng migration hiện tại:

```powershell
alembic upgrade head
```

Khi cập nhật model ở các lần sau, tạo migration rồi kiểm tra nội dung trước khi áp dụng:

```powershell
alembic revision --autogenerate -m "describe schema change"
alembic upgrade head
```

Quay lui một revision trong môi trường phù hợp:

```powershell
alembic downgrade -1
```

`DATABASE_URL` ưu tiên hơn URL placeholder trong `alembic.ini`. Quan hệ `User.posts`, `User.claims` và `User.notifications` dùng tên model dự kiến; mỗi module liên quan cần bổ sung model, khóa ngoại trỏ đến `users.id` và relationship đối ứng trước khi khởi tạo mapper hoặc truy vấn các quan hệ đó. `password_hash` chỉ lưu giá trị hash; tầng đăng ký/xác thực phải hash mật khẩu trước khi ghi và không lưu mật khẩu dạng rõ.

## Các bước tiếp theo

1. Chốt phiên bản Python và khai báo dependency/lockfile.
2. Thêm application factory hoặc entrypoint FastAPI và cấu hình môi trường.
3. Khởi tạo session PostgreSQL và bổ sung migrations cho các module còn lại.
4. Mount routers, định nghĩa schemas và triển khai từng use case.
5. Bổ sung fixture, test và lệnh chạy được kiểm chứng vào README này.

Không phục vụ bằng chứng sở hữu bằng static/public route. Đường dẫn upload trong `.env.example` là đề xuất local, không phải cơ chế bảo vệ đã triển khai.
