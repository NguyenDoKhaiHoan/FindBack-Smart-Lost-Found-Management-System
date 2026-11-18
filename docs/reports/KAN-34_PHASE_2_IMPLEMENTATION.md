# KAN-34 – BÁO CÁO PHASE 2: FIX OPENAPI, SCHEMAS & INTEGRATION DOCUMENTATION

**Dự án:** FindBack – Smart Lost & Found Management System
**Repository:** `FindBack-Smart-Lost-Found-Management-System`
**Branch:** `vu`
**Jira Ticket:** KAN-34 – Sửa lỗi và hoàn thiện tài liệu API Notifications/Admin
**Ngày thực hiện:** 18/11/2026
**Người thực hiện:** Antigravity AI – Pair Programming Engineer
**Trạng thái:** HOÀN THÀNH PHASE 2 (CHỜ TECH LEAD REVIEW TRƯỚC KHI STAGE/COMMIT)

---

## MỤC LỤC
1. [Tổng quan & Git Baseline](#1-tổng-quan--git-baseline)
2. [Danh sách Lỗi & Tồn đọng Đã Xử lý](#2-danh-sách-lỗi--tồn-đọng-đã-xử-lý)
3. [Danh sách File Thay đổi](#3-danh-sách-file-thay-đổi)
4. [So sánh Đối chiếu OpenAPI: Trước vs Sau](#4-so-sánh-đối-chiếu-openapi-trước-vs-sau)
5. [Nội dung Chuẩn hóa Hợp đồng API & Hợp đồng Sự kiện](#5-nội-dung-chuẩn-hóa-hợp-đồng-api--hợp-đồng-sự-kiện)
6. [Ma trận Phân quyền & Cô lập Quyền sở hữu (Permission Matrix)](#6-ma-trận-phân-quyền--cô-lập-quyền-sở-hữu-permission-matrix)
7. [Kết quả Kiểm thử (95/95 Test Cases Pass)](#7-kết-quả-kiểm-thử-9595-test-cases-pass)
8. [Các Điểm Tồn đọng Module Claims (Ghi nhận NOT VERIFIED)](#8-các-điểm-tồn-đọng-module-claims-ghi-nhận-not-verified)
9. [Điều phối & Xác nhận Liên Module (Identity, Posts, Claims)](#9-điều-phối--xác-nhận-liên-module-identity-posts-claims)

---

## 1. Tổng quan & Git Baseline

### 1.1. Xác minh Git
- **Branch:** `vu`
- **Baseline commit:** `a7ec9fa245e98d3271c3ffb08578b171938a7f12` (`test: add comprehensive KAN-33 notification and admin tests`)
- **Remote:** `origin/vu` hoàn toàn đồng bộ, không có xung đột.
- **Working Tree:** Chỉ sửa đổi đúng 6 file được phê duyệt trong phạm vi Phase 2 và tạo mới 1 file báo cáo implementation.
- **File untracked:** File `docs/reports/KAN-31_POST_COMMIT_REVIEW.md` được giữ nguyên vẹn, không bị stage hay tác động.

### 1.2. Mục tiêu Phase 2 đã đạt được
1. Khắc phục triệt để sự thiếu hụt các mã trạng thái lỗi trong metadata OpenAPI của cả 4 endpoint cốt lõi (`400`, `401`, `403`, `404`).
2. Hoàn thiện Pydantic Schemas với đầy đủ `Field(..., description=..., examples=...)` và định dạng `UUIDv4` chuẩn RFC 4122.
3. Chuẩn hóa toàn diện tài liệu hợp đồng `API_CONTRACT_NOTIFICATIONS_ADMIN.md`, loại bỏ hoàn toàn các ID dạng `BIGINT` cũ (`101`, `25`).
4. Chuẩn hóa hợp đồng sự kiện `NOTIFICATION_EVENT_CONTRACT.md` phục vụ việc tích hợp của module Claims trong tương lai, quy định chặt chẽ về transaction ownership (`auto_commit=False`) và cơ chế chống trùng lặp (deduplication).
5. Xác minh toàn bộ test suite tiếp tục đạt kết quả **95/95 test cases pass** (100%).

---

## 2. Danh sách Lỗi & Tồn đọng Đã Xử lý

| Mã lỗi | Hạng mục | Tình trạng trước Phase 2 | Giải pháp kỹ thuật đã thực hiện | Trạng thái |
| :---: | :--- | :--- | :--- | :---: |
| **ISSUE-01** | OpenAPI Docs | 4 Endpoint chỉ khai báo `200` và `422`, thiếu hoàn toàn các mã lỗi `400`, `401`, `403`, `404`. | Thêm dictionary `responses={...}` chi tiết vào router decorators của `notifications.py` và `admin_posts.py`, kèm mô hình `ErrorResponse`. | **ĐÃ SỬA** |
| **ISSUE-02** | Pydantic Schemas | Các schema thiếu docstrings, thiếu mô tả trường (`description`), thiếu ví dụ (`examples`) và định dạng UUID. | Bổ sung đầy đủ metadata `Field(..., description="...", examples=[...])` vào `notification.py` và `admin_post.py`. | **ĐÃ SỬA** |
| **ISSUE-03** | API Contract Doc | `API_CONTRACT_NOTIFICATIONS_ADMIN.md` còn dùng kiểu ID `BIGINT` (`101`, `25`), lệch pha với code dùng `UUID`. | Viết lại toàn bộ hợp đồng theo chuẩn `UUIDv4`, đồng bộ response JSON và status code thực tế của 4 endpoints. | **ĐÃ SỬA** |
| **ISSUE-04** | Event Contract Doc | `NOTIFICATION_EVENT_CONTRACT.md` còn dùng kiểu `recipient_id: int`, thiếu hướng dẫn cụ thể cho Claims. | Chuẩn hóa `recipient_id: uuid.UUID`, mô tả 6 event catalog, quy tắc `auto_commit=False` và ví dụ gọi service. | **ĐÃ SỬA** |
| **ISSUE-05** | Privacy & Masking | Cần bảo đảm truy cập notification người khác trả về `404 Not Found` để che giấu quyền sở hữu. | Khẳng định và tài liệu hóa rõ ràng trong router response doc và contract doc: trả về `404` thay vì `403`. | **ĐÃ SỬA** |

---

## 3. Danh sách File Thay đổi

Tất cả 6 file mã nguồn và tài liệu thay đổi đều nằm chính xác trong danh sách được phê duyệt:

1. [`backend/app/modules/notifications_admin/routers/notifications.py`](file:///c:/Users/GF63/OneDrive/Tài%20li%C3%AA%CC%A3u/Th%E1%BB%B1c%20t%E1%BA%ADp%20FPT/FindBack/FindBack-Smart-Lost-Found-Management-System/backend/app/modules/notifications_admin/routers/notifications.py)
   *Chi tiết:* Bổ sung `responses={...}` cho `GET /notifications` (`200`, `401`, `403`) và `PATCH /notifications/{id}/read` (`200`, `401`, `404`).
2. [`backend/app/modules/notifications_admin/routers/admin_posts.py`](file:///c:/Users/GF63/OneDrive/Tài%20li%C3%AA%CC%A3u/Th%E1%BB%B1c%20t%E1%BA%ADp%20FPT/FindBack/FindBack-Smart-Lost-Found-Management-System/backend/app/modules/notifications_admin/routers/admin_posts.py)
   *Chi tiết:* Bổ sung `responses={...}` cho `GET /admin/posts` (`200`, `401`, `403`) và `PATCH /admin/posts/{id}/moderation` (`200`, `400`, `401`, `403`, `404`).
3. [`backend/app/modules/notifications_admin/schemas/notification.py`](file:///c:/Users/GF63/OneDrive/Tài%20li%C3%AA%CC%A3u/Th%E1%BB%B1c%20t%E1%BA%ADp%20FPT/FindBack/FindBack-Smart-Lost-Found-Management-System/backend/app/modules/notifications_admin/schemas/notification.py)
   *Chi tiết:* Thêm class `ErrorResponse`, bổ sung `Field` descriptions, UUIDv4 examples và ISO 8601 UTC timestamp format cho `NotificationItemResponse`, `NotificationPagination`, `NotificationListResponse`, `NotificationReadResponse`, `NotificationCreateInternal`.
4. [`backend/app/modules/notifications_admin/schemas/admin_post.py`](file:///c:/Users/GF63/OneDrive/Tài%20li%C3%AA%CC%A3u/Th%E1%BB%B1c%20t%E1%BA%ADp%20FPT/FindBack/FindBack-Smart-Lost-Found-Management-System/backend/app/modules/notifications_admin/schemas/admin_post.py)
   *Chi tiết:* Bổ sung `Field` descriptions, UUIDv4 examples và ràng buộc độ dài `reason` (`1 <= len <= 500`) cho `AdminPostItemResponse`, `AdminPostPagination`, `AdminPostListResponse`, `PostModerationRequest`, `PostModerationResponse`.
5. [`docs/api/API_CONTRACT_NOTIFICATIONS_ADMIN.md`](file:///c:/Users/GF63/OneDrive/Tài%20li%C3%AA%CC%A3u/Th%E1%BB%B1c%20t%E1%BA%ADp%20FPT/FindBack/FindBack-Smart-Lost-Found-Management-System/docs/api/API_CONTRACT_NOTIFICATIONS_ADMIN.md)
   *Chi tiết:* Chuẩn hóa tài liệu API Contract sang định dạng UUIDv4, cập nhật các endpoint và permission matrix.
6. [`docs/api/NOTIFICATION_EVENT_CONTRACT.md`](file:///c:/Users/GF63/OneDrive/Tài%20li%C3%AA%CC%A3u/Th%E1%BB%B1c%20t%E1%BA%ADp%20FPT/FindBack/FindBack-Smart-Lost-Found-Management-System/docs/api/NOTIFICATION_EVENT_CONTRACT.md)
   *Chi tiết:* Chuẩn hóa tài liệu Notification Event Contract cho Claims và Posts với mã mẫu tích hợp và quy định transaction ownership.

---

## 4. So sánh Đối chiếu OpenAPI: Trước vs Sau

Kết quả trích xuất trực tiếp từ FastAPI generated OpenAPI schema (`app.openapi()`):

| Endpoint | Method | OpenAPI trước Phase 2 | OpenAPI sau Phase 2 (Hoàn thiện) | Chi tiết cải tiến |
| :--- | :---: | :---: | :---: | :--- |
| `/api/v1/notifications` | `GET` | `200`, `422` | **`200`, `401`, `403`, `422`** | Bổ sung `401 Unauthorized` (Token lỗi/hết hạn), `403 Forbidden` (User inactive). |
| `/api/v1/notifications/{id}/read` | `PATCH` | `200`, `422` | **`200`, `401`, `404`, `422`** | Bổ sung `401 Unauthorized`, `404 Not Found` (Ẩn quyền sở hữu bằng 404). |
| `/api/v1/admin/posts` | `GET` | `200`, `422` | **`200`, `401`, `403`, `422`** | Bổ sung `401 Unauthorized`, `403 Forbidden` (Chỉ dành cho Admin). |
| `/api/v1/admin/posts/{id}/moderation` | `PATCH` | `200`, `422` | **`200`, `400`, `401`, `403`, `404`, `422`** | Bổ sung `400 Bad Request` (Bài đã CLOSED hoặc action sai), `401`, `403`, `404 Not Found`. |

Tất cả các status code lỗi trên đều được liên kết chặt chẽ với schema `ErrorResponse` (`{"detail": "..."}`) trong mục `components.schemas` của OpenAPI.

---

## 5. Nội dung Chuẩn hóa Hợp đồng API & Hợp đồng Sự kiện

### 5.1. API Contract (`API_CONTRACT_NOTIFICATIONS_ADMIN.md`)
- Loại bỏ 100% các ví dụ `id: 101` hoặc `resource_id: "25"`.
- Thay thế toàn bộ bằng UUID hợp lệ (ví dụ: `a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11`, `c2a11b00-3d2e-4b68-98e1-51829e01347a`).
- Đồng bộ chính xác các trường DTO giữa API docs và mã nguồn (ví dụ: `is_read: bool`, `read_at: datetime | None`, `type: str`, `title: str`, `message: str`).
- Đặc tả chi tiết cơ chế phân trang `created_at DESC, id DESC`.

### 5.2. Notification Event Contract (`NOTIFICATION_EVENT_CONTRACT.md`)
- Chuẩn hóa chữ ký `NotificationService.create_notification(session, data: NotificationCreateInternal, auto_commit=False)`.
- Xác định rõ vai trò quản lý Transaction (Transaction Ownership):
  - Caller khi thực hiện luồng nghiệp vụ phức tạp bắt buộc truyền `auto_commit=False` để commit hoặc rollback nguyên tử.
- Danh mục 6 sự kiện: `POST_HIDDEN`, `CLAIM_CREATED`, `CLAIM_APPROVED`, `CLAIM_REJECTED`, `RETURN_REQUESTED`, `RETURN_COMPLETED`.
- Khẳng định tính lũy thừa qua ràng buộc duy nhất `uq_notifications_event_id` với thuật toán sinh UUIDv5 xác định.
- Quy định bảo mật nghiêm ngặt (PRIV-01): Cấm tuyệt đối việc đưa chứng từ nhận đồ riêng tư, token, hoặc mật khẩu vào metadata.

---

## 6. Ma trận Phân quyền & Cô lập Quyền sở hữu (Permission Matrix)

Hệ thống tuân thủ nguyên tắc Least Privilege và Data Isolation:

| Chức năng | User thường | Admin | Mã HTTP thực tế | Cơ chế kiểm soát kỹ thuật |
| :--- | :---: | :---: | :---: | :--- |
| **Xem notification của mình** (`GET /notifications`) | Cho phép (Allow) | Cho phép (Allow) | `200 OK` | Lọc cứng `WHERE recipient_id = current_user.id` |
| **Xem notification người khác** (`GET /notifications`) | Từ chối (Deny) | Từ chối (Deny) | Không bao giờ trả về | Database query cô lập theo `current_user.id`, Admin không có backdoor đọc trộm thông báo user khác |
| **Đánh dấu notification của mình đã đọc** (`PATCH /notifications/{id}/read`) | Cho phép (Allow) | Cho phép (Allow) | `200 OK` | Cập nhật `is_read = true`, `read_at = now()` (idempotent) |
| **Đánh dấu notification người khác đã đọc** (`PATCH /notifications/{id}/read`) | Từ chối (Deny) | Từ chối (Deny) | `404 Not Found` | Bảo vệ quyền riêng tư: Trả về `404` thay vì `403` để chống tấn công dò quét UUID (Resource Enumeration) |
| **Xem danh sách bài đăng Admin** (`GET /admin/posts`) | Từ chối (Deny) | Cho phép (Allow) | `403 Forbidden` (User) / `200 OK` (Admin) | Kiểm tra `current_user.is_admin is True` |
| **Kiểm duyệt bài đăng** (`PATCH /admin/posts/{id}/moderation`) | Từ chối (Deny) | Cho phép (Allow) | `403 Forbidden` (User) / `200 OK` (Admin) | Kiểm tra quyền Admin + Khóa bi quan `FOR UPDATE` |

---

## 7. Kết quả Kiểm thử (95/95 Test Cases Pass)

Toàn bộ test suite được chạy trên môi trường kiểm thử cô lập PostgreSQL (`findback_test`):

```text
============================= test session starts =============================
platform win32 -- Python 3.11.9, pytest-8.4.1, pluggy-1.6.0
rootdir: C:\Users\GF63\OneDrive\Tài liệu\Thực tập FPT\FindBack\FindBack-Smart-Lost-Found-Management-System\backend
configfile: pytest.ini
plugins: anyio-4.10.0, asyncio-1.1.0
asyncio: mode=Mode.AUTO
collected 95 items

tests/api/test_admin_posts.py ............................               [ 29%]
tests/api/test_notifications.py ....................                    [ 50%]
tests/api/test_posts_schema.py ...............                           [ 66%]
tests/integration/test_admin_audit_database.py .......                   [ 73%]
tests/integration/test_notification_database.py .....                    [ 78%]
tests/unit/notifications_admin/test_notification_service.py ..........   [ 89%]
tests/unit/notifications_admin/test_post_moderation_service.py ..........[100%]

============================= 95 passed in 52.75s =============================
```

### Phân rã kết quả:
- **Unit Tests Post Moderation Service:** 10/10 PASSED.
- **Unit Tests Notification Service:** 10/10 PASSED.
- **Database Integration Tests (Notification & Admin Audit):** 12/12 PASSED.
- **API Tests (Notifications, Admin Posts, Posts Schema):** 63/63 PASSED.
- **Tổng cộng:** **95/95 PASSED (100%)**, không có regression, không có lỗi runtime.

---

## 8. Các Điểm Tồn đọng Module Claims (Ghi nhận NOT VERIFIED)

1. **Hiện trạng Module:** Thư mục `backend/app/modules/claims_returns/` hiện vẫn rỗng (chỉ có các file placeholder `.gitkeep`).
2. **Runtime Verification:** Chưa thể kiểm thử tích hợp luồng phát sự kiện Claims $\rightarrow$ Notifications ở môi trường thực tế (end-to-end runtime).
3. **Trạng thái ghi nhận:** Chính thức đánh dấu là **NOT VERIFIED**.
4. **Hành động đã hoàn thành:** Đã cung cấp tài liệu kỹ thuật chuẩn mực và mã mẫu tích hợp trong [`docs/api/NOTIFICATION_EVENT_CONTRACT.md`](file:///c:/Users/GF63/OneDrive/Tài%20li%C3%AA%CC%A3u/Th%E1%BB%B1c%20t%E1%BA%ADp%20FPT/FindBack/FindBack-Smart-Lost-Found-Management-System/docs/api/NOTIFICATION_EVENT_CONTRACT.md) để người phụ trách module Claims triển khai theo đúng chuẩn khi đến giai đoạn của ticket đó.

---

## 9. Điều phối & Xác nhận Liên Module (Identity, Posts, Claims)

1. **Module Identity:**
   - Đã xác minh sự tương thích 100% với `get_current_active_user` và `get_current_admin_user`.
   - Các mã lỗi `401 Unauthorized` và `403 Forbidden` (User inactive) được đồng bộ chính xác.
2. **Module Posts:**
   - Trạng thái `HIDDEN`, cờ kiểm duyệt `moderated_by`, `moderated_at`, và constraint `ck_posts_moderation` hoạt động ổn định và đồng bộ hoàn hảo.
   - Luồng kiểm duyệt ẩn bài viết và ghi audit log đảm bảo tính toàn vẹn dữ liệu.
3. **Module Claims & Returns:**
   - Cần Claims Owner xác nhận chính thức danh tính người nhận (`recipient_id`) cho từng sự kiện `CLAIM_*` và `RETURN_*` khi bắt đầu triển khai code nghiệp vụ của module này.

---

## KẾT LUẬN & KIẾN NGHỊ

Phase 2 – Fix OpenAPI, Schemas & Integration Documentation đã hoàn thành xuất sắc toàn bộ các mục tiêu đề ra:
- Sửa lỗi thiếu OpenAPI status codes.
- Hoàn thiện Pydantic schemas với descriptions và UUID examples.
- Chuẩn hóa toàn bộ tài liệu hợp đồng KAN-30 sang chuẩn UUIDv4.
- Đảm bảo 100% test cases (95/95) pass.
- Giữ nguyên vẹn database phát triển `findback` và working tree sạch sẽ.

**Tôi đã dừng lại theo đúng quy trình và kính trình Tech Lead review kết quả Phase 2.**
