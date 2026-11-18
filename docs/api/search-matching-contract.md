# KAN-24 — API contract Search & Matching v1

## 1. Phạm vi và trạng thái

Contract cho `GET /api/v1/search` và `GET /api/v1/matches`. Backend truy vấn dữ liệu Posts chung và lưu các lần tính gợi ý trong PostgreSQL. Thuật toán dùng [rules-v1-draft](../matching-rules.md).

Truyền tin nguồn vào `post_id`. Xem cách lấy danh mục, tính lại và đọc chi tiết gợi ý trong [danh mục API](endpoints.md#search-và-matching).

## 2. Quy ước chung

- Cả hai endpoint chỉ đọc dữ liệu công khai, cho phép khách truy cập, không yêu cầu token. Đăng nhập hoặc vai trò admin không mở rộng dữ liệu trả về trên hai endpoint này. Luồng xem dữ liệu riêng tư thuộc API khác.
- Request không có body. Response JSON UTF-8; timestamp xuất ra RFC 3339 UTC với hậu tố `Z`. Query timestamp chấp nhận `Z` hoặc offset; dấu `+` trong URL phải encode `%2B`.
- ID là UUID. Response dùng chữ thường và dấu gạch nối.
- Tất cả query parameter là scalar, xuất hiện tối đa một lần. Tham số lạ, lặp key, chuỗi rỗng (trừ `q`), boolean thay số, số thập phân thay integer hoặc sai enum trả `422`. Tên key và mã enum phân biệt hoa/thường.
- Không truyền query tương đương dùng mặc định. Không chấp nhận chuỗi `null` như giá trị vắng mặt. Độ dài chuỗi tính theo Unicode code point sau URL decode, trước chuẩn hóa.
- Chỉ nhận các trường bộ lọc trong whitelist. Không nhận biểu thức SQL, tên cột tùy ý, JSON thuộc tính tự do, mảng hoặc phép OR.

## 3. Schema bộ lọc và query Search

`GET /api/v1/search`

| Query | Kiểu / ràng buộc | Bắt buộc | Mặc định | Ý nghĩa |
| --- | --- | --- | --- | --- |
| `q` | string, tối đa 200 ký tự | Không | Không lọc từ khóa | Mọi token chuẩn hóa phải có trong title + description công khai |
| `type` | enum `LOST`, `FOUND` | Không | Cả hai | So khớp chính xác loại tin |
| `category_id` | UUID có trong categories | Không | Không lọc | So khớp ID; danh mục tồn tại nhưng inactive vẫn hợp lệ khi tìm tin cũ |
| `location_code` | string 1–50, regex `^[A-Z0-9]+(?:[_-][A-Z0-9]+)*$`, có trong danh mục khu vực của Posts | Không | Không lọc | So khớp mã khu vực, không tìm theo bán kính |
| `event_from` | timestamp RFC 3339 có timezone | Không | Không có cận dưới | `event_time >= event_from` |
| `event_to` | timestamp RFC 3339 có timezone | Không | Không có cận trên | `event_time < event_to` |
| `status` | enum công khai `OPEN`, `CLOSED` | Không | Cả hai trạng thái công khai | Trạng thái khả năng tiếp tục xử lý tin; không phải trạng thái claim |
| `color_code` | enum `BLACK`, `WHITE`, `GRAY`, `RED`, `ORANGE`, `YELLOW`, `GREEN`, `BLUE`, `PURPLE`, `PINK`, `BROWN`, `OTHER` | Không | Không lọc | Một màu chính; không suy ra màu từ văn bản |
| `brand` | string 1–100; không rỗng sau chuẩn hóa | Không | Không lọc | So khớp giá trị brand công khai đã chuẩn hóa |
| `material` | string 1–100; không rỗng sau chuẩn hóa | Không | Không lọc | So khớp giá trị material công khai đã chuẩn hóa |
| `page` | integer 1–10000 | Không | `1` | Số trang, bắt đầu từ 1 |
| `page_size` | integer 1–100 | Không | `20` | Số phần tử tối đa mỗi trang |
| `sort` | enum `newest`, `oldest`, `event_desc`, `event_asc` | Không | `newest` | Thứ tự ở mục 6 |

Tập màu và trạng thái trên là lựa chọn API của bản thiết kế, chưa phải enum DB đã tồn tại. Posts phải ánh xạ trạng thái nội bộ sang `OPEN`/`CLOSED` trước khi tích hợp: `OPEN` còn tiếp nhận xử lý; `CLOSED` đã đóng nhưng còn được phép công khai. Tin bị ẩn/xóa mềm/kiểm duyệt không được trả dù có trạng thái nào. Matching chỉ dùng tin `OPEN` và đủ điều kiện theo Posts. Không tự suy trạng thái từ việc có claim.

Các bộ lọc kết hợp **AND**. Tin thiếu trường tương ứng không thỏa bộ lọc đã chọn. Không có query vẫn trả danh sách tin công khai với mặc định trên. Search không trả score hoặc dùng ngưỡng matching.

Chuẩn hóa `q`: Unicode NFC → chữ thường → thay dấu câu bằng khoảng trắng → gộp khoảng trắng → tách từ → loại từ trùng và từ dừng theo rules. Giữ dấu tiếng Việt. `q` rỗng, toàn khoảng trắng/dấu câu/từ dừng được coi là không lọc từ khóa. Không tìm gần đúng, từ đồng nghĩa hay semantic search.

`brand`/`material`: NFC, chữ thường, trim và gộp khoảng trắng; không loại từ dừng hoặc dấu câu. Chỉ so sánh dữ liệu có cấu trúc được Posts cho phép công khai, không trích xuất tự động từ description.

Nếu có cả hai cận thời gian thì sau chuyển UTC phải có `event_from < event_to`; không giới hạn khoảng thời gian tối đa trong v1. Không nhận date-only hoặc timestamp thiếu timezone. UI muốn lọc trọn ngày 10/11/2026 tại Việt Nam gửi `[2026-11-10T00:00:00+07:00, 2026-11-11T00:00:00+07:00)`.

Mã danh mục hoặc khu vực đúng cú pháp nhưng không tồn tại trả `422 UNKNOWN_FILTER_VALUE`. Bộ lọc hợp lệ và không có tin phù hợp trả `200` với `items: []`.

## 4. Schema query Matches

`GET /api/v1/matches`

| Query | Kiểu / ràng buộc | Bắt buộc | Mặc định | Ý nghĩa |
| --- | --- | --- | --- | --- |
| `post_id` | UUID | Có | — | Tin nguồn LOST hoặc FOUND |
| `min_score` | decimal hữu hạn, 50–100, tối đa 2 chữ số thập phân | Không | `50` | Giữ cặp có điểm tổng đã làm tròn `>= min_score` |
| `page` | integer 1–10000 | Không | `1` | Số trang |
| `page_size` | integer 1–100 | Không | `20` | Số phần tử mỗi trang |
| `sort` | enum chỉ có `score_desc` | Không | `score_desc` | Xếp hạng cố định theo mục 6 |

Không nhận lại `q`, `type`, `category_id` hoặc các bộ lọc Search trên endpoint này; truyền các key đó trả `422 UNKNOWN_QUERY_PARAMETER`. Matches phục vụ gợi ý của một tin cụ thể, không phải tìm kiếm toàn bộ các cặp. Không cho hạ min_score dưới ngưỡng lưu 50.

Tin nguồn không tồn tại, không công khai, ẩn hoặc xóa mềm đều trả cùng `404 POST_NOT_FOUND`. Tin nguồn công khai nhưng CLOSED, thiếu dữ liệu bắt buộc hoặc không đủ điều kiện matching trả `409 POST_NOT_MATCHABLE`; không trả chi tiết trường riêng tư. Tin nguồn FOUND trả ứng viên LOST và ngược lại, nhưng `lost_post_id`/`found_post_id` luôn giữ đúng nghĩa.

GET không tạo match hoặc kích hoạt tính lại. Baseline thiết kế yêu cầu đọc một thế hệ kết quả đã tính hoàn tất cho tin nguồn, cùng rule_version và phiên bản đầu vào hiện tại. Chưa tính, đang cần tính lại hoặc có kết quả cũ khác phiên bản thì trả `409 MATCHES_NOT_READY`, không trả điểm cũ như điểm hiện hành. Không có ứng viên sau một lần tính hoàn tất là `200 items: []`, khác với chưa tính.

Backend kiểm tra lại visibility và eligibility của cả hai tin. Tin đã ẩn biến mất khỏi items và total. Nếu đầu vào hợp lệ đã đổi hoặc có ứng viên mới, chủ tin hoặc admin cần tính lại qua `POST /api/v1/matches/recalculate`. Backend lưu phiên bản quy tắc và dấu vết đầu vào cho cả những lần tính có 0 kết quả.

## 5. Schema response

Tất cả field dưới đây bắt buộc trừ khi ghi khác. Object response dùng whitelist, không serialize trực tiếp ORM model; không thêm field ngoài schema khi chưa cập nhật contract.

### PublicPost

| Field | Kiểu | Quy tắc |
| --- | --- | --- |
| `id` | UUID string | ID tin |
| `type` | `LOST` hoặc `FOUND` | Loại tin |
| `title` | string | Tiêu đề đã được Posts xác nhận công khai |
| `description` | string | Mô tả công khai, không gồm nội dung xác minh |
| `category` | object `{id: UUID, name: string}` | Danh mục công khai |
| `location` | object `{code: string, name: string}` | Khu vực; không gồm tọa độ/địa chỉ riêng tư |
| `event_time` | UTC timestamp string | Thời điểm mất/nhặt |
| `status` | `OPEN` hoặc `CLOSED` | Enum công khai ở mục 3 |
| `color_code` | enum màu ở mục 3 hoặc null | null khi chưa có dữ liệu |
| `public_attributes` | object | Chỉ key `brand`, `material`; value string chuẩn hóa; bỏ key thiếu; có thể `{}` |
| `created_at` | UTC timestamp string | Thời điểm đăng, không dùng thay event_time để tính điểm |

Schema không trả ảnh trong phiên bản này. Có thể đi tới API chi tiết tin để xem ảnh đã được Posts cho phép công khai. PublicPost không chứa user/email/số điện thoại/đường dẫn file riêng tư hoặc model claim.

### Pagination

| Field | Kiểu | Giá trị |
| --- | --- | --- |
| `page`, `page_size` | integer | Giá trị query hiệu lực |
| `total` | integer >= 0 | Tổng số phần tử sau policy/bộ lọc/ngưỡng, trước phân trang |
| `total_pages` | integer >= 0 | `ceil(total/page_size)`; total=0 thì bằng 0 |
| `has_next` | boolean | `page < total_pages` |
| `has_previous` | boolean | `page > 1` và `total > 0` |

Trang vượt total_pages nhưng trong giới hạn query vẫn `200 items: []`, không phải lỗi. Offset=`(page-1)*page_size`. Total và items phải lấy từ cùng một snapshot đọc trong một request. Offset pagination không cố định snapshot qua nhiều request; thêm/sửa/ẩn tin hoặc tính lại có thể thay đổi các trang, client nên tải lại từ trang 1 khi làm mới.

### SearchResponse

`{items: PublicPost[], pagination: Pagination, sort: SearchSort}`. `SearchSort` là enum query Search. Không có `score` hoặc `explanation` trong SearchResponse.

### MatchesResponse

`{source_post_id: UUID, rule_version: string, calculated_at: timestamp, min_score: number, sort: "score_desc", items: MatchItem[], pagination: Pagination}`.

`calculated_at` là thời điểm hoàn tất thế hệ kết quả đang đọc; vẫn có giá trị khi items rỗng. `rule_version` hiện là `rules-v1-draft` trong ví dụ, không trộn nhiều phiên bản trong một response.

`MatchItem` gồm:

| Field | Kiểu | Quy tắc |
| --- | --- | --- |
| `id` | UUID string | Match ID, không dùng tie-break |
| `lost_post_id`, `found_post_id` | UUID string | Cặp tin đúng chiều LOST–FOUND |
| `candidate` | PublicPost | Tin đối ứng với source_post_id |
| `score` | JSON number 50–100 | Tổng điểm, tối đa 2 số thập phân; không phải xác suất |
| `level` | `HIGH` hoặc `POSSIBLE` | HIGH khi score >=75; POSSIBLE khi 50 <= score <75 |
| `score_details` | object | Sáu tiêu chí bắt buộc theo bảng dưới |
| `explanation` | string | Sinh từ template và dữ liệu công khai; luôn nêu đây là gợi ý cần xác minh |

Mỗi score_details có `points` (number >=0, không vượt max_points, hiển thị tối đa 2 số thập phân), `max_points` (integer cố định), `reason` và các field bổ sung đúng bảng. Không nhận key tiêu chí khác.

| Key | max_points | reason được phép | Field bổ sung bắt buộc |
| --- | ---: | --- | --- |
| `category` | 25 | `matched`, `different` | Không |
| `location` | 25 | `matched`, `different` | Không |
| `time` | 20 | `within_1_day`, `within_3_days`, `within_7_days`, `out_of_window` | `delta_seconds`: number có dấu, FOUND trừ LOST |
| `color` | 10 | `matched`, `different`, `missing` | Không |
| `keywords` | 10 | `matched`, `different`, `missing` | `intersection_count`, `union_count`: integer >=0 |
| `public_attributes` | 10 | `matched`, `different`, `missing` | `matched_count`, `compared_count`: integer, 0 <= matched_count <= compared_count <=2 |

Từ khóa/thuộc tính dùng `matched` khi có ít nhất một phần khớp, `different` khi có dữ liệu để so nhưng không khớp phần nào, `missing` khi không đủ dữ liệu so. Từ khóa missing nếu một hoặc cả hai tập rỗng; counts vẫn phản ánh giao/hợp thực tế. Thuộc tính missing thì cả hai count bằng 0. Không trả token, giá trị bí mật hay nội dung bằng chứng trong breakdown.

Tổng tính ở độ chính xác đầy đủ rồi làm tròn 2 chữ số bằng ROUND_HALF_UP; ngưỡng và thứ tự dựa trên tổng đã làm tròn. Điểm thành phần làm tròn để hiển thị có thể cộng lệch tổng 0,01. JSON number không bảo đảm giữ số 0 cuối: `100`, `100.0` và `100.00` có cùng nghĩa; UI định dạng 2 số thập phân nếu cần.

## 6. Thứ tự và đồng điểm

Search không chấm điểm relevance; `q` là bộ lọc. Áp dụng:

| sort | Thứ tự đầy đủ |
| --- | --- |
| `newest` (mặc định) | created_at DESC → id ASC |
| `oldest` | created_at ASC → id ASC |
| `event_desc` | event_time DESC → id ASC |
| `event_asc` | event_time ASC → id ASC |

Matches: **score DESC → abs(delta_seconds) ASC → candidate.id ASC**. So UUID theo thứ tự native PostgreSQL; so thời gian theo giá trị UTC chính xác, không dùng thời gian đã rút gọn để hiển thị. Luôn lọc/xếp toàn bộ kết quả trước phân trang.

Ví dụ 90 điểm/4 giờ đứng trước 90 điểm/6 giờ; cả hai đứng trước 80 điểm/1 giờ. Nếu 90 điểm và đều 4 giờ, candidate UUID nhỏ hơn đứng trước. Không dùng match ID hoặc calculated_at để phá đồng điểm. Khi dữ liệu và quy tắc không đổi, tính lại không làm đảo thứ tự.

## 7. Ví dụ request/response thành công

Các ID, nội dung và mã khu vực dưới đây là dữ liệu demo giả. Trong môi trường chạy, mã khu vực phải tồn tại trong catalog Posts.

### Search — HTTP 200

```http
GET /api/v1/search?q=v%C3%AD%20g%E1%BA%A5p&type=FOUND&location_code=AREA_A&event_from=2026-11-10T00:00:00%2B07:00&event_to=2026-11-11T00:00:00%2B07:00
```

```json
{
  "items": [
    {
      "id": "20000000-0000-4000-8000-000000000001",
      "type": "FOUND",
      "title": "ví gấp",
      "description": "ví gấp",
      "category": {"id": "30000000-0000-4000-8000-000000000001", "name": "Ví"},
      "location": {"code": "AREA_A", "name": "Khu A"},
      "event_time": "2026-11-10T05:00:00Z",
      "status": "OPEN",
      "color_code": "BLACK",
      "public_attributes": {"brand": "demo-a", "material": "da"},
      "created_at": "2026-11-10T06:00:00Z"
    }
  ],
  "pagination": {"page": 1, "page_size": 20, "total": 1, "total_pages": 1, "has_next": false, "has_previous": false},
  "sort": "newest"
}
```

Không có kết quả: `{"items":[],"pagination":{"page":1,"page_size":20,"total":0,"total_pages":0,"has_next":false,"has_previous":false},"sort":"newest"}`.

### Matches — HTTP 200

```http
GET /api/v1/matches?post_id=10000000-0000-4000-8000-000000000001&min_score=75&page=1&page_size=20
```

Tin LOST nguồn có cùng trường công khai như ứng viên, event_time là `2026-11-10T01:00:00Z`. Cặp cách nhau 4 giờ, mỗi tập từ là `{ví,gấp}`, khớp cả brand và material.

```json
{
  "source_post_id": "10000000-0000-4000-8000-000000000001",
  "rule_version": "rules-v1-draft",
  "calculated_at": "2026-11-10T06:05:00Z",
  "min_score": 75,
  "sort": "score_desc",
  "items": [
    {
      "id": "40000000-0000-4000-8000-000000000001",
      "lost_post_id": "10000000-0000-4000-8000-000000000001",
      "found_post_id": "20000000-0000-4000-8000-000000000001",
      "candidate": {
        "id": "20000000-0000-4000-8000-000000000001",
        "type": "FOUND",
        "title": "ví gấp",
        "description": "ví gấp",
        "category": {"id": "30000000-0000-4000-8000-000000000001", "name": "Ví"},
        "location": {"code": "AREA_A", "name": "Khu A"},
        "event_time": "2026-11-10T05:00:00Z",
        "status": "OPEN",
        "color_code": "BLACK",
        "public_attributes": {"brand": "demo-a", "material": "da"},
        "created_at": "2026-11-10T06:00:00Z"
      },
      "score": 100,
      "level": "HIGH",
      "score_details": {
        "category": {"points": 25, "max_points": 25, "reason": "matched"},
        "location": {"points": 25, "max_points": 25, "reason": "matched"},
        "time": {"points": 20, "max_points": 20, "reason": "within_1_day", "delta_seconds": 14400},
        "color": {"points": 10, "max_points": 10, "reason": "matched"},
        "keywords": {"points": 10, "max_points": 10, "reason": "matched", "intersection_count": 2, "union_count": 2},
        "public_attributes": {"points": 10, "max_points": 10, "reason": "matched", "matched_count": 2, "compared_count": 2}
      },
      "explanation": "Cùng danh mục (+25), cùng khu vực (+25), nhặt sau 4 giờ (+20), cùng màu (+10), từ khóa khớp (+10), hai thuộc tính công khai khớp (+10). Đây là gợi ý, cần xác minh qua claim."
    }
  ],
  "pagination": {"page": 1, "page_size": 20, "total": 1, "total_pages": 1, "has_next": false, "has_previous": false}
}
```

Sau khi đã tính hoàn tất nhưng không có gợi ý, vẫn trả đủ source_post_id, rule_version, calculated_at, min_score, sort với `items: []` và pagination total=total_pages=0.

## 8. Schema lỗi và các trường hợp lỗi

```text
ErrorResponse = {
  error: {
    code: string,
    message: string,
    request_id: string,
    details: Array<{field: string, issue: string}>
  }
}
```

`details` luôn có mặt, có thể rỗng. Field query dùng tên như `page_size`; lỗi không gắn một field dùng details rỗng. Không echo nguyên query value, nội dung bằng chứng, câu SQL hoặc stack trace. Lỗi HTTP validation cần được map về envelope này thay vì trả mặc định FastAPI khác schema.

| HTTP | error.code | Endpoint | Trường hợp |
| --- | --- | --- | --- |
| 422 | `VALIDATION_ERROR` | Cả hai | Thiếu post_id, UUID/enum/số sai, vượt giới hạn, min_score NaN/Infinity hoặc quá 2 chữ số lẻ, khoảng thời gian sai/thiếu timezone |
| 422 | `UNKNOWN_QUERY_PARAMETER` | Cả hai | Key ngoài whitelist, ví dụ evidence hoặc q trên matches |
| 422 | `DUPLICATE_QUERY_PARAMETER` | Cả hai | Lặp cùng tên query, kể cả cùng giá trị |
| 422 | `UNKNOWN_FILTER_VALUE` | Search | category_id/location_code đúng cú pháp nhưng không tồn tại |
| 404 | `POST_NOT_FOUND` | Matches | Không tồn tại hoặc không được hiển thị công khai; cùng message |
| 409 | `POST_NOT_MATCHABLE` | Matches | Tin nguồn công khai nhưng không đủ điều kiện matching |
| 409 | `MATCHES_NOT_READY` | Matches | Chưa có thế hệ kết quả hoàn tất và hiện hành |
| 500 | `INTERNAL_ERROR` | Cả hai | Lỗi ngoài dự kiến, message chung |

Backend kiểm tra tham số trước khi tra danh mục hoặc tin nguồn, rồi kiểm tra eligibility và tình trạng kết quả đã lưu.

### Search — khoảng thời gian không hợp lệ, HTTP 422

```http
GET /api/v1/search?event_from=2026-11-11T00:00:00Z&event_to=2026-11-10T00:00:00Z
```

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Query is invalid",
    "request_id": "d87d686c-4523-4fbb-aa1b-d1df87ba91aa",
    "details": [
      {"field": "query", "issue": "Value error, event_from must be earlier than event_to"}
    ]
  }
}
```

### Matches — thiếu tin nguồn, HTTP 422

```http
GET /api/v1/matches?page_size=20
```

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Query is invalid",
    "request_id": "d87d686c-4523-4fbb-aa1b-d1df87ba91aa",
    "details": [{"field": "post_id", "issue": "Field required"}]
  }
}
```

