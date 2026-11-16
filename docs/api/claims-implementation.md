# Bàn giao API tạo và xem Claims

Báo cáo đợt đầu cho ba API đọc/tạo. Ba API PATCH đã được triển khai trong
[đợt quyết định/trao trả](claims-decisions-implementation.md); xem báo cáo mới về
transaction, migration 0002, audit và sự kiện Notifications.

Đã triển khai ba operation của [contract](claims-contract.md):
`POST /api/v1/claims`, `GET /api/v1/claims/me`, `GET /api/v1/claims/{id}`.
Entrypoint: `backend/app/main.py:create_app`; xem [hướng dẫn chạy](../../backend/README.md).

## Kết quả kiểm tra ngày 16/11/2026

| Bằng chứng | Kết quả |
| --- | --- |
| Pytest trên PostgreSQL thật, schema tách riêng từng test, migration thật | 85 passed |
| Pytest trên SQLite tạm, migration thật | 80 passed, 5 test riêng PostgreSQL skipped |
| JSON Schema của contract sẵn có, kiểm UUID/timestamp | Response success/error hợp lệ trong suite |
| OpenAPI runtime qua openapi-spec-validator | Hợp lệ, đúng ba operation có BearerAuth |
| Ruff | Đạt |
| HTTP thực đến server Uvicorn + PostgreSQL local | 14 checks passed |
| GET /docs, JS/CSS Swagger local | HTTP 200 |

JUnit: `backend/.local/claims-postgres-tests.xml`, `backend/.local/claims-sqlite-tests.xml`
(gitignored). Có thể chạy lại bằng lệnh trong README backend.
Kết quả HTTP không có token/bằng chứng: `backend/.local/claims-live-checks.json`.
Server được giữ chạy tại http://127.0.0.1:8000/docs. Công cụ trình duyệt không khởi tạo
được và thao tác mở bằng Windows bị tự động chặn với lý do "blocked by policy";
chưa kiểm tra trực quan trong trình duyệt.

## Bằng chứng quyền và giao dịch

| Kịch bản | Assertion đã kiểm chứng |
| --- | --- |
| User hoạt động + FOUND hợp lệ | 201 PENDING, version=1, claimant từ JWT, Location đúng |
| Gửi actor/role/status/file_path trong body | 422 VALIDATION_ERROR, không echo input |
| Không token, sai chữ ký/thuật toán, hết hạn, sai issuer/audience, thiếu claims, User không tồn tại | 401 UNAUTHENTICATED + WWW-Authenticate |
| jti bị thu hồi hoặc token_version cũ | 401 UNAUTHENTICATED |
| Tài khoản khóa | 403 ACCOUNT_FORBIDDEN |
| Tự claim | 403 SELF_CLAIM_FORBIDDEN |
| Tin LOST / không có, ẩn, xóa mềm / đóng | 422 POST_TYPE_NOT_FOUND / 404 POST_NOT_FOUND / 409 POST_NOT_CLAIMABLE |
| PENDING hoặc APPROVED cùng cặp User/Post | 409 DUPLICATE_ACTIVE_CLAIM |
| Có APPROVED hoặc RETURNED trên Post | 409 POST_ALREADY_ASSIGNED, không lộ claim thắng |
| Claim trước REJECTED | Cho tạo ID mới, giữ lịch sử |
| /me với từng relation/status/page | Lọc tại DB trước phân trang, thứ tự ổn định, không evidence |
| Claimant/chủ tin xem detail | 200, chỉ evidence của claim đó |
| Người ngoài, claimant cạnh tranh, admin không liên quan | Cùng 404 như claim không tồn tại; không query evidence |
| file_path cũ trong DB | Không xuất hiện trong response |
| Hai POST đồng thời trên PostgreSQL | Một 201, một 409; một Claim/Evidence/audit/outbox |
| Unique violation do writer bỏ qua check ban đầu | Ánh xạ constraint có tên thành đúng 409 |
| FK User/Post sai | PostgreSQL chặn, SQLSTATE 23503 |
| Ghi evidence/audit/outbox lỗi | 500 đã làm sạch, rollback mọi bảng; không secret trong log |
| IntegrityError không nhận diện | 500, không giả thành lỗi trùng 409 |

Mã kiểm chứng: `backend/tests/api/test_claims.py`,
`backend/tests/integration/test_claims_postgres.py`.
Assertion schema dựa trên `docs/api/claims.openapi.json` có sẵn, độc lập với DTO triển khai.

## Phạm vi tích hợp

Schema `findback_api` mới dùng UUID với FK User/Post thực. Identity/Posts là adapter
tối thiểu phục vụ Claims, chưa phải module đăng nhập/đăng tin hoàn chỉnh.
Không tự nhập hoặc thay đổi SQL nháp/dữ liệu có sẵn; schema BIGINT trong
`outputs/findback.sql` chưa nối vào API UUID. Upload/download evidence và worker
thông báo vẫn ngoài phạm vi; ba PATCH được bàn giao ở báo cáo đợt tiếp theo nêu trên.

Nguồn kỹ thuật đã đối chiếu: [FastAPI JWT](https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/)
và [SQLAlchemy PostgreSQL partial indexes](https://docs.sqlalchemy.org/en/20/dialects/postgresql.html#partial-indexes).
