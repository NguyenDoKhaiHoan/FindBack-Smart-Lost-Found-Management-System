# FindBack — Smart Lost & Found Management System

FindBack là nền tảng quản lý tin mất đồ và nhặt được đồ, gợi ý các tin liên quan, hỗ trợ xác minh quyền sở hữu và ghi nhận quá trình trao trả.

**Trạng thái:** khởi tạo cấu trúc dự án và tài liệu. Chưa có ứng dụng chạy được, API nghiệp vụ, database migration hay cấu hình triển khai hoàn chỉnh. Các thư mục trống được giữ trong Git bằng `.gitkeep`.

Tài liệu nền tảng: [Phân tích hệ thống FindBack](https://docs.google.com/document/d/1F8Ngu5ViIxa2_9FLnt-T6s5GJ4o-B8GCtC_KmvlPFOg/edit?usp=sharing).

## 1. Mục tiêu và phạm vi MVP

Luồng cần trình diễn:

```text
Đăng tin LOST / FOUND → tìm kiếm, gợi ý → gửi claim
→ xác minh quyền sở hữu → trao trả → đóng hồ sơ
```

- Người dùng: đăng ký/đăng nhập, quản lý hồ sơ và tin, tìm kiếm, gửi bằng chứng, xác nhận trao trả, nhận thông báo.
- Quản trị viên: xử lý báo cáo, kiểm duyệt tin và xem thống kê.
- Matching theo quy tắc chỉ đưa ra gợi ý; không tự xác nhận chủ sở hữu.
- Vai trò đơn vị quản lý địa điểm và AI matching hình ảnh/LLM nằm ngoài MVP; AI matching thuộc P2.

## 2. Kiến trúc và công nghệ dự kiến

Áp dụng **Modular Monolith**: một backend, chia theo 5 module nghiệp vụ; chưa tách thành microservices.

```text
React UI → FastAPI routers → services → repositories → PostgreSQL
```

| Thành phần | Công nghệ dự kiến | Vai trò |
| --- | --- | --- |
| Frontend | React | Giao diện người dùng và quản trị |
| Backend | Python, FastAPI, Pydantic | API và kiểm tra dữ liệu |
| Persistence | PostgreSQL, SQLAlchemy | Lưu trữ, truy vấn và giao dịch |
| Migration | Alembic | Quản lý thay đổi schema |
| Kiểm thử backend | pytest | Kiểm thử nghiệp vụ, quyền và tích hợp |
| Môi trường | Docker Compose | Chạy các thành phần khi có cấu hình |
| Quản lý công việc | GitHub Projects | Theo dõi phân công và tiến độ |

Chưa chốt phiên bản công nghệ hoặc công cụ build frontend. Dependency, lockfile và lệnh chạy sẽ được thêm khi khởi tạo ứng dụng thực tế.

## 3. Cấu trúc thư mục

```text
FindBack/
├── backend/
│   ├── app/
│   │   ├── api/                  # Tập hợp router và dependency chung
│   │   ├── core/                 # Cấu hình, JWT/RBAC, logging
│   │   ├── db/                   # Kết nối, session, metadata
│   │   ├── shared/               # Tiện ích, lỗi và thành phần dùng chung
│   │   └── modules/
│   │       ├── identity/         # TV1: Identity & User
│   │       ├── posts/            # TV2: Lost & Found Posts
│   │       ├── matching/         # TV3: Search & Matching
│   │       ├── claims_returns/   # TV4: Claims & Returns
│   │       └── notifications_admin/ # TV5: Notifications & Admin
│   ├── alembic/versions/         # Migration tương lai
│   └── tests/
│       ├── unit/                # Logic từng module
│       ├── integration/         # Database, transaction, liên module
│       └── api/                 # HTTP, auth, RBAC, dữ liệu trả về
├── frontend/
│   ├── public/
│   ├── src/
│   │   ├── app/                 # Khởi tạo ứng dụng, routes, providers
│   │   ├── assets/
│   │   ├── components/ui/       # Thành phần giao diện tái sử dụng
│   │   ├── features/
│   │   │   ├── auth/
│   │   │   ├── profile/
│   │   │   ├── posts/
│   │   │   ├── search_matching/
│   │   │   ├── claims_returns/
│   │   │   ├── notifications/
│   │   │   └── admin/
│   │   ├── hooks/
│   │   ├── lib/                 # HTTP client và tiện ích dùng chung
│   │   └── styles/
│   └── tests/
│       ├── unit/
│       └── e2e/
├── docs/
│   ├── requirements.md          # Phạm vi, BR-01 đến BR-09, quy tắc
│   ├── architecture.md          # Ranh giới module và quy ước tầng
│   ├── api/endpoints.md         # Danh sách sơ bộ 30 API
│   ├── database/README.md       # 11 bảng dự kiến, ràng buộc cần thiết kế
│   ├── roadmap.md               # Lộ trình tương đối 21 ngày
│   └── testing.md               # Kế hoạch kiểm thử và tiêu chí MVP
├── infra/docker/                # Dockerfile, Compose trong giai đoạn sau
├── scripts/                     # Script setup, seed demo, tác vụ dự án
├── .editorconfig
├── .env.example                 # Mẫu biến môi trường, không chứa secret thật
├── .gitattributes               # Chuẩn hóa dòng LF giữa các hệ điều hành
├── .gitignore
└── README.md
```

Mỗi module backend có cùng cấu trúc `routers/`, `schemas/`, `services/`, `repositories/`, `models/`. Hướng dẫn chi tiết tại [backend/README.md](backend/README.md) và [frontend/README.md](frontend/README.md).

## 4. Phân công 5 module backend

| Thành viên | Thư mục | Phạm vi | Đầu ra theo phân tích |
| --- | --- | --- | --- |
| TV1 | `identity` | JWT, RBAC, tài khoản, hồ sơ; hỗ trợ kiến trúc | 6 API + test xác thực/phân quyền |
| TV2 | `posts` | Tin LOST/FOUND, ảnh, ownership, trạng thái | 6 API + test ownership/validation |
| TV3 | `matching` | Danh mục, tìm kiếm, chấm điểm và giải thích gợi ý | 5 API + test matching |
| TV4 | `claims_returns` | Claim, bằng chứng riêng tư, xác minh, trao trả | 7 API + test giao dịch/trạng thái |
| TV5 | `notifications_admin` | Thông báo, báo cáo, kiểm duyệt, thống kê | 6 API + test quyền admin |

## 5. Quy tắc nghiệp vụ cần giữ

- Đăng tin, gửi claim và xác nhận trao trả yêu cầu đăng nhập; chỉ chủ tin được sửa tin.
- Bằng chứng và đặc điểm bí mật không được lộ qua API công khai, ảnh công khai hoặc matching.
- Không tự claim tin của mình; chặn claim trùng đang mở.
- Claim: `PENDING → APPROVED / REJECTED / CANCELLED`.
- Return: `ARRANGED → HANDED_OVER → CONFIRMED`; chỉ tạo từ claim đã duyệt.
- Chỉ đóng tin sau khi thỏa điều kiện xác nhận; mọi quyết định và bàn giao phải có audit log.
- Xử lý cạnh tranh giữa nhiều claim bằng transaction và constraint; hỗ trợ hủy/báo cáo tranh chấp theo chính sách sẽ chốt.

Chi tiết và các điểm còn cần thống nhất nằm trong [yêu cầu nghiệp vụ](docs/requirements.md).

## 6. Bắt đầu làm việc

```bash
git clone https://github.com/NguyenDoKhaiHoan/FindBack-Smart-Lost-Found-Management-System.git
cd FindBack-Smart-Lost-Found-Management-System
git switch -c feat/identity-auth
```

1. Đọc [kiến trúc](docs/architecture.md), [API](docs/api/endpoints.md) và [dữ liệu](docs/database/README.md).
2. Chọn module theo phân công; thống nhất request/response, mã lỗi và schema trước khi triển khai.
3. Khởi tạo dependency và entrypoint của backend/frontend; bổ sung hướng dẫn chạy tương ứng.
4. Nếu dùng cấu hình local, sao chép `.env.example` thành `.env` và thay giá trị mẫu. Hiện chưa có chương trình đọc các biến này.
5. Bổ sung migration và kiểm thử cho nghiệp vụ được triển khai, rồi mở pull request.

Hiện chưa thể chạy `uvicorn`, `npm run dev`, `pytest` hoặc `docker compose up` từ bộ khung này. Không có test chức năng nào được triển khai ở commit khởi tạo.

## 7. Quy ước cộng tác

- Nhánh tính năng: `feat/<module>-<noi-dung>`; sửa lỗi: `fix/<noi-dung>`; tài liệu: `docs/<noi-dung>`.
- Commit mô tả thay đổi cụ thể, ví dụ `feat(identity): add login endpoint`.
- Pull request nêu hành vi thay đổi, API/schema bị ảnh hưởng và cách đã kiểm tra.
- Không commit `.env`, token, mật khẩu, dữ liệu cá nhân, bằng chứng sở hữu hoặc file upload.
- Cập nhật tài liệu khi thay đổi yêu cầu, trạng thái, API hoặc cách chạy.

## 8. Lộ trình và nghiệm thu

Lộ trình kéo dài **21 ngày kể từ ngày nhóm bắt đầu**, theo [roadmap](docs/roadmap.md). MVP đạt yêu cầu khi chạy được toàn bộ luồng từ đăng tin đến xác nhận trao trả, bảo vệ bằng chứng riêng tư, kiểm soát quyền và ngăn xung đột claim. Xem [kế hoạch kiểm thử](docs/testing.md).
