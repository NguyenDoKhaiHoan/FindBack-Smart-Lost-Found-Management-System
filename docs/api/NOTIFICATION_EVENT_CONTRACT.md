# Notification Event Contract – Internal Service Interface

- **Jira:** KAN-30 / KAN-32 / KAN-34
- **Module sở hữu:** TV5 – Notifications & Admin
- **Phạm vi:** Interface nội bộ tạo thông báo trong ứng dụng từ sự kiện nghiệp vụ của các module (Claims, Posts, Matching)
- **Trạng thái:** Chuẩn hóa kỹ thuật (KAN-34) – Các quy tắc nghiệp vụ Claims đang ghi nhận **TBD (Cần Claims Owner xác nhận)**
- **Kiến trúc:** Modular Monolith – Giao tiếp qua Python Service Dependency Injection, không qua HTTP hay message broker ngoài

---

## 1. Mục tiêu và Nguyên tắc Kỹ thuật

Module Notifications cung cấp giao diện nội bộ chuẩn hóa (`NotificationService.create_notification`) để các module nghiệp vụ phát sinh thông báo khi có các sự kiện trong hệ thống.

### Nguyên tắc bắt buộc:
1. **Module phát sinh nghiệp vụ chịu trách nhiệm tạo sự kiện:** Module phát sinh hành động (Posts, Claims, Returns) chủ động gọi `NotificationService`. Module Notifications không tự động suy diễn logic nghiệp vụ của module khác.
2. **Không trùng lặp cơ chế (No Dual Writers):** Toàn bộ thông báo được tạo bởi Python Application Service. **Không sử dụng PostgreSQL Database Trigger** để tạo notification (tránh side-effect ẩn trong database).
3. **Không tạo Model/Service thứ hai:** Mọi module bắt buộc dùng chung model `Notification` và service `NotificationService` từ `app.modules.notifications_admin`.
4. **Phạm vi thông báo:** Chỉ tạo thông báo lưu trữ trong ứng dụng (In-app Notifications). Không triển khai gửi email/SMS/push trong phạm vi hiện tại.
5. **Bảo vệ dữ liệu nhạy cảm (PRIV-01):** Tuyệt đối **không** đưa bằng chứng sở hữu riêng tư (private claim evidence), mật khẩu, token, secret, hoặc dữ liệu định danh cá nhân (CCCD, thẻ ngân hàng) vào `title`, `message` hay `metadata`.
6. **Quản lý Transaction (Transaction Ownership):** Khi gọi trong chu trình nghiệp vụ có nhiều bước (ví dụ: cập nhật Claim + tạo Notification), caller bắt buộc truyền `auto_commit=False` để đảm bảo tính nguyên tử (Atomicity).

---

## 2. Interface Dịch vụ Nội bộ (`NotificationService`)

