# Sự kiện Claims bàn giao cho Notifications

Producer: `backend/app/modules/claims_returns/services/events.py`.
Schema dùng chung: `backend/app/modules/notifications_admin/schemas/claim_events.py`.
JSON Schema: [claim-notification-event.schema.json](claim-notification-event.schema.json).

| type | Điều kiện | recipient_id |
| --- | --- | --- |
| claim.created | Tạo Claim PENDING + Evidence thành công | Chủ FOUND post |
| claim.approved | Chủ tin chuyển PENDING → APPROVED | Claimant |
| claim.rejected | Chủ tin chuyển PENDING → REJECTED | Claimant |
| claim.completed | Claimant xác nhận Return HANDED_OVER → CONFIRMED, Claim RETURNED, Post CLOSED | Chủ FOUND post |

Payload chỉ có bảy trường sau; UUID và thời gian UTC đều do server tạo:

```json
{
  "event_id": "d87d686c-4523-4fbb-aa1b-d1df87ba91aa",
  "type": "claim.approved",
  "claim_id": "e4febae9-b2d0-4535-94b9-01ff7a42e2ca",
  "found_post_id": "55b40512-fcb0-5c7a-b84a-8ec95e3c058f",
  "recipient_id": "27725b81-2821-4d40-bde2-98302c729bb4",
  "version": 2,
  "occurred_at": "2026-11-16T03:00:00Z"
}
```

Mỗi sự kiện được ghi vào `findback_api.outbox_events` trong **cùng transaction** với
mutation và audit. `event_id` cũng là khóa chính outbox; `version` là version Claim
sau thao tác. Không có bằng chứng, đặc điểm bí mật, lý do từ chối hoặc token.

Notifications chỉ đọc sự kiện đã commit, dedupe bằng `event_id`, gửi đúng recipient
và quản lý retry/ack ở consumer. Thất bại gửi thông báo sau commit không được đảo
ngược Claim/Post. Không gọi email/push/broker trong transaction Claims.
Đợt bàn giao này triển khai producer/outbox và schema sự kiện; worker vận chuyển,
consumer và lưu trạng thái đã gửi thuộc module Notifications, chưa được triển khai.

Pytest PostgreSQL kiểm chứng một connection khác không thấy sự kiện trước commit,
thấy đúng một sự kiện sau commit; mọi lỗi audit/outbox và retry giao dịch không tạo
sự kiện thừa. PATCH lặp trả 409, không thêm audit hoặc outbox mới.
