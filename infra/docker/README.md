# PostgreSQL local

Chạy các lệnh từ thư mục gốc dự án. Sao chép `.env.example` thành `.env`
và điền `POSTGRES_USER`, `POSTGRES_PASSWORD`, đồng thời cập nhật `DATABASE_URL`.
Không commit `.env`.

```powershell
docker compose --env-file .env -f infra/docker/compose.yaml up -d --wait
docker compose --env-file .env -f infra/docker/compose.yaml ps
```

Kết nối bằng host `localhost`, port `5432`, database `findback` và tài khoản
trong `.env`. Container có tên `findback-postgres`. PostgreSQL chỉ mở cổng
trên máy local; dữ liệu được lưu trong volume `findback_postgres_data`.
`POSTGRES_USER` là tài khoản quản trị PostgreSQL của môi trường local.

Đăng nhập trong terminal (nhập mật khẩu khi được hỏi):

```powershell
docker exec -it findback-postgres sh -c 'psql -h findback-postgres -U "$POSTGRES_USER" -d "$POSTGRES_DB" -W'
```

Dừng container và giữ dữ liệu:

```powershell
docker compose --env-file .env -f infra/docker/compose.yaml down
```

Các biến `POSTGRES_*` chỉ khởi tạo tài khoản/database khi volume còn trống.
Đổi mật khẩu trong `.env` không tự đổi mật khẩu của tài khoản đã tồn tại.

## Giao diện pgAdmin

Lệnh Compose ở trên cũng khởi động pgAdmin. Mở http://localhost:5050.
Email đăng nhập mặc định là `hoan2308@example.com` (có thể đặt
`PGADMIN_DEFAULT_EMAIL` trong `.env`); mật khẩu lấy từ `POSTGRES_PASSWORD`
khi khởi tạo pgAdmin lần đầu.

Server `FindBack` được cấu hình sẵn cho tài khoản `Hoan2308`. Chọn server
và nhập mật khẩu PostgreSQL khi được hỏi. Nếu đổi tên user hoặc database,
cập nhật cấu hình server trong pgAdmin.

pgAdmin lưu cấu hình trong volume riêng `findback_pgadmin_data`.
