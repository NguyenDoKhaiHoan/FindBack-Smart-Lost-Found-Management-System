# Notification Event Contract – Internal Service Interface

- **Jira:** KAN-30
- **Module sở hữu:** TV5 – Notifications/Admin
- **Phạm vi:** Interface nội bộ tạo notification từ sự kiện nghiệp vụ Claims/Posts
- **Trạng thái:** Draft – các event và interface liên module cần xác nhận

> Đây là hợp đồng giao tiếp nội bộ giữa các module trong Modular Monolith. Không phải HTTP API và không tạo endpoint công khai mới.

## 1. Mục tiêu và nguyên tắc

Notification module cung cấp một interface thống nhất để module nghiệp vụ yêu cầu tạo thông báo trong ứng dụng.

Nguyên tắc:

1. Module phát sinh nghiệp vụ (Claims, Posts, Returns...) xác định sự kiện và người nhận theo quy tắc nghiệp vụ của chính module đó.
2. Module Notifications chịu trách nhiệm kiểm tra dữ liệu notification, áp dụng quy tắc bảo mật và lưu notification.
3. Không gọi router của module khác từ service.
4. Không tự tạo lại `User` hoặc `Post` model thuộc module khác.
5. Không gửi notification qua email/SMS/push trong MVP; chỉ lưu thông báo trong ứng dụng.
6. Không đưa token, mật khẩu, bằng chứng sở hữu hoặc dữ liệu nhạy cảm vào title, message hay metadata.
7. Một sự kiện chỉ được một cơ chế chịu trách nhiệm tạo notification; phải tránh tạo trùng giữa PostgreSQL trigger và Python service.

## 2. Interface nội bộ đề xuất

Tên protocol và method dưới đây là đề xuất cho contract; cần thống nhất với quy ước code của nhóm trước khi triển khai.

```python
from typing import Protocol


class NotificationServiceProtocol(Protocol):
    async def create_notification(
        self,
        *,
        recipient_id: int,
        event_type: str,
        title: str,
        message: str,
        resource_type: str | None = None,
        resource_id: str | None = None,
        metadata: dict[str, object] | None = None,
        idempotency_key: str | None = None,
    ) -> "Notification":
        ...
```

### 2.1. Thông tin đầu vào

| Field | Kiểu đề xuất | Bắt buộc | Ý nghĩa / validation |
|---|---|---:|---|
| `recipient_id` | `int` | Có | ID người nhận; phải tham chiếu user hợp lệ theo schema và policy hiện hành |
| `event_type` | `str` | Có | Mã sự kiện nằm trong danh sách đã được thống nhất |
| `title` | `str` | Có | Tiêu đề hiển thị; không chứa dữ liệu bí mật |
| `message` | `str` | Có | Nội dung thông báo; không chứa bằng chứng riêng tư/token |
| `resource_type` | `str \| None` | Không | Loại tài nguyên liên quan, phải thuộc allowlist đã thống nhất |
| `resource_id` | `str \| None` | Không | ID tài nguyên dạng chuỗi theo schema hiện có |
| `metadata` | `dict \| None` | Không | Chỉ chứa key/value trong allowlist; mặc định không đưa vào API response |
| `idempotency_key` | `str \| None` | Không | Khóa chống tạo trùng nếu nhóm triển khai cơ chế này; schema SQL hiện tại cần xác nhận có hỗ trợ lưu khóa hay không |

`Notification` là kiểu trả về khái niệm. Model thực tế thuộc module Notifications/Admin và phải khớp schema database đã được nhóm chốt.

## 3. Schema PostgreSQL tham chiếu

Theo báo cáo kiểm tra `findback.sql`, bảng `notifications` hiện được mô tả với các cột:

- `id`
- `recipient_id`
- `type`
- `title`
- `message`
- `metadata`
- `resource_type`
- `resource_id`
- `post_id`, `claim_id`, `return_id`, `report_id`, `match_id`
- `is_read`
- `read_at`
- `created_at`

Ràng buộc được báo cáo:

- `recipient_id` tham chiếu `users(id)` với `ON DELETE CASCADE`.
- Index theo `(recipient_id, created_at DESC)`.
- Partial index cho notification chưa đọc.
- Trigger `trg_notifications_guard` xử lý liên kết resource FK và trạng thái `read_at`.

Đây là schema tham chiếu từ SQL được kiểm tra, không phải quyết định rằng file SQL đó đã được nhóm phê duyệt làm baseline migration. Cần xác nhận với người phụ trách database trước KAN-31.

## 4. Event catalog

### 4.1. Sự kiện có thể cân nhắc

