# API Contract – Notifications/Admin

- **Jira:** KAN-30
- **Phạm vi:** Đặc tả 4 API Notifications/Admin
- **Trạng thái tài liệu:** Draft – cần xác nhận các mục `PENDING CONFIRMATION`
- **Base path dự kiến:** `/api/v1`
- **Backend:** FastAPI / PostgreSQL

> Tài liệu này là hợp đồng API ở mức thiết kế. Nó không khẳng định các endpoint đã được triển khai. Những chi tiết chưa có trong Jira hoặc tài liệu nền được đánh dấu là đề xuất hoặc cần xác nhận với module sở hữu.

## 1. Mục tiêu và phạm vi

Đặc tả đúng 4 endpoint:

1. `GET /api/v1/notifications`
2. `PATCH /api/v1/notifications/{id}/read`
3. `GET /api/v1/admin/posts`
4. `PATCH /api/v1/admin/posts/{id}/moderation`

Không bổ sung endpoint công khai khác trong KAN-30. Giao diện tạo thông báo từ sự kiện nghiệp vụ được mô tả riêng trong `NOTIFICATION_EVENT_CONTRACT.md`; đó là interface nội bộ, không phải HTTP endpoint.

## 2. Quy ước chung

### 2.1. Authentication

- Các endpoint đều yêu cầu người gọi đã đăng nhập.
- Danh tính người gọi phải lấy từ cơ chế xác thực chung của module Identity.
- Interface dự kiến từ Identity: dependency tương đương `get_current_active_user`, trả về user có tối thiểu `id`, `role`, `status`.
- Tên dependency, kiểu đối tượng và cách biểu diễn role/status: **PENDING CONFIRMATION WITH TV1 – IDENTITY**.
- User không được tự gửi `recipient_id` hoặc `actor_id` để thay thế danh tính lấy từ token.

### 2.2. Content-Type và thời gian

- Request/response JSON dùng `application/json`.
- Thời gian biểu diễn theo ISO 8601; dữ liệu lưu trữ dự kiến dùng `TIMESTAMPTZ` theo schema SQL hiện có.
- Ví dụ timestamp trong tài liệu dùng UTC (`Z`).

### 2.3. Phân trang

Đề xuất dùng chung:

| Parameter | Kiểu | Mặc định | Quy tắc đề xuất |
|---|---|---:|---|
| `page` | integer | 1 | `>= 1` |
| `limit` | integer | 20 | `1..100` |

Giới hạn tối đa `100` là đề xuất cần thống nhất với nhóm. Thứ tự mặc định đề xuất là mới nhất trước (`created_at DESC`), thêm khóa phụ `id DESC` để thứ tự ổn định.

Response phân trang đề xuất:

```json
{
  "items": [],
  "pagination": {
    "page": 1,
    "limit": 20,
    "total": 0,
    "total_pages": 0
  }
}
```

## 3. Ma trận phân quyền

| Vai trò | GET notifications | PATCH notification read | GET admin posts | PATCH moderation |
|---|---:|---:|---:|---:|
| Chưa đăng nhập | 401 | 401 | 401 | 401 |
| User đang hoạt động | Chỉ thông báo của mình | Chỉ thông báo của mình | 403 | 403 |
| Admin đang hoạt động | Chỉ thông báo của mình | Chỉ thông báo của mình | Cho phép | Cho phép |
| Tài khoản không hoạt động | Bị từ chối theo Identity policy | Bị từ chối theo Identity policy | Bị từ chối | Bị từ chối |

`Admin` vẫn chỉ xem/đánh dấu thông báo có `recipient_id` bằng ID của chính mình. Vai trò admin không mặc nhiên cho phép đọc thông báo của người khác.

## 4. API 1 – Lấy danh sách thông báo

`GET /api/v1/notifications`

### 4.1. Query parameters

| Tên | Kiểu | Bắt buộc | Mô tả |
|---|---|---:|---|
| `page` | integer | Không | Trang, mặc định `1` |
| `limit` | integer | Không | Số phần tử/trang, mặc định `20`, tối đa đề xuất `100` |
| `is_read` | boolean | Không | Lọc theo trạng thái đã đọc/chưa đọc; bỏ qua nếu không truyền |

Không hỗ trợ `recipient_id` từ client. Backend bắt buộc giới hạn truy vấn theo `recipient_id = current_user.id`.

### 4.2. Response `200 OK`

Schema item dựa trên các cột đã được báo cáo trong `findback.sql`:

