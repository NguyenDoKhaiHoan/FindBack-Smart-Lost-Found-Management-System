# Danh mục API sơ bộ — 30 endpoints

Danh sách bám theo tài liệu phân tích, chưa phải OpenAPI contract hoặc API đã triển khai. Chưa thêm prefix/version cho URL. Cần chốt request/response, quyền, mã lỗi và phân trang khi thiết kế contract.

## TV1 — Identity & User (6)

| Method | Endpoint | Mục đích |
| --- | --- | --- |
| POST | `/auth/register` | Đăng ký |
| POST | `/auth/login` | Đăng nhập |
| POST | `/auth/refresh` | Làm mới token |
| GET | `/users/me` | Xem hồ sơ |
| PATCH | `/users/me` | Sửa hồ sơ |
| GET | `/users/{id}` | Hồ sơ công khai |

## TV2 — Posts (6)

| Method | Endpoint | Mục đích |
| --- | --- | --- |
| POST | `/posts` | Tạo tin |
| GET | `/posts` | Danh sách/lọc |
| GET | `/posts/{id}` | Chi tiết |
| PATCH | `/posts/{id}` | Chỉnh sửa |
| DELETE | `/posts/{id}` | Xóa mềm |
| GET | `/users/me/posts` | Tin của tôi |

## TV3 — Search & Matching (5)

| Method | Endpoint | Mục đích |
| --- | --- | --- |
| GET | `/categories` | Danh mục |
| GET | `/posts/search` | Tìm nâng cao |
| GET | `/posts/{id}/matches` | Gợi ý phù hợp |
| POST | `/matches/recalculate` | Tính lại điểm |
| GET | `/matches/{id}` | Chi tiết gợi ý |

Khi mount router, đăng ký đường dẫn tĩnh như `/posts/search`, `/users/me` trước đường dẫn tham số tương ứng để tránh xung đột.

## TV4 — Claims & Returns (7)

**Cập nhật thiết kế 2026-11-14:** [Contract Claims và ma trận quyền](claims-contract.md)
và [OpenAPI sáu endpoint `/api/v1/claims`](claims.openapi.json) là đặc tả đề xuất mới
cho tạo/xem/approve/reject/complete. Bảng bảy API dưới đây được giữ làm lịch sử phân tích;
`decision` được tách thành `approve`/`reject`, `complete` xác nhận nhận đồ qua Return.
Upload bằng chứng, lập lịch và ghi nhận giao là phụ thuộc cần contract riêng, chưa được sáu API bao phủ.
Các quyết định tích hợp và khác biệt RETURNED/CANCELLED/Return nằm trong contract mới.

| Method | Endpoint | Mục đích |
| --- | --- | --- |
| POST | `/claims` | Tạo claim |
| GET | `/claims/me` | Claim liên quan |
| GET | `/claims/{id}` | Chi tiết claim |
| POST | `/claims/{id}/evidence` | Gửi bằng chứng |
| PATCH | `/claims/{id}/decision` | Duyệt/từ chối |
| POST | `/returns` | Lập phiên trao trả |
| POST | `/returns/{id}/confirm` | Xác nhận bàn giao |

## TV5 — Notifications & Admin (6)

| Method | Endpoint | Mục đích |
| --- | --- | --- |
| GET | `/notifications` | Danh sách thông báo |
| PATCH | `/notifications/{id}/read` | Đánh dấu đã đọc |
| POST | `/reports` | Báo cáo vi phạm |
| GET | `/admin/reports` | Danh sách báo cáo |
| PATCH | `/admin/reports/{id}` | Xử lý báo cáo |
| GET | `/admin/statistics` | Thống kê |

## Ví dụ tiêu chí API: POST /claims

| Trường | Nội dung theo phân tích |
| --- | --- |
| Actor | User đã đăng nhập |
| Input | `found_post_id`, `evidence_description` |
| Điều kiện | Tin FOUND tồn tại, chưa trao trả; người gửi không là chủ tin |
| Thành công | HTTP 201, trả `claim_id`, `status=PENDING` |
| Lỗi | 401 chưa đăng nhập; 403 sai quyền; 404 không tồn tại; 409 claim trùng |
| Nghiệm thu | Tạo thành công, chặn trùng, không lộ bằng chứng |
| Kiểm thử | Happy path, self-claim, duplicate, invalid post, unauthenticated |

Lỗi validation và schema lỗi chung cần bổ sung khi chốt contract. Danh sách sơ bộ chưa quy định đầy đủ endpoint hủy, tranh chấp, chuyển bước bàn giao hoặc upload ảnh tin; không tự coi các luồng này đã được bao phủ.