| Event type đề xuất | Nguồn | Người nhận dự kiến | Trạng thái |
|---|---|---|---|
| `POST_HIDDEN` | Posts moderation | Chủ bài đăng bị ẩn | Đề xuất; cần TV2 xác nhận |
| `CLAIM_CREATED` | Claims | Chủ bài đăng liên quan | Cần đối chiếu trigger hiện có và TV4 |
| `CLAIM_APPROVED` | Claims | Người gửi claim | Cần TV4 xác nhận |
| `CLAIM_REJECTED` | Claims | Người gửi claim | Cần TV4 xác nhận |
| `RETURN_ARRANGED` | Returns | Các bên liên quan theo workflow | Cần TV4 xác nhận |
| `SYSTEM_NOTICE` | Hệ thống | Người nhận được chỉ định hợp lệ | Đề xuất; cần thống nhất phạm vi sử dụng |

Tên event trong bảng là mã đề xuất hoặc ví dụ để thảo luận, không khẳng định trigger hiện tại phát đúng các mã này.

### 4.2. Cơ chế đang tồn tại cần lưu ý

Theo kết quả kiểm tra SQL:

- `trg_claims_notify`, `trg_returns_notify`, `trg_reports_notify` gọi `public.notify_workflow()`.
- Các trigger này được báo cáo là tạo notification khi Claim tạo/cập nhật, Return cập nhật, Report tạo mới/cập nhật.
- Chưa thấy trigger cho sự kiện Posts moderation `POST_HIDDEN`.

Vì vậy, trước khi triển khai:

1. Không để Python NotificationService tạo thêm notification cho cùng sự kiện đã được trigger xử lý.
2. Với `POST_HIDDEN`, có thể dùng internal service nếu TV2 và nhóm database thống nhất.
3. Nếu nhóm muốn chuyển toàn bộ việc tạo notification sang application service, phải có quyết định rõ ràng về việc tắt/bỏ trigger và migration tương ứng; không tự ý làm trong KAN-30.

## 5. Recipient resolution

- Module phát sinh event chịu trách nhiệm xác định người nhận dựa trên nghiệp vụ và truyền `recipient_id`.
- NotificationService kiểm tra recipient hợp lệ theo schema/quan hệ dữ liệu và quy ước của nhóm.
- Không nhận `recipient_id` từ request công khai của client để tạo thông báo tùy ý.
- Không suy luận recipient từ nội dung message.
- Ví dụ `POST_HIDDEN`: TV2 xác định chủ bài đăng từ Post; sau đó gửi ID chủ bài đăng vào interface.
- Ví dụ `CLAIM_CREATED`: TV4 xác định chủ bài đăng/người nhận phù hợp theo claim; phải thống nhất với TV4 và trigger hiện có.

## 6. Metadata allowlist và bảo mật

Metadata chỉ được chứa dữ liệu định danh tài nguyên hoặc dữ liệu hiển thị không nhạy cảm đã được nhóm cho phép.

Allowlist tối thiểu đề xuất:

| Key | Ý nghĩa | Trạng thái |
|---|---|---|
| `resource_type` | Loại tài nguyên liên quan | Có thể dùng nếu trùng schema và allowlist |
| `resource_id` | ID tài nguyên liên quan | Có thể dùng nếu trùng schema và allowlist |
| `post_id` | ID bài đăng | Cần xác nhận kiểu và mục đích |
| `claim_id` | ID claim | Cần xác nhận kiểu và mục đích |

Không được đưa vào metadata hoặc message:

- Token, access token, refresh token, session secret.
- Mật khẩu, password hash, thông tin đăng nhập.
- Ảnh hoặc nội dung bằng chứng sở hữu riêng tư.
- Đặc điểm bí mật dùng để xác minh quyền sở hữu.
- Thông tin cá nhân không cần thiết để hiển thị thông báo.
- Nội dung nội bộ chỉ dành cho người có quyền xem bằng chứng.

Nếu cần hiển thị chi tiết nhạy cảm, người dùng phải truy cập tài nguyên qua API có kiểm tra quyền riêng; notification chỉ nên chứa nội dung thông báo an toàn và tham chiếu tài nguyên.

## 7. Quy tắc chống tạo trùng

Đây là yêu cầu bắt buộc vì database SQL hiện tại đã có trigger tạo notification cho Claims/Returns/Reports.

Quy tắc:

1. Lập bảng mapping `event -> producer -> notification writer` trước khi tích hợp.
2. Với event đã được PostgreSQL trigger tạo notification, Python service không tạo notification lần thứ hai.
3. Với event chưa có trigger (ví dụ `POST_HIDDEN` theo kết quả kiểm tra hiện tại), application service chỉ tạo khi module sở hữu xác nhận.
4. Nếu cần idempotency ở tầng ứng dụng, phải thống nhất cách lưu khóa idempotency và unique constraint/migration. Không giả định cột `idempotency_key` đã tồn tại trong bảng hiện tại.
5. Việc retry event không được tạo bản ghi lặp ngoài chủ đích.

