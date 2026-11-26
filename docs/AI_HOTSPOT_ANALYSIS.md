# FindBack AI Lost-Item Hotspot Analysis

FindBack dùng DBSCAN với khoảng cách Haversine để nhóm các báo cáo mất đồ theo vị trí. Bản đồ công khai ở `/ban-do-that-lac`. Quản trị viên mở **Quản trị → Phân tích thất lạc** hoặc vào `/quan-tri/phan-tich-that-lac`.

## Phân quyền và dữ liệu

| Đối tượng | Quyền trên backend |
| --- | --- |
| Khách, USER | Xem bản đồ tổng hợp và các liên kết tới bài đăng công khai trong cụm đủ điều kiện. |
| Chủ tin LOST | Chọn, thay đổi hoặc bỏ đóng góp một ghim gần đúng cho tin của mình. |
| ADMIN | Xem số liệu toàn hệ thống về báo cáo có vị trí, biểu đồ, so sánh theo kỳ, cấu hình DBSCAN, phân tích lại và tải CSV. |
| LOCATION MANAGER | FindBack hiện chỉ cấp vai trò USER và ADMIN. Dashboard theo địa điểm và phân công manager chưa có trong mô hình quyền hiện tại. |

Chỉ báo cáo LOST đủ dữ liệu, người đăng đã chọn đóng góp vị trí, tin công khai còn hoặc đã đóng, có thời điểm xảy ra hợp lệ mới được dùng. Tin FOUND, tin ẩn, tin đã xóa, tọa độ thiếu hoặc sai và thời điểm tương lai bị loại. Báo cáo trùng người đăng, phút xảy ra, vị trí, danh mục và tên đồ được gộp khi tiêu đề cũng trùng sau chuẩn hóa. Tọa độ của tin lịch sử chưa chọn tham gia giữ nguyên trong cơ sở dữ liệu.

Ghim đóng góp được lưu tới ba chữ số thập phân. Công chúng chỉ nhận tâm cụm làm tròn tới hai chữ số và cụm từ ít nhất năm tài khoản khác nhau. Các mục danh mục và khung giờ công khai cần ít nhất ba báo cáo. Dữ liệu riêng theo giờ, tọa độ từng tin và điểm nhiễu không xuất hiện trong API công khai. API bài đăng liên quan trả mã tin, tiêu đề công khai đã che email và số điện thoại nhận dạng được, và ngày xảy ra. Chủ tin đọc vị trí mình đã góp qua endpoint xác thực riêng.

Tổng số trên bản đồ công khai là số báo cáo thuộc các cụm đủ điều kiện công bố. Trang quản trị đếm cả báo cáo có vị trí nằm ngoài cụm. Mật độ là mức tương đối dựa trên số báo cáo trong kỳ, không phải xác suất dự báo mất đồ.

## Kiến trúc

