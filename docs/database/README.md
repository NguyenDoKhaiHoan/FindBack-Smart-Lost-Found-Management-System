# Dữ liệu dự kiến

PostgreSQL, SQLAlchemy và Alembic được đề xuất trong phân tích. Đây là danh sách bảng/thuộc tính sơ bộ, chưa phải schema thực thi hay ERD đã chốt.

| Bảng | Dữ liệu chính |
| --- | --- |
| `users` | id, email, password_hash, role, status |
| `posts` | id, user_id, type, category_id, title, description, location, event_time, status |
| `post_images` | id, post_id, file_path |
| `categories` | id, name |
| `matches` | id, lost_post_id, found_post_id, score, explanation |
| `claims` | id, found_post_id, claimant_id, status, created_at |
| `claim_evidence` | id, claim_id, private_content, file_path |
| `returns` | id, claim_id, status, confirmed_at |
| `notifications` | id, user_id, type, is_read |
| `reports` | id, reporter_id, post_id, reason, status |
| `audit_logs` | id, actor_id, action, entity_id, timestamp |

## Quan hệ cần biểu diễn trong ERD

- User có nhiều posts, claims, notifications, reports và audit logs.
- Category có nhiều posts; post có nhiều post_images.
- Match liên kết một LOST post và một FOUND post.
- Claim liên kết FOUND post với người gửi; claim có bằng chứng và phiên trao trả theo chính sách sẽ chốt.
- Report liên kết người báo cáo với post được báo cáo.
- Audit log liên kết actor với thực thể/hành động; cần bổ sung cách xác định loại thực thể.

## Ràng buộc cần thiết kế

- Khóa chính, khóa ngoại, nullability, kiểu ID, timestamp/timezone và chính sách xóa mềm.
- Unique email theo quy tắc chuẩn hóa thống nhất; mật khẩu chỉ lưu dạng hash.
- Check/enum cho loại tin, role và trạng thái; không xem các tên trạng thái chưa chốt là giá trị mặc định.
- Không trùng cặp LOST–FOUND; index phục vụ danh mục, khu vực, thời gian và trạng thái theo cách truy vấn thực tế.
- Chống claim trùng đang mở và xử lý cạnh tranh phê duyệt bằng constraint/locking phù hợp trong transaction.
- Tạo return chỉ khi claim hợp lệ; chốt số phiên trao trả và điều kiện xác nhận để tránh bàn giao nhiều lần.
- Chốt metadata của file, chính sách truy cập bằng chứng, lưu trữ lịch sử và vòng đời dữ liệu.

Không tạo migration từ bảng sơ bộ này trước khi thống nhất các quy tắc tại [requirements.md](../requirements.md). Migration tương lai đặt ở `backend/alembic/versions/`; dữ liệu seed chỉ dùng dữ liệu demo giả.
