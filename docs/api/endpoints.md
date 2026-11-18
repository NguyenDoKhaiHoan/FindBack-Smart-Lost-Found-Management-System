# API FindBack

FastAPI công bố contract của phiên bản chạy tại `/openapi.json` và Swagger UI tại `/docs`. Các đường dẫn dưới đây có tiền tố `/api/v1`. ID user, tin, danh mục, claim, phiên trao trả và thông báo là UUID.

| Module | Đường dẫn và phương thức |
| --- | --- |
| Identity | `POST /auth/register`, `POST /auth/login`, `POST /auth/refresh`, `GET /users/{id}`, `GET /users/me`, `PATCH /users/me` |
| Posts | `GET /posts`, `POST /posts`, `GET /posts/{id}`, `PATCH /posts/{id}`, `DELETE /posts/{id}`, `GET /users/me/posts`, `POST /posts/{id}/images`, `GET /posts/{id}/images/{image_id}` |
| Search & Matching | `GET /categories`, `GET /search`, `GET /matches`, `POST /matches/recalculate`, `GET /matches/{id}` |
| Claims | `POST /claims`, `GET /claims/me`, `GET /claims/{id}`, `PATCH /claims/{id}/approve`, `PATCH /claims/{id}/reject`, `PATCH /claims/{id}/complete`, `POST /claims/{id}/evidence`, `GET /claims/{id}/evidence/{evidence_id}/file` |
| Returns | `POST /returns`, `GET /returns/{id}`, `PATCH /returns/{id}/handover` |
| Notifications & Admin | `GET /notifications`, `PATCH /notifications/{id}/read`, `GET /admin/posts`, `PATCH /admin/posts/{id}/moderation`, `POST /reports`, `GET /admin/reports`, `PATCH /admin/reports/{id}`, `GET /admin/statistics` |

`GET /api/v1/health` kiểm tra kết nối DB và trả `503` khi mất kết nối.

## Danh tính và bài đăng

- Đăng nhập trả `access_token` và `refresh_token`. Gửi access token qua `Authorization: Bearer …`. Gửi refresh token trong JSON `{"refresh_token":"…"}` để đổi cả hai token. Refresh token có thời hạn 30 ngày và được thay sau mỗi lần dùng.
- Hồ sơ công khai chỉ trả ID, tên và avatar. Email và số điện thoại chỉ có trong hồ sơ của chính người dùng.
- Tin dùng `OPEN` và `CLOSED`. Tin bị kiểm duyệt trả `HIDDEN` khi thành viên xem tin của mình hoặc admin xem danh sách. Xóa mềm và ẩn đều gỡ tin cùng ảnh khỏi các API công khai.
- Chọn `category_id` từ `GET /categories`. Mã khu vực tích hợp gồm `VN-HN`, `VN-SG`, `VN-DN`, `OTHER`. Nếu bỏ trống mã, tin dùng `OTHER`. `event_time` cần có múi giờ.
- Upload ảnh bài đăng dùng multipart với trường `file`. Tối đa 5 ảnh mỗi tin, mỗi ảnh tối đa 5 MiB và dùng JPEG, PNG hoặc WebP. Giá trị `image.file_path` là URL tải qua API.

## Search và Matching

Xem [contract truy vấn, điểm và phân trang](search-matching-contract.md). Search/Matching áp dụng visibility của Posts. Đọc gợi ý bằng `GET /matches?post_id=<uuid>`. Chủ tin hoặc admin tính lại bằng `POST /matches/recalculate` với JSON `{"post_id":"<uuid>"}`. Lỗi `409 MATCHES_NOT_READY` yêu cầu tính lại khi chưa có kết quả hoặc dữ liệu đầu vào đã đổi. Dùng `GET /matches/{id}?post_id=<uuid>` để chỉ rõ tin nguồn khi xem chi tiết.

## Bằng chứng và trao trả

Sáu API gốc giữ [contract Claims](claims-contract.md). Duyệt và từ chối dùng route riêng. Bước xác nhận nhận đồ dùng `PATCH /claims/{id}/complete`.

1. Người gửi claim có thể bổ sung bằng chứng khi claim ở `PENDING`. Gửi `expected_version` và `evidence_description`. Để gửi ảnh JPEG, PNG hoặc WebP tối đa 5 MiB, gửi thêm `image_base64` và `image_content_type`. Chủ tin và người gửi claim có thể tải ảnh theo ID bằng chứng.
2. Chủ tin duyệt claim, rồi gọi `POST /returns` với `claim_id` và `expected_version`. Có thể gửi thêm `scheduled_at` và `meeting_note`. Hai người liên quan có thể xem phiên và ghi chú qua `GET /returns/{id}`.
3. Chủ tin gọi `PATCH /returns/{id}/handover` với `expected_version` để ghi nhận đã giao. Người nhận gọi `PATCH /claims/{id}/complete` với phiên bản mới và `receipt_confirmed: true`.
4. Mỗi thay đổi tăng version của claim. Đọc lại `GET /claims/{id}` trước thao tác tiếp theo. Thay đổi nghiệp vụ, audit và thông báo trong ứng dụng được ghi cùng giao dịch.

## Kiểm duyệt

Người đăng nhập gửi báo cáo bằng `POST /reports` với `post_id` và `reason`. Mỗi người có tối đa một báo cáo đang mở cho mỗi tin. Admin xem và cập nhật báo cáo bằng `status` và `resolution_note`. Báo cáo mới là `PENDING`, có thể sang `REVIEWING`, `RESOLVED` hoặc `DISMISSED`. Admin ẩn tin qua route moderation với `{"action":"HIDE","reason":"…"}`. Các API `/admin/*` yêu cầu vai trò admin.

Hủy claim và chính sách tranh chấp cần contract nghiệp vụ riêng theo [yêu cầu dự án](../requirements.md).
