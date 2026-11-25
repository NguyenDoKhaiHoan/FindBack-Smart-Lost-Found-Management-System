# Tính năng AI của FindBack

FindBack chạy bốn chức năng trên ứng dụng React và FastAPI hiện có. Gợi ý đối chiếu và tìm ảnh chạy trên CPU. Tạo bản nháp và chatbot gọi OpenAI Responses API từ backend.

## Chạy local

Tại thư mục gốc, dùng cấu hình PostgreSQL hiện có trong `.env` và khởi động dịch vụ nếu cần.

```powershell
docker compose --env-file .env -f infra/docker/compose.yaml up -d postgres
cd backend
uv sync --locked --group ai
uv run --locked --group ai alembic upgrade head
uv run --locked --group ai python -m app.modules.ai.index
uv run --locked --group ai uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000
```

Lệnh `app.modules.ai.index` tải trọng số khi cần và tạo trước embedding từ tin đang mở. Có thể chạy lại sau khi nhập nhiều tin hoặc đổi phiên bản mô hình. Mô hình cũng được nạp khi có yêu cầu đầu tiên. Kiểm tra kết nối đến Hugging Face và dành vài GB cho PyTorch, trọng số và bộ nhớ đệm. Nhóm `ai` dùng bản CPU của PyTorch trên Windows và Linux x64. Gói nhẹ `openai` đã có trong nhóm phụ thuộc mặc định.

Nếu ổ hệ thống thiếu chỗ, đặt các biến sau trước khi chạy các lệnh `uv`, migration, lập chỉ mục và khởi động API. Đổi thư mục theo ổ đĩa có sẵn.

```powershell
$env:UV_PROJECT_ENVIRONMENT = 'D:/FindBack-AI/.venv'
$env:UV_CACHE_DIR = 'D:/FindBack-AI/uv-cache'
$env:HF_HOME = 'D:/FindBack-AI/huggingface'
$env:TORCH_HOME = 'D:/FindBack-AI/torch'
```

Mở terminal khác tại thư mục gốc.

```powershell
cd frontend
npm ci
npm run dev
```