### 2.1. Cấu trúc Schema đầu vào (`NotificationCreateInternal`)
Định nghĩa tại [`app/modules/notifications_admin/schemas/notification.py`](file:///c:/Users/GF63/OneDrive/Tài%20li%C3%AA%CC%A3u/Th%E1%BB%B1c%20t%E1%BA%ADp%20FPT/FindBack/FindBack-Smart-Lost-Found-Management-System/backend/app/modules/notifications_admin/schemas/notification.py):

| Thuộc tính | Kiểu dữ liệu | Bắt buộc | Ràng buộc / Ý nghĩa |
| :--- | :--- | :---: | :--- |
| `recipient_id` | `uuid.UUID` | Có | UUID của người nhận thông báo; bắt buộc là tài khoản tồn tại và có `status == "ACTIVE"` |
| `event_type` | `string` | Có | Tên sự kiện hợp lệ từ enum `NotificationEventType` |
| `title` | `string` | Có | Tiêu đề hiển thị ngắn gọn (`1 <= len <= 255`) |
| `message` | `string` | Có | Nội dung chi tiết thông báo hiển thị cho người dùng (`>= 1 ký tự`) |
| `resource_type` | `string \| None` | Không | Loại tài nguyên liên kết: `POST`, `CLAIM`, `RETURN`, `REPORT`, `MATCH` |
| `resource_id` | `uuid.UUID \| None` | Không | UUID của tài nguyên tương ứng |
| `metadata` | `dict[str, Any] \| None` | Không | Từ điển chứa thông tin bổ sung; tự động được lọc qua bộ lọc bảo mật Allowlist |
| `event_id` | `uuid.UUID \| None` | Không | UUID sự kiện dùng để chống tạo trùng / đảm bảo tính lũy thừa (Deduplication) |

### 2.2. Method Signature
```python
from sqlalchemy.ext.asyncio import AsyncSession
from app.modules.notifications_admin.models.notification import Notification
from app.modules.notifications_admin.schemas.notification import NotificationCreateInternal

class NotificationService:
    async def create_notification(
        self,
        session: AsyncSession,
        data: NotificationCreateInternal,
        auto_commit: bool = True,
    ) -> Notification:
        ...
```

---

## 3. Danh mục Sự kiện (Event Catalog)

Bảng dưới đây thống kê toàn bộ 6 sự kiện cốt lõi được định nghĩa trong hệ thống:

| Event Type | Module phát sinh | Người nhận (`recipient_id`) | Resource Type | Trạng thái tích hợp |
| :--- | :--- | :--- | :--- | :--- |
| **`POST_HIDDEN`** | `posts` (hoặc `notifications_admin`) | Tác giả bài đăng (`post.user_id`) | `POST` | **ĐÃ TRIỂN KHAI & VERIFIED** (KAN-32/33) |
| **`CLAIM_CREATED`** | `claims_returns` | **TBD** (Đề xuất: Tác giả bài đăng) | `CLAIM` | **NOT VERIFIED** (Chờ Claims Owner xác nhận) |
| **`CLAIM_APPROVED`** | `claims_returns` | **TBD** (Đề xuất: Người gửi yêu cầu nhận lại đồ) | `CLAIM` | **NOT VERIFIED** (Chờ Claims Owner xác nhận) |
| **`CLAIM_REJECTED`** | `claims_returns` | **TBD** (Đề xuất: Người gửi yêu cầu nhận lại đồ) | `CLAIM` | **NOT VERIFIED** (Chờ Claims Owner xác nhận) |
| **`RETURN_REQUESTED`** | `claims_returns` | **TBD** (Đề xuất: Bên nhận/bên trả theo workflow) | `RETURN` | **NOT VERIFIED** (Chờ Claims Owner xác nhận) |
| **`RETURN_COMPLETED`** | `claims_returns` | **TBD** (Đề xuất: Các bên liên quan hoàn tất trả đồ) | `RETURN` | **NOT VERIFIED** (Chờ Claims Owner xác nhận) |

> [!IMPORTANT]
> **Quy định đối với Module Claims:**
> Vì module `backend/app/modules/claims_returns/` hiện tại chỉ chứa các file placeholder `.gitkeep` và chưa có mã nguồn nghiệp vụ, người phụ trách module Claims bắt buộc phải:
> 1. Xác nhận chính thức danh tính người nhận (`recipient_id`) cho từng sự kiện.
> 2. Tuyệt đối không tự suy đoán logic nếu quy trình trả đồ có nhiều bên liên quan.
> 3. Kế thừa chuẩn `uuid.UUID` cho toàn bộ các trường ID.

---

## 4. Bảo mật Metadata & Cơ chế Lọc Đệ quy (Allowlist Sanitization)

Hàm `NotificationService.sanitize_metadata` tự động thực hiện thanh lọc an toàn (Security Rule PRIV-01) trước khi ghi vào cột `metadata_json` (JSONB) của PostgreSQL:

### 4.1. Allowlist các khóa gốc (Root Keys được phép lưu):
Chỉ những key sau mới được giữ lại ở root level:
```python
ALLOWED_METADATA_KEYS = {
    "resource_type",
    "resource_id",
    "post_id",
    "claim_id",
    "return_id",
    "category_id",
    "action",
    "public_reference",
    "reference_code",
    "item_name",
}
```

### 4.2. Từ khóa bị cấm (Forbidden Keywords - Substring Check):
Bất kỳ key hoặc chuỗi ký tự nào ở bất kỳ cấp độ lồng nhau (nested dict/list) chứa các từ khóa sau sẽ bị loại bỏ hoàn toàn:
- `password`, `password_hash`
- `token`, `access_token`, `refresh_token`, `jwt`, `authorization`
- `secret`, `api_key`
- `evidence`, `private_evidence`, `private_content`
- `id_card`, `credit_card`, `ssn`

---

## 5. Cơ chế Chống Tạo Trùng Lặp (Deduplication / Idempotency)

- Bảng `notifications` có ràng buộc duy nhất trên cột `event_id`:
  ```sql
  CONSTRAINT uq_notifications_event_id UNIQUE (event_id)
  ```
- **Quy tắc sinh `event_id`:**
  - Đối với các thao tác có khả năng gọi lặp (retry, network timeout), module gọi nên sinh `event_id` theo thuật toán xác định (**UUIDv5**):
    ```python
    import uuid
    EVENT_NAMESPACE = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")
    event_id = uuid.uuid5(EVENT_NAMESPACE, f"{event_type}:{resource_id}:{recipient_id}")
    ```
- Khi xảy ra xung đột `event_id`, PostgreSQL thực thi `ON CONFLICT (event_id) DO NOTHING` hoặc `NotificationRepository.create_idempotent` tự động tái sử dụng bản ghi đã tồn tại, ngăn chặn hoàn toàn việc người dùng nhận 2 thông báo giống nhau cho cùng một sự kiện.

---

## 6. Hướng dẫn Tích hợp Mẫu (Code Walkthrough)

### 6.1. Tích hợp trong Nghiệp vụ Posts Moderation (Đã triển khai KAN-32)
```python
import uuid
from app.modules.notifications_admin.schemas.notification import NotificationCreateInternal
from app.modules.notifications_admin.services.notification_service import NotificationService

# 1. Khởi tạo service
notification_service = NotificationService()

# 2. Sinh event_id xác định
event_id = uuid.uuid5(uuid.NAMESPACE_OID, f"POST_HIDDEN:{post.id}")

# 3. Tạo payload thông báo
notification_data = NotificationCreateInternal(
    recipient_id=post.user_id,
    event_type="POST_HIDDEN",
    title="Bài đăng của bạn đã bị ẩn",
    message=f"Bài đăng '{post.title}' của bạn đã bị quản trị viên ẩn do: {reason}",
    resource_type="POST",
    resource_id=post.id,
    metadata={"post_id": post.id, "action": "HIDE"},
    event_id=event_id,
)

# 4. Gọi NotificationService với auto_commit=False (tham gia vào transaction của caller)
await notification_service.create_notification(
    session=session,
    data=notification_data,
    auto_commit=False,
)

# 5. Caller commit toàn bộ transaction sau khi hoàn tất các thao tác nghiệp vụ
await session.commit()
```

### 6.2. Hướng dẫn Mẫu dành cho Module Claims (Khi triển khai)
```python
# Ví dụ khi Claims Owner triển khai xử lý duyệt yêu cầu nhận đồ:
from app.modules.notifications_admin.schemas.notification import NotificationCreateInternal
from app.modules.notifications_admin.services.notification_service import NotificationService

async def approve_claim(session: AsyncSession, claim_id: uuid.UUID, claim_owner_id: uuid.UUID):
    # Cập nhật trạng thái claim...

    # Tạo thông báo cho người gửi claim
    event_id = uuid.uuid5(uuid.NAMESPACE_OID, f"CLAIM_APPROVED:{claim_id}")

    await notification_service.create_notification(
        session=session,
        data=NotificationCreateInternal(
            recipient_id=claim_owner_id,
            event_type="CLAIM_APPROVED",
            title="Yêu cầu nhận đồ của bạn đã được chấp thuận",
            message="Người nhặt được đồ đã xác nhận và chấp thuận yêu cầu nhận lại đồ của bạn.",
            resource_type="CLAIM",
            resource_id=claim_id,
            metadata={"claim_id": claim_id},
            event_id=event_id,
        ),
        auto_commit=False,  # BẮT BUỘC để rollback nếu thao tác phía sau thất bại
    )

    await session.commit()
```

---

## 7. Các Nội dung Cần Điều phối & Xác nhận

| Bên liên quan | Vấn đề cần xác nhận | Trạng thái hiện tại |
| :--- | :--- | :---: |
| **TV4 – Claims & Returns** | 1. Xác nhận danh sách sự kiện chính thức và người nhận tương ứng.<br>2. Cam kết truyền `auto_commit=False` khi nằm trong transaction.<br>3. Cam kết không đưa ảnh/bằng chứng sở hữu riêng tư vào metadata. | **PENDING CONFIRMATION** |
| **TV2 – Posts** | Xác nhận enum trạng thái `HIDDEN` và trường `moderated_by` đã đồng bộ với Posts schema. | **VERIFIED (KAN-32/33)** |
| **TV1 – Identity** | Xác nhận xác thực JWT Bearer và kiểm tra trạng thái user `ACTIVE`. | **VERIFIED (KAN-31/33)** |