Mapping hiện tại ở mức sơ bộ:

| Nhóm event | Cơ chế được báo cáo | Hành động KAN-30 |
|---|---|---|
| Claims | PostgreSQL trigger `notify_workflow()` | Không tạo thêm bằng Python cho đến khi thống nhất chuyển cơ chế |
| Returns | PostgreSQL trigger `notify_workflow()` | Không tạo thêm bằng Python cho đến khi thống nhất chuyển cơ chế |
| Reports | PostgreSQL trigger `notify_workflow()` | Không tạo thêm bằng Python cho đến khi thống nhất chuyển cơ chế |
| Posts moderation | Chưa thấy trigger tương ứng trong SQL được kiểm tra | Đề xuất internal service cho `POST_HIDDEN`, chờ TV2/database xác nhận |
| System notice | Chưa xác định | Chỉ triển khai sau khi thống nhất use case và quyền gọi |

## 8. Transaction và xử lý lỗi

- Notification cần được lưu bền vững trong PostgreSQL.
- Khi notification là một phần của use case nghiệp vụ (ví dụ moderation), nhóm phải thống nhất transaction boundary để trạng thái nghiệp vụ và notification không rơi vào trạng thái lệch nhau.
- Không tự mở transaction độc lập trong repository nếu use case/service cấp trên đang sở hữu transaction boundary theo kiến trúc dự án.
- Nếu DB trigger là writer, lỗi trigger nằm trong transaction của thao tác nghiệp vụ tương ứng; cách xử lý lỗi phải tuân theo quyết định database/integration.
- Nếu application service là writer, caller cần biết notification failure có làm rollback use case hay được xử lý qua cơ chế khác. Đây là quyết định cần chốt, không tự mặc định.

## 9. Ví dụ tích hợp nội bộ (minh họa, chưa phải code triển khai)

### 9.1. Posts moderation

```python
# Pseudocode: TV2 Posts service sau khi moderation thành công.
# Chỉ gọi khi TV2 và nhóm database xác nhận application service là writer
# cho event POST_HIDDEN.

await notification_service.create_notification(
    recipient_id=post.owner_id,
    event_type="POST_HIDDEN",
    title="Bài đăng của bạn đã bị ẩn",
    message="Một bài đăng của bạn đã được quản trị viên ẩn.",
    resource_type="POST",
    resource_id=str(post.id),
    metadata={"post_id": post.id},
)
```

### 9.2. Claims event

```python
# Pseudocode: TV4 Claims service.
# Không gọi đoạn này nếu PostgreSQL trigger hiện tại đã tạo notification
# cho cùng một event. Cần TV4/database xác nhận writer trước khi tích hợp.

await notification_service.create_notification(
    recipient_id=post_owner_id,
    event_type="CLAIM_CREATED",
    title="Bạn có yêu cầu nhận đồ mới",
    message="Có người đã gửi yêu cầu nhận đồ trong bài đăng của bạn.",
    resource_type="CLAIM",
    resource_id=str(claim.id),
    metadata={"claim_id": claim.id},
)
```

## 10. Các nội dung cần xác nhận liên module

| Module/nhóm | Cần xác nhận |
|---|---|
| TV1 – Identity | Kiểu ID user; trạng thái user hợp lệ; cách dependency xác thực được inject vào service/route |
| TV2 – Posts | Cách lấy owner ID; event moderation; thời điểm phát event; service/hàm moderation; transaction boundary |
| TV4 – Claims/Returns | Danh sách event; recipient cho từng event; mapping với trigger `notify_workflow()`; event nào không còn do trigger tạo |
| Database/Integration | `findback.sql` có phải schema baseline; trigger có giữ lại không; migration strategy; idempotency strategy |
| TV5 – Notifications/Admin | Event catalog chính thức; metadata allowlist; nội dung thông báo an toàn; cách xử lý lỗi |

## 11. Ngoài phạm vi KAN-30

- Không triển khai Python service hoặc model.
- Không sửa trigger/function PostgreSQL.
- Không tạo hoặc chạy SQL.
- Không tạo Alembic migration.
- Không thay đổi module Claims, Posts hoặc Identity.
- Không thêm HTTP endpoint công khai.
- Không commit hoặc push Git.

---

**Trạng thái:** Draft chờ xác nhận liên module. Không xem các event đề xuất là event đã được triển khai hoặc đã được các module khác chấp thuận.
