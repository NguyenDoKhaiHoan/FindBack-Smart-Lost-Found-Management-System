# Backend FindBack

Backend đã có FastAPI entrypoint, dependency và API matching độc lập. SQLAlchemy, PostgreSQL, Alembic và các module nghiệp vụ khác chưa được tích hợp.

## Chạy matching và kiểm thử

Yêu cầu Python 3.12. Từ thư mục `backend`, dùng PowerShell:

```powershell
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements-dev.txt
.venv/Scripts/python -m pytest -q
.venv/Scripts/python -m uvicorn app.demo:create_demo_app --factory
```

Mở `http://127.0.0.1:8000/docs` hoặc gọi:

```text
GET http://127.0.0.1:8000/api/v1/matches?post_id=10000000-0000-4000-8000-000000000001
```

Demo dùng dữ liệu giả trong bộ nhớ và tính sẵn cặp 100 điểm; không lưu sau khi dừng tiến trình. Entry point thật `.venv/Scripts/python -m uvicorn app.main:app` mặc định trả 503 cho matches hợp lệ cho đến khi truyền adapter Posts/generation vào `create_app(reader)`. Không tự chuyển sang seed demo. Chỉ cần `requirements.txt` để chạy, `requirements-dev.txt` thêm test tools.

Chi tiết thuật toán, ranh giới dữ liệu và dependency Posts: [matching-implementation.md](../docs/matching-implementation.md). Chưa triển khai `GET /api/v1/search`, persistence hoặc endpoint tính lại điểm.

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

## Các bước tích hợp backend còn lại

1. Đồng bộ phiên bản/dependency với các module khác; hiện matching chạy bằng Python 3.12 và dependency đã khai báo.
2. Mở rộng application factory hiện có và cấu hình môi trường.
3. Khởi tạo session PostgreSQL, models, Alembic và migration đầu tiên.
4. Mount routers, định nghĩa schemas và triển khai từng use case.
5. Bổ sung fixture, test và lệnh chạy được kiểm chứng vào README này.

Không phục vụ bằng chứng sở hữu bằng static/public route. Đường dẫn upload trong `.env.example` là đề xuất local, không phải cơ chế bảo vệ đã triển khai.
