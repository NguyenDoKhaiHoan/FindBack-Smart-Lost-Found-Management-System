# API Contract – Notifications & Admin

- **Jira:** KAN-30 / KAN-32 / KAN-34
- **Phạm vi:** Đặc tả chuẩn hóa 4 API cốt lõi của Notifications và Admin Post Moderation
- **Trạng thái tài liệu:** Chuẩn hóa chính thức theo mã nguồn triển khai thực tế (KAN-34 Verified)
- **Base path:** `/api/v1`
- **Backend:** FastAPI 0.115+ / SQLAlchemy 2.0 Async / PostgreSQL 16
- **Định dạng khóa chính (ID):** RFC 4122 UUID (UUIDv4 / UUIDv5) trên toàn hệ thống

---

## 1. Mục tiêu và phạm vi

Tài liệu này đặc tả chính xác 4 endpoint API công khai:

1. `GET /api/v1/notifications` – Lấy danh sách thông báo người dùng theo phân trang và bộ lọc.
2. `PATCH /api/v1/notifications/{id}/read` – Đánh dấu thông báo đã đọc (idempotent, cô lập quyền sở hữu).
3. `GET /api/v1/admin/posts` – Lấy danh sách bài đăng hệ thống dành cho Quản trị viên (Admin).
4. `PATCH /api/v1/admin/posts/{id}/moderation` – Kiểm duyệt ẩn bài đăng vi phạm (Admin Moderation).

