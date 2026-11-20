# Backend FindBack

Backend FastAPI dùng chung JWT, phân quyền, SQLAlchemy và PostgreSQL cho cả năm module. Xem [danh mục API và luồng nghiệp vụ](../docs/api/endpoints.md).

## Chạy local

Cài Python 3.11 trở lên và [uv](https://docs.astral.sh/uv/). Khởi động PostgreSQL theo [hướng dẫn Docker](../infra/docker/README.md). Dùng `.env.example` để tạo `.env` ở thư mục gốc. Điền `DATABASE_URL`, `POSTGRES_PASSWORD` và `JWT_SECRET_KEY` ngẫu nhiên (ít nhất 32 ký tự). Biến môi trường của tiến trình được ưu tiên.

```powershell
cd backend
uv sync --locked
uv run --locked alembic upgrade head
uv run --locked uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000
```

Mở [Swagger UI](http://127.0.0.1:8000/docs) hoặc lấy schema từ `/openapi.json`. Gọi `POST /api/v1/auth/register` rồi `POST /api/v1/auth/login`. Trong Swagger **Authorize**, dán `access_token` để thử route yêu cầu đăng nhập. Sau khi đăng ký tài khoản dự kiến làm admin, người quản trị máy chủ có thể cấp quyền bằng lệnh sau. Tài khoản đăng nhập lại để lấy JWT mới.

```powershell
uv run --locked python -m app.grant_admin admin@example.com
```

Migration `0003_integrated_system` nâng cấp schema UUID của nhánh Claims, giữ các ID và dữ liệu hiện có, thêm danh mục mẫu và tạo thông báo cho các sự kiện Claims đã có. Các bảng có ID số từ bản chạy riêng của Identity và Posts cần kế hoạch nhập dữ liệu riêng. Có thể cấu hình schema PostgreSQL qua `DATABASE_SCHEMA` (mặc định `findback_api`).

Migration `0004_post_image_data` lưu ảnh bài đăng mới trong DB. Ảnh bài đăng tải lên trước migration và ảnh bằng chứng vẫn được đọc từ `backend/uploads` hoặc thư mục `MEDIA_ROOT`. Khi sao lưu, giữ cả DB và thư mục này. Nếu tệp ảnh bài đăng cũ đã mất, chủ tin đang mở có thể gửi lại ảnh qua `POST /api/v1/posts/{id}/images?restore_image_id={image_id}` để giữ nguyên đường dẫn và thứ tự ảnh. `CORS_ORIGINS` là danh sách origin ngăn cách bằng dấu phẩy.

## Kiểm thử

```powershell
uv run --locked pytest -q
uv run --locked ruff check app tests alembic
```

Suite mặc định dùng SQLite tạm. Chạy thêm trên PostgreSQL để kiểm chứng migration, row lock và các request cạnh tranh. Mỗi test dùng schema riêng. `TEST_DATABASE_URL` phải trỏ đến database kiểm thử và tài khoản có quyền tạo schema.

```powershell
$env:TEST_DATABASE_URL = '<PostgreSQL test URL>'
uv run --locked pytest --postgres -q
```

Để chạy kiểm tra Claims cũ trên local, có thể dùng `uv run --locked python -m app.seed_demo`, sau đó chạy `app.check_claims` và `app.check_claim_decisions` bằng Python. Dữ liệu và token giả nằm trong `backend/.local/`.