```json
{
  "items": [
    {
      "id": 101,
      "type": "CLAIM_CREATED",
      "title": "Bạn có yêu cầu nhận đồ mới",
      "message": "Một người dùng đã gửi yêu cầu nhận đồ trong bài đăng của bạn.",
      "resource_type": "CLAIM",
      "resource_id": "25",
      "is_read": false,
      "read_at": null,
      "created_at": "2026-11-16T10:30:00Z"
    }
  ],
  "pagination": {
    "page": 1,
    "limit": 20,
    "total": 1,
    "total_pages": 1
  }
}
```

Quy tắc:

- Chỉ trả notification thuộc người dùng hiện tại.
- Không trả `metadata` trong response mặc định cho đến khi schema metadata được rà soát và allowlist được nhóm duyệt.
- Không trả bằng chứng sở hữu, token, thông tin xác thực hoặc dữ liệu riêng tư.
- Thứ tự mặc định đề xuất: `created_at DESC, id DESC`.

### 4.3. Lỗi có thể trả về

- `401`: chưa xác thực hoặc token không hợp lệ.
- `422`: query parameter sai kiểu hoặc ngoài giới hạn.

## 5. API 2 – Đánh dấu thông báo đã đọc

`PATCH /api/v1/notifications/{id}/read`

### 5.1. Path parameter

| Tên | Kiểu | Quy tắc |
|---|---|---|
| `id` | integer (BIGINT theo schema hiện có) | Phải là số nguyên dương |

Request body: không yêu cầu body.

### 5.2. Response `200 OK`

```json
{
  "id": 101,
  "is_read": true,
  "read_at": "2026-11-16T10:35:00Z"
}
```

Quy tắc:

- Backend lấy actor ID từ user đã xác thực.
- Chỉ cập nhật notification khi `recipient_id = current_user.id`.
- Gọi lặp lại phải idempotent: nếu notification đã đọc thì không làm sai trạng thái hoặc ghi nhận thời điểm đọc mới một cách không cần thiết.
- SQL hiện có được báo cáo là có hàm `public.mark_notification_read(p_notification_id, p_actor_id)` kiểm tra quyền sở hữu và idempotency. Cách backend sử dụng hàm này hay triển khai logic tương đương phải được thống nhất với người phụ trách database; không được đồng thời thực hiện hai cơ chế cập nhật độc lập.

### 5.3. Lỗi

| HTTP | Trường hợp |
|---|---|
| `401` | Chưa xác thực |
| `404` | Không tồn tại hoặc không thuộc người nhận hiện tại (đề xuất dùng cùng phản hồi để tránh tiết lộ tài nguyên của người khác) |
| `422` | ID sai định dạng hoặc không hợp lệ |

## 6. API 3 – Danh sách bài đăng dành cho Admin

`GET /api/v1/admin/posts`

### 6.1. Query parameters

| Tên | Kiểu | Bắt buộc | Mô tả |
|---|---|---:|---|
| `page` | integer | Không | Trang, mặc định `1` |
| `limit` | integer | Không | Số phần tử/trang, mặc định `20` |
| `status` | string | Không | Lọc theo trạng thái bài đăng đã được TV2 xác nhận |
| `type` | string | Không | Lọc loại bài đăng LOST/FOUND nếu đúng với model TV2 |
| `q` | string | Không | Từ khóa tìm kiếm; trường tìm kiếm và cách chuẩn hóa cần TV2 xác nhận |

Các trạng thái được thấy trong SQL/tài liệu hiện tại gồm `DRAFT`, `ACTIVE`, `HIDDEN`, `CLOSED`; cần xác nhận enum/model thực tế với TV2 trước khi khóa schema. Không tự suy ra thêm trạng thái.

### 6.2. Response `200 OK` – ví dụ minh họa

```json
{
  "items": [
    {
      "id": 25,
      "title": "Mất ví màu đen",
      "type": "LOST",
      "status": "ACTIVE",
      "created_at": "2026-11-16T09:00:00Z"
    }
  ],
  "pagination": {
    "page": 1,
    "limit": 20,
    "total": 1,
    "total_pages": 1
  }
}
```

Đây là response minh họa, không phải schema Post đã được xác nhận. TV2 cần cung cấp danh sách field được phép trả về, kiểu dữ liệu, trạng thái, enum loại tin và quy tắc lọc. Không trả thông tin bằng chứng riêng tư hoặc dữ liệu nhạy cảm.

### 6.3. Phân quyền và lỗi

- Chưa đăng nhập: `401`.
- Đã đăng nhập nhưng không có role admin: `403`.
- Query sai kiểu/không hợp lệ: `422`.

## 7. API 4 – Kiểm duyệt bài đăng

`PATCH /api/v1/admin/posts/{id}/moderation`

### 7.1. Path parameter và request body

`id`: ID bài đăng, số nguyên dương theo kiểu ID mà TV2 xác nhận.