1. Biểu mẫu tin LOST giữ tọa độ tùy chọn trong các trường `posts.latitude`, `posts.longitude` hiện có. `posts.hotspot_zone` lưu nhóm địa điểm công cộng do chủ tin chọn và biểu thị việc đồng ý đóng góp.
2. `HotspotService` đọc và chuẩn hóa dữ liệu, áp dụng bộ lọc, loại trùng, rồi gọi `clustering.py`. Scikit-learn nhận tọa độ theo radian, với `eps` theo mét chia cho bán kính Trái Đất 6.371.008,8 m. Mặc định `eps=200 m`, `min_samples=5`. Nhãn `-1` là nhiễu. Các ghim trùng tọa độ được nén và đếm bằng `sample_weight`.
3. Ngưỡng mặc định theo số báo cáo mỗi cụm là thấp dưới 10, trung bình từ 10, cao từ 20 và rất cao từ 35. Một cụm được đặt tên bằng loại địa điểm công cộng và thành phố chiếm nhiều báo cáo nhất trong cụm.
4. Ngày và khung hai giờ dùng UTC+7. Kỳ trước có cùng số ngày lịch và tiếp giáp kỳ đang xem. So sánh của từng cụm dựa trên báo cáo kỳ trước nằm trong `eps` của thành viên cụm gần nhất. Hiện phần trăm thay đổi khi cả hai kỳ có ít nhất năm báo cáo.
5. API công khai, quản trị và bốn công cụ chatbot dùng chung service. Backend lấy quyền chatbot từ JWT đã xác thực và tài khoản trong DB. Mô hình OpenAI chỉ chọn công cụ và tham số. Câu trả lời số liệu và nhận xét dashboard được dựng từ kết quả thống kê bằng quy tắc, không gửi dữ liệu thô hoặc tọa độ cá nhân đến mô hình.
6. Cache theo phạm vi quyền, bộ lọc, kỳ, cấu hình và phiên bản dữ liệu xác định từ số lượng tin và thời điểm cập nhật gần nhất. Cache mỗi tiến trình giữ tối đa 24 mục trong 90 giây. Mỗi kỳ xử lý tối đa 6.000 báo cáo, phản hồi trả tối đa 100 cụm và 12 tin cho mỗi cụm. API gắn `truncated` khi chạm giới hạn. Di chuyển bản đồ chỉ vẽ lại phía trình duyệt.
7. Giao diện dùng React Leaflet và lớp Canvas simpleheat. Màu từ xanh lá, vàng, cam đến đỏ thể hiện mức mật độ. Bản đồ nền tải khi người dùng mở bản đồ, có attribution hiển thị và không tải trước. [Chính sách ô bản đồ OpenStreetMap](https://operations.osmfoundation.org/policies/tiles/)

## API

FastAPI có hợp đồng theo kiểu dữ liệu tại `/openapi.json` và Swagger ở `/docs` của backend.

| Phương thức và đường dẫn | Quyền và tác dụng |
| --- | --- |
| `GET /api/ai/hotspots` | Công khai. Kỳ, cụm, điểm nhiệt và thống kê tổng hợp. |
| `GET /api/ai/hotspots/heatmap` | Công khai. Các tâm cụm đã làm tròn và trọng số theo mật độ. |
| `GET /api/ai/hotspots/statistics` | Công khai. Thống kê từ các cụm đủ điều kiện công bố. |
| `GET /api/ai/hotspots/{cluster_id}` | Công khai. Chi tiết cụm và liên kết tới bài đăng công khai. |
| `GET /api/admin/ai/hotspots` | ADMIN. Báo cáo chi tiết và so sánh kỳ trước. |
| `GET /api/admin/ai/hotspots/{cluster_id}` | ADMIN. Chi tiết cụm, chuỗi thời gian và báo cáo liên quan. |
| `GET /api/admin/ai/hotspots/config` | ADMIN. Đọc cấu hình đã lưu. |
| `PATCH /api/admin/ai/hotspots/config` | ADMIN. Cập nhật cấu hình bền vững. |
| `POST /api/admin/ai/hotspots/recalculate` | ADMIN. Bỏ qua cache để chạy lại với bộ lọc hiện tại. |
| `GET /api/admin/ai/hotspots/export` | ADMIN. Xuất CSV tổng hợp các cụm trong kỳ. |
| `GET /api/v1/posts/{id}/hotspot-location` | Chủ tin. Xem ghim gần đúng đã góp hoặc `null`. |
| `POST /api/v1/posts`, `PATCH /api/v1/posts/{id}` | Trường tùy chọn `latitude`, `longitude`, `hotspot_zone` cho tin LOST. Khi bỏ ghim, gửi ba trường bằng `null`. |

Các API phân tích hỗ trợ `period=7|30|90` hoặc cặp `start_date` và `end_date` (ngày YYYY-MM-DD, tối đa 180 ngày, bao gồm ngày cuối). Các bộ lọc khác gồm `category_id` (UUID), `location_id` (mã thành phố trong FindBack), `zone` (nhóm địa điểm) và `group_by=day|week|month`. Đọc chi tiết cụm với đúng bộ lọc đã dùng để lấy danh sách. Mã cụm có thể đổi khi thành viên đổi. API trả 404 cho cụm ngoài phạm vi kết quả, 401 khi thiếu xác thực, 403 khi thiếu quyền, 422 cho tham số sai và 503 nếu phân tích đang bận.

Cấu hình quản trị cho phép `eps_meters` từ 50–1.000, `min_samples` từ 3–50, `period_days` từ 7–90 và ba ngưỡng mật độ tăng dần bắt đầu từ `min_samples`. Giới hạn công bố năm tài khoản được giữ độc lập với cấu hình.

Chatbot có `get_lost_item_hotspots`, `get_hotspot_statistics`, `get_top_lost_categories` và `get_peak_lost_hours`. Có thể hỏi “Trong 30 ngày qua, khu vực nào có nhiều báo cáo mất đồ?” hoặc “Ở thư viện thường mất đồ vào khung giờ nào?”. Chatbot hiện lọc khu vực theo danh mục địa điểm và thành phố, ví dụ Thư viện ở Hà Nội. Câu hỏi về một địa chỉ cụ thể hoặc phạm vi quản lý chưa được mô hình hóa sẽ được giải thích thay vì suy đoán.

## Migration và thư viện

- `0007_hotspot_analysis` thêm `posts.hotspot_zone`, chỉ mục `ix_posts_hotspot_period` và bảng singleton `hotspot_settings`. Tin cũ có `hotspot_zone = NULL`. Không điền tọa độ giả, không thay đổi các trường tọa độ cũ.
- Backend thêm `scikit-learn` vào dependencies mặc định và dùng NumPy hiện có. Chạy CPU, không cần nhóm PyTorch.
- Frontend thêm `leaflet`, `react-leaflet`, `simpleheat` và `@types/leaflet`. Biểu đồ dùng HTML và SVG. Map tải theo nhu cầu.
- Tile mặc định từ OSM. Có thể cấu hình `VITE_HOTSPOT_TILE_URL` khi nhà cung cấp thay đổi, kèm attribution theo giấy phép của nhà cung cấp. [React Leaflet](https://react-leaflet.js.org/docs/start-installation/) · [Scikit-learn DBSCAN](https://scikit-learn.org/stable/modules/generated/sklearn.cluster.DBSCAN.html)

## Chạy backend và frontend

Dùng cấu hình local hiện có, gồm `JWT_SECRET_KEY`, `DATABASE_URL` và `CORS_ORIGINS` phù hợp với frontend. Cấu hình `OPENAI_API_KEY` tại backend để dùng lựa chọn công cụ trong chatbot.

```powershell
Set-Location backend
uv sync --locked
uv run --no-sync alembic upgrade head
uv run --no-sync uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000
```

Từ terminal khác, tại thư mục repository

```powershell
Set-Location frontend
npm ci
$env:VITE_API_BASE_URL = 'http://127.0.0.1:8000'
npm run dev
```

## Demo tách riêng

Từ thư mục `backend`, tạo cơ sở SQLite riêng. Script chỉ chạy khi chế độ và tên DB trùng cấu hình demo dưới đây. Chọn thư mục và cổng riêng nếu đang chạy FindBack local cho dữ liệu thường.

```powershell
$env:APP_ENV = 'hotspot-demo'
$env:DATABASE_URL = 'sqlite:///./findback-hotspot-demo.db'
$env:JWT_SECRET_KEY = [Guid]::NewGuid().ToString('N') + [Guid]::NewGuid().ToString('N')
$env:HOTSPOT_DEMO_PASSWORD = '<mật khẩu demo ít nhất 12 ký tự>'
$env:CORS_ORIGINS = 'http://127.0.0.1:5173'
uv run --locked python -m app.modules.hotspots.demo create
uv run --no-sync uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000
```

Seed cố định tạo 184 báo cáo giả lập từ nhiều tài khoản tại sáu nhóm địa điểm và một số vị trí nhiễu. Ngày được tạo tương đối với ngày seed để xem được kỳ hiện tại và kỳ trước. Bản đồ hiện nhãn **Dữ liệu giả lập** khi dùng backend demo. Chạy lại `create` không nhân đôi báo cáo. Muốn làm mới mốc ngày, xóa báo cáo demo rồi seed lại. Với cùng cấu hình, dùng `uv run --locked python -m app.modules.hotspots.demo delete` để xóa đúng các báo cáo do seed tạo. Các tài khoản demo được giữ để đăng nhập lại.

1. Ở chế độ khách, mở `/ban-do-that-lac`. Chọn **30 ngày**, lọc **Thư viện**, bật hoặc tắt bản đồ nhiệt và điểm nóng. Nhấn cụm rồi mở một bài đăng liên quan.
2. Đăng nhập `hotspot-user@example.org` bằng mật khẩu demo. Xác nhận tài khoản bị chặn ở đường dẫn quản trị. Đăng tin mất đồ, chọn **Góp vị trí gần đúng vào Bản đồ thất lạc**, chọn loại địa điểm và đặt ghim. Mở sửa tin để đổi hoặc bỏ ghim.
3. Đăng nhập `hotspot-admin@example.org` bằng cùng mật khẩu. Mở phân tích, chọn gộp theo tuần hoặc tháng, đối chiếu kỳ trước, đổi bán kính DBSCAN, phân tích lại và tải CSV.
4. Với OpenAI đã được cấu hình, hỏi chatbot về khung giờ hoặc địa điểm báo mất nhiều. Dữ liệu demo được ghi rõ trong câu trả lời. Các kiểm thử gọi bốn công cụ cũng chạy với phản hồi mô hình giả lập.

## Kiểm thử và phạm vi

```powershell
# backend
uv run --no-sync ruff check app tests alembic
uv run --no-sync pytest -q

# frontend
npm run lint
npm test
npm run build
```

Kiểm thử backend gồm Haversine, DBSCAN, nhiễu, tọa độ lỗi, loại trùng, quyền và phạm vi, cấu hình, cache sau sửa ghim, CSV, lịch sử theo kỳ và bốn công cụ chatbot. Kiểm thử frontend bao gồm dữ liệu rỗng, lỗi API và thử lại, bộ lọc và liên kết công khai. Các luồng này cũng được thử trên trình duyệt với backend demo, gồm canvas heatmap, popup, tài khoản USER/ADMIN, lưu ghim và tải CSV.

Kết quả kiểm thử ngày 26/11/2026

- Backend 290 đạt, 9 bài dành cho PostgreSQL được bỏ qua trong môi trường SQLite. Kiểm tra nâng và hạ migration SQLite xác nhận các tọa độ cũ vẫn đúng giá trị.
- Frontend 42 đạt. Lint, TypeScript và bản build production đều đạt.
- Demo 184 báo cáo sinh sáu cụm công khai trong kỳ mặc định. Kiểm tra Postman xác nhận nhãn demo, độ làm tròn tọa độ, heatmap và yêu cầu xác thực ở API quản trị.
- Hai câu hỏi qua OpenAI thật được đối chiếu với API demo theo khu vực nhiều báo cáo nhất và khung giờ cao điểm tại thư viện.

## Tệp triển khai

- `backend/app/modules/hotspots/{clustering,service,schemas,router,models,demo}.py`
- `backend/alembic/versions/0007_hotspot_analysis.py`, `backend/app/db/models.py`, `backend/app/main.py`
- `backend/app/modules/posts/{models/post,schemas/post,routers/post_router,services/catalog,services/listings}.py`
- `backend/app/modules/ai/{chat,chat_hotspots,router,schemas}.py`
- `backend/{pyproject.toml,uv.lock}`, `frontend/{package.json,package-lock.json}`
- `frontend/src/features/hotspots/`, `frontend/src/vite-env.d.ts`
- `frontend/src/{app/App,components/layout/AppLayout,features/admin/AdminPage,features/posts/PublicPages}.tsx`, `frontend/src/lib/api/system.ts`, `frontend/src/features/ai/{api.ts,ChatWidget.tsx}`
- `backend/tests/unit/test_hotspot_clustering.py`, `backend/tests/api/{test_hotspots,test_ai,test_system}.py`, `frontend/src/features/hotspots/HotspotDashboard.test.tsx`

Tính năng theo vai trò LOCATION MANAGER cần hệ thống phân công địa điểm trước khi có thể triển khai an toàn. Nhận xét trên dashboard dùng quy tắc thống kê và hoạt động độc lập với OpenAI. FindBack không xác định tên tòa nhà cụ thể qua geocoding ở phiên bản này, chỉ dùng nhóm địa điểm công cộng và thành phố do người đăng chọn.