### Matches — tin nguồn bị ẩn hoặc không tồn tại, HTTP 404

```json
{
  "error": {
    "code": "POST_NOT_FOUND",
    "message": "Không tìm thấy tin công khai.",
    "request_id": "d87d686c-4523-4fbb-aa1b-d1df87ba91aa",
    "details": []
  }
}
```

### Matches — chưa tính hoặc kết quả cũ, HTTP 409

```json
{
  "error": {
    "code": "MATCHES_NOT_READY",
    "message": "Gợi ý chưa sẵn sàng. Vui lòng thử lại sau khi hệ thống tính lại.",
    "request_id": "d87d686c-4523-4fbb-aa1b-d1df87ba91aa",
    "details": []
  }
}
```

## 9. Ranh giới dữ liệu công khai

Posts cung cấp DTO được duyệt cho PublicPost; không mặc định title/description là an toàn chỉ vì tên trường. Nếu chưa tách được văn bản công khai với thông tin xác minh thì chưa đủ điều kiện đưa tin vào dữ liệu hai endpoint. Đặc điểm riêng tư được giữ ở nguồn riêng, không đưa vào DTO rồi chỉ loại khi serialize.

Search/matching không đọc claim_evidence, ảnh bằng chứng, nội dung claim, số định danh đầy đủ, serial dùng xác minh, dấu hiệu bí mật, thông tin liên hệ riêng tư hoặc token. Không dùng các nguồn này để tính điểm tổng, tạo explanation, suy luận hoặc ghi log. Explanation sinh từ tiêu chí/count công khai và template cố định; không nối nội dung bằng chứng hoặc toàn bộ object vào chuỗi.

Các tổng số và metadata chỉ phản ánh tập được phép hiển thị. Không trả số tin ẩn, lý do kiểm duyệt, internal eligibility details, đường dẫn lưu file hoặc dữ liệu riêng tư qua lỗi. Hai endpoint không xác nhận chủ sở hữu, duyệt claim, tạo return hoặc đổi trạng thái tin.

## 10. Đối chiếu nghiệm thu và bàn giao

| Tiêu chí task | Vị trí đặc tả |
| --- | --- |
| Có từ khóa, bộ lọc, phân trang, mặc định | Mục 2–4 |
| Hai endpoint có schema query/response và ví dụ | Mục 3–5, 7 |
| Có trường hợp lỗi và ví dụ lỗi | Mục 8 |
| Có thứ tự và cách phá đồng điểm | Mục 6 |
| Không có bằng chứng riêng tư trong kết quả/giải thích | Whitelist mục 5 và policy mục 9 |

Kiểm thử HTTP liên module nằm tại `backend/tests/api/test_system.py`.