Giao tiếp nội bộ liên module (tạo thông báo từ Claims, Posts, Matching) được đặc tả riêng trong [`NOTIFICATION_EVENT_CONTRACT.md`](file:///c:/Users/GF63/OneDrive/Tài%20li%C3%AA%CC%A3u/Th%E1%BB%B1c%20t%E1%BA%ADp%20FPT/FindBack/FindBack-Smart-Lost-Found-Management-System/docs/api/NOTIFICATION_EVENT_CONTRACT.md).

---

## 2. Quy ước chung

### 2.1. Authentication & Authorization (RBAC)
- **Header:** Tất cả các endpoint đều yêu cầu xác thực qua HTTP Bearer token:
  ```http
  Authorization: Bearer <access_token_jwt>
  ```
- **Dependency xác thực (`app.core.dependencies`):**
  - `get_current_active_user`: Giải mã JWT token (thuật toán HS256, khóa bí mật từ cấu hình hệ thống), kiểm tra hạn sử dụng (`exp`), xác thực `sub` là UUID hợp lệ, truy vấn database đảm bảo tài khoản tồn tại và có `status == "ACTIVE"`.
  - `get_current_admin_user`: Kế thừa `get_current_active_user`, đồng thời kiểm tra `current_user.is_admin is True`.
- **Nguyên tắc bảo vệ danh tính:** Client không được phép tự truyền `recipient_id`, `actor_id` hoặc header giả mạo `X-User-Id`. Danh tính người dùng được trích xuất an toàn từ payload token.

### 2.2. Kiểu dữ liệu ID và Thời gian
- **ID:** Toàn bộ ID (Notification ID, Post ID, User ID, Claim ID) sử dụng chuẩn **RFC 4122 UUIDv4** (chuỗi 36 ký tự dạng `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`). Tuyệt đối không sử dụng số nguyên BIGINT.
- **Thời gian:** Biểu diễn theo chuẩn ISO 8601 UTC (`YYYY-MM-DDTHH:MM:SSZ`), ví dụ: `2026-11-18T10:30:00Z`.
- **Content-Type:** `application/json; charset=utf-8`.

### 2.3. Quy ước Phân trang (Pagination)
Tất cả các endpoint danh sách đều tuân theo cấu trúc phân trang:
- `page`: Số trang, bắt đầu từ 1 (`ge=1`), mặc định `1`.
- `limit`: Số bản ghi trên mỗi trang, từ 1 đến 100 (`ge=1, le=100`), mặc định `20`.
- **Thứ tự sắp xếp mặc định:** Sắp xếp theo thời gian tạo mới nhất trước: `created_at DESC, id DESC` (đảm bảo tính ổn định của phân trang khi có nhiều bản ghi cùng timestamp).

Cấu trúc metadata phân trang:
```json
{
  "page": 1,
  "limit": 20,
  "total": 42,
  "total_pages": 3
}
```

---

## 3. Ma trận Phân quyền & Cô lập Dữ liệu (Permission Matrix)

| Chức năng | User thường | Admin | Mã HTTP thực tế | Cơ chế kiểm soát |
| :--- | :---: | :---: | :---: | :--- |
| **Xem notification của mình** (`GET /notifications`) | Cho phép (Allow) | Cho phép (Allow) | `200 OK` | Lọc cứng `WHERE recipient_id = current_user.id` |
| **Xem notification người khác** (`GET /notifications`) | Từ chối (Deny) | Từ chối (Deny) | Không bao giờ trả về | Database query cô lập theo `current_user.id`, Admin không có backdoor đọc trộm thông báo user khác |
| **Đánh dấu notification của mình đã đọc** (`PATCH /notifications/{id}/read`) | Cho phép (Allow) | Cho phép (Allow) | `200 OK` | Cập nhật `is_read = true`, `read_at = now()` (idempotent) |
| **Đánh dấu notification người khác đã đọc** (`PATCH /notifications/{id}/read`) | Từ chối (Deny) | Từ chối (Deny) | `404 Not Found` | Bảo vệ quyền riêng tư: Trả về `404` thay vì `403` để chống tấn công dò quét UUID (Resource Enumeration) |
| **Xem danh sách bài đăng Admin** (`GET /admin/posts`) | Từ chối (Deny) | Cho phép (Allow) | `403 Forbidden` (User) / `200 OK` (Admin) | Kiểm tra `current_user.is_admin is True` |
| **Kiểm duyệt bài đăng** (`PATCH /admin/posts/{id}/moderation`) | Từ chối (Deny) | Cho phép (Allow) | `403 Forbidden` (User) / `200 OK` (Admin) | Kiểm tra quyền Admin + Khóa bi quan `FOR UPDATE` |

---

## 4. Đặc tả Chi tiết 4 Endpoints

### 4.1. API 1: Lấy danh sách thông báo người dùng

- **Endpoint:** `GET /api/v1/notifications`
- **Tags:** `Notifications`
- **Summary:** Lấy danh sách thông báo của người dùng
- **Yêu cầu xác thực:** Bearer JWT Token (`get_current_active_user`).

#### Query Parameters:
| Tên tham số | Kiểu | Bắt buộc | Mặc định | Ràng buộc | Mô tả |
| :--- | :--- | :---: | :---: | :--- | :--- |
| `page` | `integer` | Không | `1` | `>= 1` | Số thứ tự trang cần lấy |
| `limit` | `integer` | Không | `20` | `1 <= limit <= 100` | Số lượng thông báo trên một trang |
| `is_read` | `boolean` | Không | `None` | `true` hoặc `false` | Bộ lọc: `true` (chỉ thông báo đã đọc), `false` (chỉ thông báo chưa đọc), `None` (lấy tất cả) |

#### Responses:
- **`200 OK` – Thành công:**
```json
{
  "items": [
    {
      "id": "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11",
      "type": "CLAIM_CREATED",
      "title": "Bạn có yêu cầu nhận đồ mới",
      "message": "Một người dùng đã gửi yêu cầu nhận đồ trong bài đăng của bạn.",
      "resource_type": "CLAIM",
      "resource_id": "b1ffcd88-8b0a-4fe7-aa5c-5aa8ac270b22",
      "is_read": false,
      "read_at": null,
      "created_at": "2026-11-18T10:30:00Z"
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
- **`401 Unauthorized`:** Token thiếu, token hết hạn hoặc chữ ký không hợp lệ:
```json
{
  "detail": "Chưa xác thực hoặc token không hợp lệ"
}
```
- **`403 Forbidden`:** Tài khoản người dùng bị khóa hoặc không ở trạng thái hoạt động:
```json
{
  "detail": "Tài khoản không ở trạng thái hoạt động: SUSPENDED"
}
```
- **`422 Unprocessable Entity`:** Tham số phân trang không hợp lệ (ví dụ `limit=0` hoặc `limit=105`):
```json
{
  "detail": [
    {
      "type": "less_than_equal",
      "loc": ["query", "limit"],
      "msg": "Input should be less than or equal to 100",
      "input": 105
    }
  ]
}
```

---

### 4.2. API 2: Đánh dấu thông báo đã đọc

- **Endpoint:** `PATCH /api/v1/notifications/{id}/read`
- **Tags:** `Notifications`
- **Summary:** Đánh dấu thông báo đã đọc
- **Yêu cầu xác thực:** Bearer JWT Token (`get_current_active_user`).
- **Request Body:** Không có body.

#### Path Parameters:
| Tên tham số | Kiểu | Bắt buộc | Định dạng | Mô tả |
| :--- | :--- | :---: | :--- | :--- |
| `id` | `UUID` | Có | RFC 4122 UUIDv4 | Định danh duy nhất của thông báo cần đánh dấu |

#### Responses:
- **`200 OK` – Thành công (Idempotent):**
```json
{
  "id": "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11",
  "is_read": true,
  "read_at": "2026-11-18T10:35:00Z"
}
```
*Lưu ý tính lũy thừa:* Nếu thông báo đã đọc từ trước, endpoint lập tức trả về `200 OK` cùng `read_at` cũ mà không thực hiện câu lệnh ghi thừa vào database.

- **`401 Unauthorized`:** Chưa đăng nhập hoặc token sai.
- **`404 Not Found`:** Thông báo không tồn tại HOẶC thông báo thuộc người dùng khác:
```json
{
  "detail": "Thông báo không tồn tại hoặc không thuộc quyền sở hữu."
}
```
- **`422 Unprocessable Entity`:** `id` trên đường dẫn không đúng định dạng UUID:
```json
{
  "detail": [
    {
      "type": "uuid_parsing",
      "loc": ["path", "id"],
      "msg": "Input should be a valid UUID, invalid character: found 'x' in input",
      "input": "invalid-uuid"
    }
  ]
}
```

---

### 4.3. API 3: Danh sách bài đăng dành cho Quản trị viên (Admin)

- **Endpoint:** `GET /api/v1/admin/posts`
- **Tags:** `Admin Posts`
- **Summary:** Lấy danh sách bài đăng dành cho Quản trị viên (Admin)
- **Yêu cầu xác thực:** Bearer JWT Token với quyền Admin (`get_current_admin_user`).

#### Query Parameters:
| Tên tham số | Kiểu | Bắt buộc | Mặc định | Mô tả |
| :--- | :--- | :---: | :---: | :--- |
| `page` | `integer` | Không | `1` | Số trang (`>= 1`) |
| `limit` | `integer` | Không | `20` | Số lượng phần tử mỗi trang (`1 <= limit <= 100`) |
| `status` | `string` | Không | `None` | Lọc trạng thái: `DRAFT`, `ACTIVE`, `HIDDEN`, `CLOSED` |
| `type` | `string` | Không | `None` | Lọc loại tin: `LOST`, `FOUND` |
| `q` | `string` | Không | `None` | Từ khóa tìm kiếm theo tiêu đề, mô tả hoặc địa điểm |

#### Responses:
- **`200 OK` – Thành công:**
```json
{
  "items": [
    {
      "id": "c2a11b00-3d2e-4b68-98e1-51829e01347a",
      "title": "Nhặt được ví da màu đen tại Tòa FPT",
      "description": "Nhặt được chiếc ví tại phòng Lab 204 lúc 15h ngày 18/11/2026.",
      "type": "FOUND",
      "status": "ACTIVE",
      "user_id": "d3b22c11-4e3f-4c79-a9f2-6293af12458b",
      "location": "Tòa nhà FPT, Khu Công nghệ cao",
      "area": "Quận 9, TP. Thủ Đức",
      "moderated_by": null,
      "moderated_at": null,
      "moderation_reason": null,
      "created_at": "2026-11-18T08:00:00Z",
      "updated_at": "2026-11-18T08:30:00Z"
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
- **`401 Unauthorized`:** Token không hợp lệ hoặc thiếu token.
- **`403 Forbidden`:** Người dùng không có vai trò Quản trị viên (`is_admin is False`):
```json
{
  "detail": "Chức năng chỉ dành cho quản trị viên (Admin)"
}
```
- **`422 Unprocessable Entity`:** Lỗi tham số phân trang.

---

### 4.4. API 4: Kiểm duyệt bài đăng (Admin Moderation)

- **Endpoint:** `PATCH /api/v1/admin/posts/{id}/moderation`
- **Tags:** `Admin Posts`
- **Summary:** Kiểm duyệt bài đăng (Admin)
- **Yêu cầu xác thực:** Bearer JWT Token với quyền Admin (`get_current_admin_user`).

#### Path Parameters:
| Tên tham số | Kiểu | Bắt buộc | Định dạng | Mô tả |
| :--- | :--- | :---: | :--- | :--- |
| `id` | `UUID` | Có | RFC 4122 UUIDv4 | Định danh duy nhất của bài đăng cần kiểm duyệt |

#### Request Body (`application/json`):
| Thuộc tính | Kiểu | Bắt buộc | Giá trị cho phép | Ràng buộc / Mô tả |
| :--- | :--- | :---: | :--- | :--- |
| `action` | `string` | Có | `"HIDE"` | Hành động kiểm duyệt (hiện chỉ hỗ trợ `"HIDE"`) |
| `reason` | `string` | Có | Chuỗi ký tự | Bắt buộc; không được để trống hoặc chỉ có khoảng trắng; độ dài `1 <= length <= 500` sau khi trim |

*Ví dụ Request Body:*
```json
{
  "action": "HIDE",
  "reason": "Tin đăng có nội dung vi phạm điều khoản cộng đồng."
}
```

#### Responses:
- **`200 OK` – Kiểm duyệt thành công:**
```json
{
  "id": "c2a11b00-3d2e-4b68-98e1-51829e01347a",
  "status": "HIDDEN",
  "moderated_by": "e4c33d22-5f4a-4d8a-ba03-73a4b023569c",
  "moderation_reason": "Tin đăng có nội dung vi phạm điều khoản cộng đồng.",
  "moderated_at": "2026-11-18T10:15:00Z"
}
```

- **`400 Bad Request`:**
  - Bài viết đã đóng (`CLOSED`): Không thể kiểm duyệt bài viết đã hoàn tất chu trình.
    ```json
    {
      "detail": "Không thể kiểm duyệt bài đăng đã đóng (CLOSED)."
    }
    ```
  - Hành động không được hỗ trợ (khác `"HIDE"`):
    ```json
    {
      "detail": "Hành động kiểm duyệt không hợp lệ: APPROVE. Chỉ hỗ trợ hành động HIDE."
    }
    ```

- **`401 Unauthorized`:** Chưa xác thực.
- **`403 Forbidden`:** Người gọi không phải là Admin.
- **`404 Not Found`:** Bài đăng không tồn tại trong hệ thống:
  ```json
  {
    "detail": "Không tìm thấy bài đăng với ID: c2a11b00-3d2e-4b68-98e1-51829e01347a"
  }
  ```
- **`422 Unprocessable Entity`:** Lý do kiểm duyệt rỗng hoặc chỉ toàn khoảng trắng:
  ```json
  {
    "detail": "Lý do kiểm duyệt không được để trống."
  }
  ```

---

## 5. Quy tắc Tính nguyên tử và Giao dịch (Transaction Integrity)

Trong `PATCH /api/v1/admin/posts/{id}/moderation`, quy trình kiểm duyệt diễn ra với các đảm bảo kỹ thuật:
1. **Pessimistic Locking (`SELECT ... FOR UPDATE`):** Khóa dòng bài viết tại thời điểm đọc, ngăn ngừa xung đột dữ liệu khi 2 admin cùng thao tác.
2. **Transaction Atomicity:** Ba thao tác nghiệp vụ được thực hiện trong cùng một session database:
   - Cập nhật trạng thái Post thành `HIDDEN`, gán `moderated_by` và `moderated_at`.
   - Ghi nhật ký kiểm toán vào bảng `audit_logs` (`action="HIDE"`, `actor_id=admin.id`).
   - Tạo thông báo `POST_HIDDEN` cho chủ bài đăng (`auto_commit=False`).
   - Gọi `await session.commit()` duy nhất một lần. Nếu bất kỳ bước nào xảy ra lỗi, toàn bộ thao tác được rollback tự động.
3. **Tính lũy thừa (Idempotency):** Nếu bài viết đã ở trạng thái `HIDDEN`, hệ thống trả về ngay kết quả hiện tại mà không tạo bản ghi audit log trùng hay gửi lặp lại thông báo cho người dùng.
