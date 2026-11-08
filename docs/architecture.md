# Kiến trúc và quy ước tổ chức

## Kiến trúc đích

Modular Monolith với React, FastAPI và PostgreSQL. Mỗi module nằm trong cùng ứng dụng backend, cùng cơ sở dữ liệu; không tạo 5 service độc lập.

```text
frontend/src/features
          │ HTTP
          ▼
backend/app/api                 tập hợp router
          ▼
modules/<module>/routers        xử lý giao thức và dependency
          ▼
modules/<module>/services       use case, quyền và state machine
          ▼
modules/<module>/repositories   truy cập dữ liệu
          ▼
PostgreSQL                      ràng buộc và transaction
```

`schemas/` định nghĩa request/response; `models/` định nghĩa persistence. Không trả trực tiếp model có bằng chứng, password hash hoặc dữ liệu nhạy cảm ra API.

## Ranh giới module

| Module | Trách nhiệm |
| --- | --- |
| Identity | Auth, user, JWT, RBAC, hồ sơ |
| Posts | Tin LOST/FOUND, ảnh công khai, ownership, trạng thái tin |
| Matching | Danh mục, bộ lọc, điểm gợi ý, giải thích dựa trên dữ liệu cho phép |
| Claims & Returns | Bằng chứng riêng tư, quyết định claim, giao dịch bàn giao |
| Notifications & Admin | Thông báo, báo cáo, kiểm duyệt, thống kê |

Giao tiếp liên module qua service/interface rõ ràng. Không gọi router từ service, không tạo kết nối DB riêng trong từng repository. Điểm bắt đầu/kết thúc transaction thuộc use case để cập nhật claim, return, trạng thái tin và audit log nhất quán.

## Dữ liệu và tệp

- PostgreSQL là nguồn dữ liệu nghiệp vụ; thay đổi schema phải đi qua Alembic.
- Tách ảnh tin công khai khỏi bằng chứng riêng tư. Bằng chứng cần endpoint kiểm tra quyền; không chỉ giấu URL ở frontend.
- File runtime và dump không được đưa vào Git. Thư mục lưu trữ sẽ được cấu hình khi triển khai.
- Ghi audit log cho duyệt, từ chối, bàn giao và các hành động nhạy cảm theo quy tắc đã chốt. Không ghi nội dung bằng chứng hay token vào application log.
- Thông báo MVP là thông báo trong ứng dụng; email, push và realtime chưa được yêu cầu.

## Trạng thái hiện tại

Chỉ có cấu trúc thư mục và tài liệu. Chưa có server, cấu hình database, container, cơ chế lưu file hoặc kiểm soát quyền hoạt động. Xem [README gốc](../README.md) để bắt đầu phát triển.
