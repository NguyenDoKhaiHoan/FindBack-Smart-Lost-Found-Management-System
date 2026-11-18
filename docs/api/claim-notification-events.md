# Sự kiện Claims và Returns

`backend/app/modules/claims_returns/services/events.py` tạo audit, outbox và thông báo trong ứng dụng cùng giao dịch với thay đổi nghiệp vụ. Khóa duy nhất `event_id` liên kết thông báo với sự kiện. Người nhận có thể đọc thông báo qua `GET /api/v1/notifications` sau commit.

| type | Điều kiện | recipient_id |
| --- | --- | --- |
| claim.created | Tạo claim và bằng chứng ban đầu | Chủ tin FOUND |
| claim.evidence_added | Người gửi bổ sung bằng chứng cho claim PENDING | Chủ tin FOUND |
| claim.approved | Chủ tin duyệt claim | Người gửi claim |
| claim.rejected | Chủ tin từ chối claim | Người gửi claim |
| return.arranged | Chủ tin lập phiên trao trả | Người gửi claim |
| return.handed_over | Chủ tin ghi nhận đã giao đồ | Người gửi claim |
| claim.completed | Người gửi xác nhận nhận đồ và tin được đóng | Chủ tin FOUND |

Payload gồm `event_id`, `type`, `claim_id`, `found_post_id`, `recipient_id`, `version` và `occurred_at`. `version` là phiên bản của claim sau thao tác. Bằng chứng và ghi chú trao trả chỉ có trong các API giới hạn cho hai bên liên quan. [JSON Schema sự kiện](claim-notification-event.schema.json)
