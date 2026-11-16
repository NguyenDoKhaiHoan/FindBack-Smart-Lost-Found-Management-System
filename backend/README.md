# Backend FindBack

Đã triển khai ba API Claims bằng FastAPI, Pydantic, SQLAlchemy 2 và Alembic:

| API | Kết quả | Quyền |
| --- | --- | --- |
| POST /api/v1/claims | 201 PENDING + Evidence | User hoạt động, FOUND của người khác |
| GET /api/v1/claims/me | Danh sách có phân trang | claimant / reviewer / all của chính actor |
| GET /api/v1/claims/{id} | Chi tiết và bằng chứng | Claimant hoặc chủ tin; người ngoài cùng 404 |

## Chạy local

Python >= 3.11 và [uv](https://docs.astral.sh/uv/). Khởi động PostgreSQL theo
[hướng dẫn Docker](../infra/docker/README.md), sau đó từ thư mục gốc:

```powershell
cd backend
uv sync --locked
```

Tạo `backend/.env` (gitignored): đặt `DATABASE_URL` trỏ PostgreSQL local,
`JWT_SECRET_KEY` ngẫu nhiên ít nhất 32 ký tự, `APP_ENV=development`.
Tạo secret bằng `python -c "import secrets; print(secrets.token_urlsafe(48))"`.
Ứng dụng đọc `.env` gốc rồi `backend/.env`; biến môi trường tiến trình ưu tiên cao nhất.
Placeholder CHANGE_ME bị từ chối. Không commit secret/token.

```powershell
uv run alembic upgrade head
uv run python -m app.seed_demo
uv run uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000 --no-access-log
```

Mở [Swagger UI](http://127.0.0.1:8000/docs). OpenAPI thực tế: `/openapi.json`.
Swagger UI 5.35.0 được phục vụ local, hỗ trợ OpenAPI 3.1, không phụ thuộc CDN.

Seed chỉ thêm User/Post giả lập, không tạo claim hoặc sửa bản ghi có sẵn.
File `.local/claims-demo.json` chứa ID, request mẫu và JWT hạn một giờ của
owner, claimant, outsider, admin. Chạy lại seed để lấy token mới.
Trong Swagger: **Authorize** → dán riêng `users.claimant.token` (không thêm Bearer)
→ POST với `create_body`. Đổi token owner để xem `relation=reviewer`.
Outsider/admin xem detail sẽ nhận 404. Token không được lưu lâu dài trong trình duyệt.

## Kiểm thử và bằng chứng

```powershell
uv run pytest -q --junitxml=.local/claims-sqlite-tests.xml
uv run ruff check app tests alembic
```

Suite mặc định dùng SQLite tạm. Để kiểm chứng khóa và cạnh tranh trên PostgreSQL,
đặt TEST_DATABASE_URL vào database kiểm thử, với quyền tạo schema:

```powershell
$env:TEST_DATABASE_URL = '<PostgreSQL test URL>'
uv run pytest --postgres -q --junitxml=.local/claims-postgres-tests.xml
```

Mỗi test dùng schema ngẫu nhiên `claims_test_<uuid>` và chỉ xóa schema đó khi kết thúc.
Không tự lấy URL production khi thiếu TEST_DATABASE_URL.
Kiểm tra HTTP trên server local đang chạy, sau khi seed:

```powershell
uv run python -m app.check_claims
```

Lệnh này thêm một Post/Claim giả mới mỗi lần và ghi báo cáo không token/bằng chứng
vào `.local/claims-live-checks.json`. Xem [báo cáo bàn giao](../docs/api/claims-implementation.md).

## Tích hợp

- Router → service → repository, cùng session cho xác thực, Posts và Claims.
- JWT HS256 kiểm chữ ký, sub UUID, exp, iat, jti, issuer, audience, token_version;
  đối chiếu User hiện có/hoạt động và bảng thu hồi jti. Tăng users.token_version
  để thu hồi mọi token của User, hoặc thêm jti vào revoked_tokens.
  Issuer mặc định findback, audience findback-api.
- Identity/Posts hiện là adapter persistence tối thiểu có FK thực, chưa có API đăng
  nhập/đăng tin. Không có route công khai cấp token; seed chỉ dùng ở development.
- Theo contract, ID là UUID. PostgreSQL dùng schema mới findback_api, đổi qua
  DATABASE_SCHEMA; không sửa public, claims_dev, claims_returns_demo hoặc tự nhập
  outputs/findback.sql có ID BIGINT. Ghép schema BIGINT cần mapping/migration
  và cập nhật contract riêng, không ép đổi ID ngầm.
- Post adapter: OPEN nhận claim, CLOSED không nhận; tin ẩn/xóa mềm bị che 404.
  Writer tương lai phải khóa Post → Claim → Return, cấm đổi owner khi có claim mở.
  PostgreSQL dùng row lock và hai partial unique index.
- Claim, Evidence, audit, outbox cùng commit. Chưa có worker gửi thông báo;
  payload không chứa bằng chứng/lý do. Không lưu request body/token vào log.
- Evidence chỉ có văn bản. Không có public/static route cho evidence, không trả
  file_path. Summary/list không chứa evidence. Lỗi validation không lặp input.
- Mọi response có Cache-Control: no-store. Claim không liên quan và không tồn tại
  cùng 404 CLAIM_NOT_FOUND; admin không có quyền xem toàn bộ.
- Ba PATCH approve/reject/complete vẫn là thiết kế cho đợt sau; Swagger chỉ công bố
  ba API đã chạy. Bảng Returns chỉ phục vụ đọc metadata tương thích.

Có thể phát triển với DATABASE_URL=sqlite:///./findback.db; kiểm chứng cạnh tranh
phải dùng PostgreSQL. Server không tự tạo bảng; schema thay đổi qua Alembic.
