# Kế hoạch kiểm thử

Chưa có test hoặc ứng dụng chạy được. Tài liệu này hướng dẫn kiểm thử khi từng module được triển khai; không phải kết quả test đã đạt.

## Vị trí

| Thư mục | Mục đích |
| --- | --- |
| `backend/tests/unit/<module>/` | Logic quyền, validation, matching và chuyển trạng thái |
| `backend/tests/integration/` | PostgreSQL, repository, transaction, ràng buộc và phối hợp module |
| `backend/tests/api/` | HTTP status, schema, authentication, authorization, bảo vệ dữ liệu |
| `frontend/tests/unit/` | Hành vi component và tương tác giao diện |
| `frontend/tests/e2e/` | Luồng người dùng từ đăng nhập đến trao trả |

## Các tình huống ưu tiên

- Identity: đăng ký/đăng nhập, token sai/hết hạn, user không được gọi thao tác admin.
- Posts: thiếu dữ liệu bắt buộc, sửa tin người khác, ẩn/xóa mềm, không lộ dữ liệu nhạy cảm.
- Matching: đúng cặp LOST–FOUND, bộ lọc, thứ tự điểm ổn định, giải thích không tiết lộ bí mật; gợi ý không tự duyệt claim.
- Claims: tạo hợp lệ, tự claim, claim trùng, tin không tồn tại/đã trao trả, chưa đăng nhập, xem bằng chứng sai quyền.
- Returns: claim chưa duyệt không tạo return; chặn chuyển trạng thái sai thứ tự, xác nhận sai quyền/trùng và đóng tin quá sớm.
- Transaction: hai request cạnh tranh cùng đồ vật không tạo kết quả duyệt/bàn giao trái chính sách; kiểm tra trên PostgreSQL thực tế khi schema đã chốt.
- Notifications/Admin: chỉ xem/đánh dấu thông báo của mình, user không xử lý report của admin; hành động quyết định/bàn giao có audit log.

## Luồng nghiệm thu MVP

1. Hai user đăng nhập, đăng LOST và FOUND với dữ liệu hợp lệ.
2. Tìm kiếm, xem gợi ý có giải thích theo quy tắc.
3. User gửi claim kèm bằng chứng riêng tư.
4. Người có quyền xem xét và duyệt/từ chối; người ngoài không đọc được bằng chứng.
5. Từ claim được duyệt, tạo phiên trao trả; đi qua các bước và xác nhận theo quyền đã chốt.
6. Đóng tin khi đủ điều kiện, lưu lịch sử/audit log và thông báo theo nghiệp vụ.
7. Kiểm tra thêm cạnh tranh claim, claim trùng, hủy/tranh chấp theo contract được thống nhất.

Khi bổ sung công cụ kiểm thử, ghi lệnh chạy và kết quả thực tế vào README hoặc test report. Không dùng dữ liệu cá nhân hay bằng chứng thật làm fixture.