Request body đề xuất cho phạm vi hiện được SQL hỗ trợ:

```json
{
  "action": "HIDE",
  "reason": "Tin đăng có nội dung vi phạm quy định."
}
```

- `action`: hiện chỉ đề xuất giá trị `HIDE`.
- `reason`: bắt buộc, sau khi trim không được rỗng; giới hạn độ dài cần thống nhất với TV2/database.
- Không tự thêm `APPROVE`, `RESTORE`, `UNHIDE` hoặc hành động khác vì SQL được kiểm tra hiện chỉ mô tả thao tác ẩn tin.

### 7.2. Response `200 OK` – ví dụ minh họa

```json
{
  "id": 25,
  "status": "HIDDEN",
  "moderated_by": 1,
  "moderation_reason": "Tin đăng có nội dung vi phạm quy định.",
  "moderated_at": "2026-11-16T11:00:00Z"
}
```

Tên field và response cuối cùng cần khớp model/response schema của TV2.

### 7.3. Quy tắc nghiệp vụ

Theo báo cáo kiểm tra SQL hiện có:

- `public.moderate_post(p_post_id, p_actor_id, p_reason)` kiểm tra quyền admin.
- Lý do kiểm duyệt là bắt buộc.
- Không cho ẩn bài có trạng thái `CLOSED`.
- Hành động ẩn chuyển trạng thái sang `HIDDEN` và lưu thông tin người kiểm duyệt, thời điểm, lý do.

Cần xác nhận với TV2 và nhóm database xem backend gọi hàm SQL này hay gọi service/repository Posts dùng chung. Không tạo logic cập nhật trạng thái song song, gây lệch dữ liệu.

### 7.4. Lỗi

| HTTP | Trường hợp |
|---|---|
| `400` | Hành động không hợp lệ hoặc không thể chuyển trạng thái theo quy tắc nghiệp vụ |
| `401` | Chưa đăng nhập |
| `403` | Không có role admin |
| `404` | Không tìm thấy bài đăng |
| `422` | Body/path sai định dạng hoặc thiếu `reason` |

Việc dùng `400` hay `409` cho xung đột trạng thái là điểm cần thống nhất với quy ước lỗi chung của dự án; Jira yêu cầu có mã lỗi cho hành động không hợp lệ nhưng chưa chốt chính xác status code.

## 8. Định dạng lỗi chung

Định dạng lỗi toàn dự án chưa được xác nhận. Hai phương án cần chọn thống nhất:

**Phương án A – FastAPI mặc định/tối giản:**

```json
{
  "detail": "Not authenticated"
}
```

**Phương án B – envelope có mã lỗi:**

```json
{
  "error": {
    "code": "FORBIDDEN",
    "message": "Bạn không có quyền thực hiện hành động này."
  }
}
```

**PENDING CONFIRMATION:** chọn một format chung với TV1 và nhóm tích hợp; không tự triển khai mỗi module một kiểu.

## 9. Audit logging

Các hành động moderation cần ghi nhận tối thiểu:

- Actor/user thực hiện.
- Action (ví dụ `POST_HIDDEN`).
- Resource type và resource ID.
- Thời điểm thực hiện.
- Kết quả và thông tin lý do theo chính sách audit log của nhóm.

TV5 phối hợp cấu trúc/vị trí audit log; service nghiệp vụ phát sinh hành động chịu trách nhiệm phát log theo kiến trúc dự án. Không ghi token, password, bằng chứng sở hữu hoặc payload nhạy cảm vào log.

## 10. Các xác nhận bắt buộc trước triển khai

| Chủ thể | Cần xác nhận |
|---|---|
| TV1 – Identity | Dependency user hiện tại; enum/format role và status; lỗi 401/403 chung |
| TV2 – Posts | Model Post; field response; enum type/status; bộ lọc `q`; service/hàm moderation; giới hạn reason; quy tắc audit |
| TV4 – Claims/Returns | Sự kiện nghiệp vụ và recipient; event nào đã được DB trigger tạo notification |
| Nhóm tích hợp/database | API prefix; error envelope; nguồn schema chuẩn; chiến lược trigger so với application service; migration baseline |

## 11. Ngoài phạm vi KAN-30

- Không triển khai code router/service/model.
- Không tạo hoặc chạy SQL.
- Không tạo Alembic migration.
- Không thêm endpoint mới.
- Không thay đổi schema Posts/Users/Claims.
- Không commit hoặc push Git.

---

**Trạng thái:** Draft chờ xác nhận liên module. Tài liệu này là đầu ra đặc tả KAN-30, không phải bằng chứng endpoint đã hoạt động.
