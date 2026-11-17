# Hạ tầng FindBack (Docker & Database)

Thư mục `infra/` quản lý cấu hình triển khai hạ tầng cơ sở dữ liệu và các dịch vụ nền tảng cho dự án FindBack.

---

## 1. Cấu hình Docker Compose

File cấu hình chính: `infra/docker/compose.yaml`

Dịch vụ bao gồm:
- **`postgres`**: PostgreSQL 16 Alpine
  - Container name: `findback_postgres`
  - Port map: `5432:5432` (Host:Container)
  - Default User: `findback`
  - Default DB: `findback`
  - Password: thiết lập qua biến môi trường `POSTGRES_PASSWORD` (mặc định `findback_secret`)
  - Volume: `findback_postgres_data` (lưu trữ dữ liệu độc lập, không bị mất khi stop container)
  - Healthcheck: kiểm tra `pg_isready -U findback -d findback` định kỳ 5s

> **Lưu ý bảo mật:**
> - Tuyệt đối không commit file `.env` chứa mật khẩu thực tế lên Git.
> - Các container phục vụ công việc khác trên máy host (ví dụ cổng 3000, 5000, 8000) được giữ nguyên, không gây xung đột tài nguyên.

---

## 2. Hướng dẫn vận hành

### 2.1. Khởi chạy PostgreSQL

```bash
# Từ thư mục gốc repository:
docker compose -f infra/docker/compose.yaml up -d
```

### 2.2. Kiểm tra trạng thái container

```bash
docker compose -f infra/docker/compose.yaml ps
```

Container cần hiển thị trạng thái `Up` và `(healthy)`.

### 2.3. Xem log dịch vụ

```bash
docker compose -f infra/docker/compose.yaml logs -f postgres
```

### 2.4. Dừng dịch vụ

```bash
# Dừng container (dữ liệu vẫn được bảo toàn trong Docker Volume findback_postgres_data)
docker compose -f infra/docker/compose.yaml down
```

Nếu muốn xóa toàn bộ dữ liệu (cẩn trọng):

```bash
docker compose -f infra/docker/compose.yaml down -v
```