Mở [FindBack local](http://127.0.0.1:5173) và [Swagger](http://127.0.0.1:8000/docs). Nếu `frontend/.env.local` có `API_PROXY_TARGET`, dùng cổng backend tương ứng. Trên bản local hiện tại, proxy dùng cổng 8002.

### OpenAI

Thêm các biến sau vào `.env` ở thư mục gốc hoặc `backend/.env`, rồi khởi động lại backend. Biến môi trường của tiến trình được ưu tiên. Hai biến model phải là tên model mà tài khoản API có quyền sử dụng. GPT-4.1 mini hỗ trợ cả ảnh đầu vào, function calling và structured outputs. [Tài liệu model](https://developers.openai.com/api/docs/models/gpt-4.1-mini)

```dotenv
OPENAI_API_KEY=
OPENAI_CHAT_MODEL=gpt-4.1-mini
OPENAI_VISION_MODEL=gpt-4.1-mini
OPENAI_TIMEOUT_SECONDS=30
AI_MATCHING_ENABLED=true
AI_IMAGE_SEARCH_ENABLED=true
AI_AUTO_POST_ENABLED=true
AI_CHATBOT_ENABLED=true
AI_CPU_THREADS=2
AI_TEXT_INDEX_BATCH=32
AI_IMAGE_INDEX_BATCH=12
AI_REQUESTS_PER_MINUTE=12
AI_GLOBAL_REQUESTS_PER_MINUTE=40
```

Điền khóa của dự án OpenAI vào `OPENAI_API_KEY`. Giữ khóa ở backend và để các tệp `.env` ngoài Git. Tạo bản nháp và chatbot cần JWT FindBack. Backend giới hạn mỗi tác vụ ở 12 yêu cầu/phút cho mỗi tài khoản hoặc IP và 40 yêu cầu/phút cho toàn bộ tiến trình theo mặc định. Tạo bản nháp gọi OpenAI một lần với tối đa 450 token đầu ra. Chatbot dùng tối đa 350 token để chọn thao tác và thêm tối đa 300 token khi cần soạn lời giải thích hoặc tư vấn. Ảnh bản nháp gửi OpenAI đã bỏ metadata và được thu nhỏ xuống cạnh dài tối đa 768 px.

## API

| Phương thức và đường dẫn | Đầu vào | Kết quả |
| --- | --- | --- |
| `GET /api/ai/matches/{item_id}` | UUID của tin công khai | Tối đa 5 tin khác loại, điểm 0–1, lý do và dữ liệu hiển thị |
| `POST /api/ai/image-search` | Form gồm `file` hoặc `image_id` công khai, tùy chọn `type` và `category_id` | Tối đa 5 tin đang mở, mỗi tin lấy ảnh có điểm cao nhất |
| `POST /api/ai/generate-post` | Form gồm `file`, Bearer JWT | `title`, tên và UUID danh mục, mã màu, `description`, ghi chú kiểm tra bản nháp |
| `POST /api/ai/chat` | JSON gồm `message` tối đa 500 ký tự, `conversation_id` tùy chọn, một thao tác nhanh như `compare: {first, second}` và Bearer JWT | `reply`, UUID hội thoại, `related_items`, hành động giao diện và trạng thái chọn tin |
| `POST /api/ai/chat/image-search` | Form gồm `file`, `conversation_id` tùy chọn và Bearer JWT | Kết quả tin có ảnh tương tự trong hội thoại |

Các yêu cầu POST gửi `Content-Length`. Tệp nhận JPEG, PNG và WebP, tối đa 5 MiB và 16 triệu pixel. Kết quả tìm ảnh và gợi ý có `indexing_pending` nếu còn dữ liệu chờ lập chỉ mục.

## Kiến trúc và dữ liệu

- **Đối chiếu tin.** Sentence Transformers dùng `paraphrase-multilingual-MiniLM-L12-v2` để mã hóa tiêu đề và mô tả công khai. Backend dùng cosine và trọng số 50% ngữ nghĩa, 12% danh mục, 8% màu, 20% địa điểm và 10% thời gian. Các thành phần thiếu được bỏ khỏi mẫu số. Giữ đúng cặp LOST–FOUND đang mở, lọc thời điểm nhặt sớm hơn thời điểm mất và xếp theo điểm. Điểm phục vụ việc tìm tin liên quan. Quyền sở hữu vẫn được xử lý qua luồng xác minh hiện có. [Model card](https://huggingface.co/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2)
- **Tìm ảnh.** OpenCLIP dùng `ViT-B-32-quickgelu` với trọng số `openai` và nhận diện các loại đồ phổ biến ngay trên CPU. Hệ thống đối chiếu loại đồ từ ảnh và tiêu đề tin để ưu tiên đúng nhóm, đồng thời giảm các kết quả có điểm ảnh yếu. Giao diện hiển thị loại đồ nhận diện được và phân biệt kết quả trùng loại với ảnh rất giống. Kho ảnh dùng byte trong PostgreSQL và có đường đọc ảnh cũ từ `MEDIA_ROOT`. Tìm từ ảnh của tin loại chính tin nguồn khỏi kết quả. [OpenCLIP](https://github.com/mlfoundations/open_clip)
- **Bản nháp.** OpenAI Vision trả JSON theo schema. Backend kiểm tra lại bằng Pydantic và ánh xạ danh mục đang hoạt động. Bản nháp có thể chỉnh sửa độc lập. Nút **Áp dụng vào biểu mẫu** điền các trường được chọn. Nút **Đăng tin** của form tiếp tục dùng API quản lý tin hiện có. [OpenAI Vision](https://developers.openai.com/api/docs/guides/images-vision)
- **Chatbot.** FastAPI kiểm tra JWT và chặn yêu cầu rõ ràng về mật khẩu, thông tin riêng tư và vượt quyền trước khi gọi OpenAI. Model chọn một công cụ được phép hoặc từ chối nội dung ngoài FindBack. Backend kiểm tra tham số, quyền truy cập và che các mẫu thông tin nhạy cảm phổ biến. Với câu hỏi tiếp nối và tình huống cần tư vấn, model có thể soạn lời giải thích từ dữ kiện của tin hoặc hướng dẫn FindBack, rồi hỏi thêm khi thiếu thông tin. Thẻ tin và lý do xếp hạng vẫn lấy từ kết quả của backend. Hội thoại giữ ba lượt gần nhất trong bộ nhớ tối đa 30 phút. [OpenAI function calling](https://developers.openai.com/api/docs/guides/function-calling)
- **Lưu embedding.** Migration `0005_ai_embeddings` thêm `ai_embedding_key` và `ai_embedding` dạng JSON vào `posts` và `post_images`. Fingerprint giúp tái lập chỉ mục khi văn bản, mô hình hoặc tệp ảnh cũ thay đổi. Truy vấn công khai loại tin đã ẩn, xóa hoặc hoàn tất. Mỗi worker giới hạn một phiên suy luận CPU và một yêu cầu chờ. Các API đối chiếu theo quy tắc tại `/api/v1/matches` tiếp tục phục vụ luồng hiện có.

## Demo

1. Đăng hai tin có cùng món đồ, một tin mất và một tin nhặt được. Đặt thời điểm nhặt sau thời điểm mất. Mở trang chi tiết để xem ảnh, điểm và lý do gợi ý.
2. Vào **Khám phá → Tìm đồ bằng hình ảnh**. Chọn ảnh và bấm **Tìm đồ tương tự**. Có thể bắt đầu từ liên kết trong chi tiết tin có ảnh. Bộ lọc loại tin và danh mục trên trang khám phá cũng áp dụng cho kết quả ảnh.
3. Đăng nhập, mở **Đăng tin**, chọn ảnh và bấm **Tạo mô tả bằng AI**. Sửa nội dung nháp, bấm **Áp dụng vào biểu mẫu**, điền địa điểm và thời điểm rồi bấm **Đăng tin**.
4. Mở **FindBack AI Assistant** ở góc dưới bên phải. Thử hỏi “Tìm giúp tôi ví đen gần thư viện” hoặc “Có gợi ý nào cho tin mất đồ của tôi?”. Mở một kết quả hoặc chọn tin của mình để xem gợi ý.
5. Bấm biểu tượng ảnh trong chat, chọn ảnh rồi bấm **Tìm bằng ảnh**. Ảnh được xử lý cục bộ bằng OpenCLIP và chỉ dùng cho lượt tìm. Khi có từ hai kết quả, bấm **So sánh 2 tin đầu** hoặc nhập “So sánh tin số 2 và tin số 3” nếu có đủ số tin. Chatbot đối chiếu loại tin, thời gian và địa điểm đã đăng.

## Kiểm thử và xử lý lỗi

```powershell
cd backend
uv run --locked pytest -q tests/api/test_ai.py tests/unit/matching/test_ai_scoring.py
uv run --locked ruff check app tests alembic
cd ../frontend
npm test
npm run lint
npm run build
```

Test tích hợp dùng OpenAI SDK thật với HTTP transport mô phỏng. Các test kiểm tra định dạng request, lỗi upstream, công cụ chatbot, quyền sở hữu, lọc tin công khai, kiểm tra ảnh và bộ nhớ đệm embedding. API chạy được với SQLite trong test và PostgreSQL local.

Playwright kiểm tra bốn luồng với SQLite tạm, mô hình CPU thật và phản hồi OpenAI mô phỏng. Trên PostgreSQL, 15 kiểm thử API AI đã qua trên database riêng và migration đã áp dụng cho database FindBack local. Tạo bản nháp và chatbot cần khóa hợp lệ để thử với OpenAI thật.

| Lỗi | Cách xử lý |
| --- | --- |
| `AI_NOT_CONFIGURED` | Kiểm tra khóa, tên model và quyền dự án OpenAI, rồi khởi động lại backend. |
| `AI_DISABLED` | Kiểm tra biến bật tính năng tương ứng. |
| `AI_MODEL_UNAVAILABLE` | Cài nhóm `ai`, kiểm tra bộ nhớ đệm và kết nối tải trọng số. |
| `AI_BUSY`, `AI_TIMEOUT`, `AI_RATE_LIMIT` | Thử lại sau. Kiểm tra hạn mức dự án nếu yêu cầu OpenAI liên tục bị giới hạn. |
| `AI_CONVERSATION_NOT_FOUND` | Chọn **Cuộc trò chuyện mới** sau khi phiên hết hạn hoặc backend khởi động lại. |
| `indexing_pending: true` | Tìm lại để xử lý lô tiếp theo hoặc chạy lệnh lập chỉ mục trên backend. |

Đối chiếu và tìm ảnh quét các vector JSON của tin phù hợp. Thời gian truy vấn tăng theo số tin và ảnh. Hội thoại và hạn mức dùng bộ nhớ từng worker, phù hợp bản local chạy một worker. Tìm kiếm qua chatbot dùng từ khóa và bộ lọc hiện có, nên cách diễn đạt khác biệt có thể cho ít kết quả hơn.

Chatbot có thể tra bản đồ từ địa điểm công khai và ước tính khoảng cách đường chim bay bằng tọa độ của tin hoặc mốc thành phố Hà Nội, TP. Hồ Chí Minh và Đà Nẵng. Với địa chỉ trùng tên, chatbot hỏi thêm quận hoặc địa danh. Nút **Xem chỉ đường** mở Google Maps để tra tuyến đường. Các nút hỏi tiếp về lý do, vị trí và thời gian dùng trực tiếp kết quả gần nhất trong hội thoại. [Dữ liệu tọa độ GeoNames](https://www.geonames.org/VN/largest-cities-in-vietnam.html), [Google Maps URLs](https://developers.google.com/maps/documentation/urls/get-started)

## Tệp triển khai

| Phần | Tệp |
| --- | --- |
| Backend AI | `backend/app/modules/ai/{router,schemas,runtime,inference,matching,images,drafts,chat,index}.py` |
| Tích hợp backend | `backend/app/main.py`, `backend/app/core/config.py`, `backend/app/modules/matching/services/search.py`, `backend/app/modules/posts/models/post.py` |
| Schema và dependencies | `backend/alembic/versions/0005_ai_embeddings.py`, `backend/pyproject.toml`, `backend/uv.lock`, `.env.example` |
| Giao diện AI | `frontend/src/features/ai/{AISearch,AICards,PostDraftAssistant,ChatWidget}.tsx`, `frontend/src/features/ai/api.ts`, `frontend/src/features/ai/ai.css` |
| Tích hợp giao diện | `frontend/src/features/posts/PublicPages.tsx`, `frontend/src/components/layout/AppLayout.tsx`, `frontend/src/lib/api/client.ts` |
| Kiểm thử | `backend/tests/api/test_ai.py`, `backend/tests/unit/matching/test_ai_scoring.py`, `backend/tests/api/test_system.py` |
| Tài liệu | `README.md`, `backend/README.md`, `docs/api/endpoints.md`, `docs/AI_FEATURES.md` |
