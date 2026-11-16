# Bàn giao API quyết định và xác nhận trao trả

Đã triển khai:

| API | Actor | Điều kiện và kết quả |
| --- | --- | --- |
| PATCH /api/v1/claims/{id}/approve | Chủ tin, khác claimant | PENDING + evidence hợp lệ → APPROVED, version + 1 |
| PATCH /api/v1/claims/{id}/reject | Chủ tin, khác claimant | PENDING → REJECTED, trim reason, version + 1 |
| PATCH /api/v1/claims/{id}/complete | Claimant | APPROVED + Return HANDED_OVER + receipt_confirmed=true → RETURNED/CONFIRMED/CLOSED |

Contract HTTP giữ nguyên tại [claims-contract.md](claims-contract.md) và
[claims.openapi.json](claims.openapi.json). Swagger runtime công bố đủ sáu API tại
http://127.0.0.1:8000/docs.

## Transaction và thứ tự kiểm tra

Xác thực JWT và User → tìm parent Post theo quan hệ đọc → khóa Post → khóa Claim →
kiểm tra lại quan hệ/quyền → state → expected_version → điều kiện nghiệp vụ.
Complete khóa Return sau Claim. Người ngoài/admin không liên quan nhận 404 như claim
không tồn tại; claimant tự approve/reject hoặc chủ tin complete nhận 403.

UPDATE Claim có điều kiện id + status + version, tăng version đúng một lần.
UPDATE Return có điều kiện HANDED_OVER, chưa có xác nhận và đã có thời điểm giao.
Return phải được giao sau lúc approve và trước lúc xác nhận. Tất cả thời gian/actor
xác nhận do server ghi; returned_at = confirmed_at = updated_at.

Complete gọi service Posts trong cùng session; đánh dấu Post CLOSED với
completed_claim_id và completed_at. Post đã đóng vì lý do khác, đã bị ẩn/xóa mềm,
không phải FOUND hoặc gắn claim khác trả POST_STATE_CONFLICT và rollback cả Return.
Cờ đóng nhất quán của chính claim được giữ nguyên theo contract.

Approve không đóng Post, không tạo Return và không tự reject claim cạnh tranh.
Reject được xử lý claim PENDING tồn đọng trên tin đã đóng/ẩn hoặc có người thắng.
Complete không tạo Return hay tự giả lập bước giao đồ. Chưa có endpoint lập lịch/
ghi HANDED_OVER trong phạm vi sáu API; module Returns phải cung cấp dữ liệu đó.

Khóa Post nối tiếp mọi quyết định trên cùng món đồ. Partial unique index vẫn chặn
nhiều APPROVED/RETURNED trên cùng Post. PATCH lặp/sai state trả CLAIM_STATE_CONFLICT,
stale version trả CLAIM_VERSION_CONFLICT; state được kiểm tra trước version.
Deadlock/serialization failure chỉ retry toàn bộ transaction tối đa ba lần;
mọi lỗi khác rollback và trả lỗi server đã làm sạch.

Audit lưu actor/action/claim/post/version trước-sau/thời gian. Cùng transaction ghi
[sự kiện Notifications vào outbox](claim-notification-events.md), đúng người nhận,
không evidence/reason. Worker gửi thông báo là phần tích hợp ngoài producer này.

## Migration và kiểm tra

Kết quả ngày 16/11/2026:

| Kiểm chứng | Kết quả |
| --- | --- |
| Full suite trên PostgreSQL thật | 205 passed, 0 failed |
| Full suite trên SQLite tạm | 196 passed, 9 test chỉ dành cho PostgreSQL skipped |
| HTTP đến Uvicorn + PostgreSQL | 15 checks passed; 5 audit và 5 outbox cho hai claim demo |
| Ba ca cạnh tranh có chờ khóa Post thật | Mỗi ca chỉ một 200, một 409, một audit/event quyết định |
| OpenAPI runtime | Hợp lệ qua openapi-spec-validator, đúng sáu operation |
| Swagger local | HTTP 200 |
| JSON Schema bàn giao Notifications | Các outbox event đã commit hợp lệ |
| Ruff, git diff --check | Đạt |

Không còn schema test bị bỏ lại sau suite. Báo cáo JUnit tại
`backend/.local/claims-decisions-postgres-tests.xml` và
`backend/.local/claims-decisions-sqlite-tests.xml` (gitignored).
Một cảnh báo deprecation của Starlette TestClient/httpx không làm thất bại kiểm thử.

`0002_claim_decisions` bổ sung Return.confirmed_by và marker hoàn tất trên Post,
FK và CHECK tương ứng. Không sửa migration 0001 hoặc nhập SQL nháp/schema BIGINT.
Upgrade/downgrade được kiểm tra khi đã có Post, Claim, Evidence và Return tham chiếu
nhau; dữ liệu được giữ nguyên. SQLite batch migration kiểm FK sau khi dựng lại bảng.

Mã kiểm chứng:

- `backend/tests/api/test_claim_decisions.py`: quyền, state, version, validation,
  metadata, recipient, rollback mọi bảng khi lỗi Return/Post/Claim/audit/outbox.
- `backend/tests/integration/test_claim_decision_transactions.py`: hai approve,
  approve/reject và hai complete bị buộc chờ trên cùng khóa Post thực của PostgreSQL;
  chỉ một thành công, một audit/event. Kiểm bounded retry và event chỉ thấy sau commit.
- `backend/tests/integration/test_claim_decision_migration.py`: migration với dữ liệu có sẵn.
- `backend/app/check_claim_decisions.py`: kiểm HTTP trên Uvicorn + PostgreSQL local,
  dùng dữ liệu hoàn toàn giả lập; bước HANDED_OVER chỉ là fixture development rõ ràng.

Lệnh chạy từ backend:

```powershell
uv run alembic upgrade head
uv run pytest -q --junitxml=.local/claims-decisions-sqlite-tests.xml
$env:TEST_DATABASE_URL = '<PostgreSQL test URL>'
uv run pytest --postgres -q --junitxml=.local/claims-decisions-postgres-tests.xml
uv run python -m app.seed_demo
uv run python -m app.check_claim_decisions
```

Test PostgreSQL dùng schema claims_test_<uuid> và xóa đúng schema riêng sau mỗi test.
Báo cáo HTTP: backend/.local/claims-decisions-live-checks.json; không có token/nội dung bí mật.
Chỉ bảo đảm một người thắng trên mỗi FOUND post, theo giả định một Post = một món đồ;
chống trùng giữa các post khác nhau cần item_id chung và contract riêng.

Nguồn đối chiếu: [SQLAlchemy conditional UPDATE](https://docs.sqlalchemy.org/en/20/orm/queryguide/dml.html#orm-update-and-delete-with-custom-where-criteria)
và [PostgreSQL row locks](https://www.postgresql.org/docs/17/explicit-locking.html#LOCKING-ROWS).
