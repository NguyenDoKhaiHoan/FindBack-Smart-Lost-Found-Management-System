# Hạ tầng dự kiến

`docker/` dành cho Dockerfile và Docker Compose sau khi backend/frontend có entrypoint và dependency.

Khi triển khai cần bổ sung cấu hình chạy backend, frontend, PostgreSQL, health check, migration, volume và biến môi trường. Tách dữ liệu PostgreSQL, ảnh tin và bằng chứng riêng tư khỏi source code. Không nhúng secret vào image hay commit file `.env`.

Hiện chưa có file Compose hoặc container chạy được. Chỉ bổ sung hướng dẫn triển khai sau khi đã kiểm chứng cấu hình thực tế.
