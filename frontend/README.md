# FindBack frontend

Ứng dụng React dùng trực tiếp [API FindBack](../docs/api/endpoints.md). Trang chủ và tìm kiếm hiển thị các tin trong cơ sở dữ liệu được backend cấu hình. Tin mới, hồ sơ, báo cáo và thông báo được lưu qua API.

## Chạy trong VS Code

Chạy backend theo [hướng dẫn](../backend/README.md). Sau đó mở terminal PowerShell thứ hai.

```powershell
cd frontend
npm ci
npm run dev
```

Mở [FindBack](http://127.0.0.1:5173). Vite chuyển tiếp `/api` đến cổng `8000` theo mặc định. Nếu backend đang chạy cổng `8001`, đặt `API_PROXY_TARGET=http://127.0.0.1:8001` trong `frontend/.env.local` rồi khởi động lại Vite. Có thể để trống `VITE_API_BASE_URL` khi dùng proxy.

## Luồng sử dụng

- Đăng ký, đăng nhập và sửa hồ sơ. Phiên truy cập được giữ trong bộ nhớ của tab và gia hạn khi tab còn mở.
- Đăng tin mất hoặc nhặt được, thêm ảnh, tìm kiếm và quản lý tin. Trang **Gợi ý phù hợp** dùng tin đang mở của bạn để tính kết quả.
- Mở một tin nhặt được, chọn **Đây là đồ của tôi** và gửi mô tả bằng chứng. Khi yêu cầu còn chờ duyệt, người gửi có thể bổ sung ảnh riêng tư.
- Chủ tin duyệt yêu cầu, lập phiên và ghi nhận đã giao. Người nhận xác nhận sau khi nhận đúng đồ. Cập nhật xuất hiện ở **Thông báo**.
- Tài khoản có quyền quản trị đã được backend cấp có thể vào **Quản trị** để xem thống kê, xử lý báo cáo và ẩn tin.

## Kiểm tra

```powershell
npm run lint
npm test
npm run build
npm run test:api
npm run test:browser
npm run test:production
```

`test:api` và `test:browser` cần `backend/.venv` từ `uv sync --locked`. Chạy hai lệnh tuần tự vì dùng chung cổng test backend 18000. Các bài kiểm tra tạo dữ liệu trong SQLite tạm. Trên Windows, bài kiểm tra trình duyệt dùng Chrome đã cài.
