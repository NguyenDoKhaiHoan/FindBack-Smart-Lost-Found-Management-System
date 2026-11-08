# Backend FindBack

Backend dự kiến dùng FastAPI, Pydantic, SQLAlchemy, PostgreSQL, Alembic và pytest. Đây là cấu trúc chuẩn bị phát triển; chưa có entrypoint, dependency manifest, migration hoặc API hoạt động.

## Cấu trúc một module

```text
app/modules/<module>/
├── routers/         # HTTP endpoint, dependency và chuyển tiếp đến service
├── schemas/         # Pydantic request/response; tách dữ liệu công khai/riêng tư
├── services/        # Use case, quyền nghiệp vụ, state machine, transaction
├── repositories/    # Truy vấn và ghi dữ liệu bằng session được truyền vào
└── models/          # SQLAlchemy models thuộc module
```

| Module | Chủ trì | Dữ liệu phụ trách |
| --- | --- | --- |
| `identity` | TV1 | users |
| `posts` | TV2 | posts, post_images |
| `matching` | TV3 | categories, matches |
| `claims_returns` | TV4 | claims, claim_evidence, returns |
| `notifications_admin` | TV5 | notifications, reports; điều phối audit_logs |

`audit_logs` phục vụ mọi module; TV5 điều phối cấu trúc và nơi ghi log, từng service chịu trách nhiệm phát sinh sự kiện cho hành động của mình. Đây là quy ước tổ chức đề xuất, cần thống nhất khi thiết kế schema.

## Thư mục dùng chung

- `app/api/`: tập hợp router và dependency HTTP dùng chung.
- `app/core/`: đọc cấu hình, JWT/RBAC, logging; không chứa nghiệp vụ riêng của một module.
- `app/db/`: engine, session, metadata và cơ sở transaction.
- `app/shared/`: exception và tiện ích có nhiều module sử dụng; tránh gom mọi logic vào đây.
- `alembic/versions/`: migration có thứ tự; hiện chưa khởi tạo môi trường Alembic.
- `tests/unit/<module>/`, `tests/integration/`, `tests/api/`: xem [kế hoạch kiểm thử](../docs/testing.md).

## Trước khi chạy được backend

1. Chốt phiên bản Python và khai báo dependency/lockfile.
2. Thêm application factory hoặc entrypoint FastAPI và cấu hình môi trường.
3. Khởi tạo session PostgreSQL, models, Alembic và migration đầu tiên.
4. Mount routers, định nghĩa schemas và triển khai từng use case.
5. Bổ sung fixture, test và lệnh chạy được kiểm chứng vào README này.

Không phục vụ bằng chứng sở hữu bằng static/public route. Đường dẫn upload trong `.env.example` là đề xuất local, không phải cơ chế bảo vệ đã triển khai.
