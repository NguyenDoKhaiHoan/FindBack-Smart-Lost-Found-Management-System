# KAN-23 — Phân tích tiêu chí tìm kiếm và quy tắc đánh giá trùng khớp

## 1. Mục tiêu và trạng thái

Cập nhật triển khai: đã có thuật toán và GET matches dùng các quy tắc dưới đây, được kiểm thử với adapter bộ nhớ. Xem [bàn giao triển khai](matching-implementation.md). Bản phân tích KAN-23 vẫn giữ trạng thái draft; việc triển khai không thay thế review nhóm hoặc tích hợp Posts/DB.

Đề xuất bộ quy tắc `rules-v1-draft` để tìm kiếm tin và xếp hạng cặp LOST–FOUND bằng dữ liệu công khai, không dùng AI/ML. Điểm biểu thị mức tương đồng theo quy tắc, không phải xác suất đúng chủ sở hữu.

Đây là đầu ra phân tích để review với Posts và Claims, không phải chức năng đã triển khai hoặc quy tắc đã được nhóm phê duyệt. Trọng số, ngưỡng và các trường đề xuất dưới đây cần được thống nhất trước KAN-26.

Phạm vi: tiêu chí tìm kiếm, chuẩn hóa đầu vào, điều kiện ghép cặp, công thức điểm, dữ liệu thiếu, xếp hạng, giải thích và ví dụ tính tay. Không triển khai endpoint, model, migration hoặc thuật toán trong task này. Ước lượng: 5 giờ; task DB được theo dõi riêng.

Nguồn đối chiếu: [README](../README.md), [yêu cầu](requirements.md), [API sơ bộ](api/endpoints.md), [schema DB đề xuất](database/matching-schema.sql).

## 2. Đầu vào và phối hợp Posts/Claims

| Tiêu chí | Trường trong schema Posts sơ bộ | Đầu vào so sánh đề xuất | Điều cần thống nhất |
|---|---|---|---|
| Từ khóa | title, description | Tập từ công khai đã chuẩn hóa | Posts chỉ cung cấp nội dung được phép công khai |
| Loại đồ vật | category_id | ID danh mục | Dùng chung categories; không so sánh bằng tên tự nhập |
| Địa điểm | location | Mã khu vực chuẩn hóa | location hiện chưa chốt kiểu; đề xuất trường location_code hoặc ánh xạ trong contract |
| Thời gian | event_time | Timestamp có múi giờ | Thời điểm mất/nhặt, không dùng thời gian đăng; độ chính xác cần được xác nhận |
| Màu | Chưa có trường riêng | color_code, một màu chính | Đề xuất bổ sung trường; không tự trích xuất màu từ văn bản |
| Đặc điểm công khai | Chưa có trường riêng | public_attributes với whitelist brand, material | Đề xuất bổ sung dữ liệu có cấu trúc; chưa coi là trường đang có |
| Loại tin | type | LOST hoặc FOUND | Thống nhất enum với Posts |
| Trạng thái/hiển thị | status; cơ chế xóa mềm chưa chốt | Khả năng hiển thị và tham gia matching | Posts cung cấp policy; không tự đặt tên trạng thái |
| ID | id | ID tin ổn định | DB dự thảo giả định UUID, cần xác nhận với Posts |

Claims xác nhận danh sách dữ liệu riêng tư: nội dung bằng chứng, ảnh bằng chứng, số định danh đầy đủ, số serial dùng xác minh, dấu hiệu bí mật và thông tin liên hệ riêng tư. Không truy vấn claim_evidence hoặc đưa các dữ liệu này vào bất kỳ đầu vào, log, điểm hay giải thích nào.

Matching chỉ đọc DTO chứa trường công khai đã được Posts cho phép. Nội dung văn bản cần qua chính sách công khai của Posts; không thể mặc định an toàn chỉ vì có tên description. Nếu chưa phân biệt được dữ liệu công khai/riêng tư, chưa sử dụng nguồn đó để tính điểm.

## 3. Tiêu chí tìm kiếm

Tìm kiếm trả tin thỏa bộ lọc người dùng; khác với matching là đánh giá một cặp tin. Các tên đầu vào ở đây là tên logic đề xuất, chưa phải API contract.

| Tiêu chí | Quy tắc đề xuất | Khi không cung cấp |
|---|---|---|
| Từ khóa q | Chuẩn hóa thành tập từ; mọi từ của q phải có trong tập từ title + description công khai | Không lọc từ khóa |
| Loại tin | So khớp LOST/FOUND | Không lọc loại |
| Danh mục | So khớp category_id | Không lọc danh mục |
| Khu vực | So khớp mã khu vực chính xác | Không lọc khu vực |
| Khoảng thời gian | event_time thuộc [from, to), dùng mốc bắt đầu bao gồm, mốc kết thúc không bao gồm | Bỏ điều kiện ở đầu khoảng không được cung cấp |
| Trạng thái | Chỉ trong tập trạng thái mà người gọi được phép xem | Áp dụng policy hiển thị mặc định của Posts |
| Màu | So khớp color_code nếu Posts đã hỗ trợ | Không lọc màu |
| Đặc điểm công khai | So khớp chính xác từng key/value được hỗ trợ; kết hợp AND | Không lọc đặc điểm |

Các bộ lọc khác nhau kết hợp AND. Trường dữ liệu của tin bị thiếu không thỏa bộ lọc tương ứng khi người dùng đã chọn lọc. Truy vấn chỉ gồm từ dừng được coi như không có q. Không tìm từ đồng nghĩa, gần đúng, ảnh hoặc suy luận ngữ nghĩa trong v1.

Khoảng from >= to, mã không hợp lệ hoặc timestamp không có múi giờ phải được validation theo API contract, không âm thầm bỏ qua điều kiện. Đầu vào ngày lịch được chuyển thành đầu ngày tại múi giờ giao diện; ngày kết thúc bao gồm được chuyển thành đầu ngày kế tiếp trước khi áp dụng [from, to).

Phân trang, giới hạn kích thước trang, schema lỗi và thứ tự mặc định của tìm kiếm được đặc tả trong [contract KAN-24](api/search-matching-contract.md) cho `GET /api/v1/search` và `GET /api/v1/matches`; không dùng ngưỡng matching để loại kết quả tìm kiếm thông thường. Contract cụ thể hóa enum/bộ lọc và chính sách đọc, vẫn cần review với Posts/Claims trước triển khai.

## 4. Chuẩn hóa dữ liệu

- Văn bản: Unicode NFC, chữ thường, dấu câu thành khoảng trắng, gộp khoảng trắng, tách theo khoảng trắng và loại từ trùng. Giữ dấu tiếng Việt; không stemming hoặc dùng mô hình.
- Từ dừng cố định của bản dự thảo: {tôi, mình, bị, mất, nhặt, được, tìm, thấy, ở, tại, và, là, của, một, cái, chiếc}. Khi sửa danh sách phải đổi rule_version.
- Tập từ matching lấy title + description công khai; v1 chưa tự loại từ màu/địa điểm/thuộc tính trong văn bản vì chưa có bộ từ điển đáng tin cậy. Chấp nhận một phần tín hiệu lặp; từ khóa chỉ có trọng số 10. Không triển khai quy tắc loại từ không được đặc tả.
- Danh mục và khu vực: so sánh mã chuẩn, không so sánh chuỗi tên hoặc suy luận khoảng cách.
- Màu: dùng mã từ tập đóng do Posts thống nhất, ví dụ BLACK, WHITE, BLUE. Dữ liệu không ánh xạ được được ghi là thiếu; v1 chưa so sánh nhiều màu.
- Đặc điểm: chỉ brand và material. Giá trị được chuẩn hóa NFC, chữ thường và khoảng trắng; không suy ra từ title/description. Chuỗi rỗng/null không được xem là giá trị.
- Thời gian: quy đổi timestamp có múi giờ thành UTC để so sánh. Ví dụ trong tài liệu hiển thị UTC+07:00. V1 giả định thời điểm cụ thể; dữ liệu chỉ có ngày hoặc khoảng ước lượng cần contract bổ sung, không tự gán giờ rồi coi là chính xác.

## 5. Điều kiện ghép cặp trước khi chấm điểm

1. Hai tin tồn tại, khác ID và gồm đúng một LOST với một FOUND. Khi khởi phát từ FOUND vẫn chuẩn hóa thứ tự lost_post_id/found_post_id như nhau.
2. Cả hai tin được phép hiển thị và đang đủ điều kiện matching theo policy của Posts. Tin ẩn, xóa mềm hoặc không còn nhận gợi ý phải bị loại.
3. Hai tin có category_id hợp lệ, mã khu vực hợp lệ và event_time có múi giờ/độ chính xác phù hợp. Thiếu các đầu vào bắt buộc này: không chấm điểm, báo lý do dữ liệu thiếu trong nội bộ; không lưu cặp điểm 0 giả.
4. Có mô tả công khai hợp lệ theo Posts. Việc tập từ trở thành rỗng sau chuẩn hóa vẫn được xử lý ở tiêu chí từ khóa.
5. Danh mục khác nhau không bị loại cứng trong bản v1: nhận 0 ở tiêu chí danh mục. Với trọng số hiện tại, cặp khác danh mục vẫn có thể đạt tối đa 75; đây là lựa chọn cần nhóm review, không phải cam kết hai tin cùng loại đồ.
6. FOUND trước LOST không bị loại cứng, nhưng tiêu chí thời gian nhận 0. Quy tắc này hỗ trợ dữ liệu thời gian khai báo có thể sai; không suy ra quyền sở hữu từ điểm.

Cùng người đăng không phải điều kiện loại matching trong bản dự thảo. Claims vẫn phải chặn tự claim độc lập. Không suy rộng quy tắc của Claims thành quy tắc matching khi chưa thống nhất.

## 6. Bảng trọng số và công thức

Ký hiệu Δ = found.event_time - lost.event_time, tính bằng số giây thực tế; 1 ngày = 86.400 giây.

| Tiêu chí | Tối đa | Quy tắc điểm | Thiếu dữ liệu |
|---|---:|---|---|
| Danh mục | 25 | Cùng category_id: 25; khác: 0 | Thiếu/không hợp lệ: loại ở bước điều kiện |
| Khu vực | 25 | Cùng mã: 25; khác: 0 | Thiếu/không hợp lệ: loại ở bước điều kiện |
| Thời gian | 20 | 0 ≤ Δ ≤ 1 ngày: 20; 1 < Δ ≤ 3 ngày: 15; 3 < Δ ≤ 7 ngày: 5; Δ < 0 hoặc Δ > 7 ngày: 0 | Thiếu/không rõ độ chính xác: loại ở bước điều kiện |
| Màu | 10 | Cùng mã màu: 10; khác: 0 | Một hoặc cả hai thiếu: 0, reason=missing |
| Từ khóa | 10 | 10 × Jaccard(A,B), A/B là tập từ công khai sau chuẩn hóa | Một hoặc cả hai tập rỗng: 0, reason=missing |
| Đặc điểm công khai | 10 | 10 × m/n; n là số key trong {brand, material} có giá trị ở cả hai tin; m là số key trong n có giá trị giống nhau | n=0: 0, reason=missing; key chỉ có ở một tin bị bỏ khỏi mẫu số |
| Tổng | 100 | Tổng sáu điểm thành phần | Không phân bổ lại trọng số |

Jaccard(A,B) = |A ∩ B| / |A ∪ B|. Hai tập rỗng không được coi là giống hoàn toàn. Các tiêu chí số học được tính ở độ chính xác đầy đủ; chỉ làm tròn tổng cuối cùng 2 chữ số theo ROUND_HALF_UP. Điểm tổng đã làm tròn là giá trị lưu, xét ngưỡng và xếp hạng; điểm chi tiết hiển thị làm tròn có thể cộng lệch 0,01.

Chỉ một thuộc tính công khai so sánh được và giống nhau thì tiêu chí vẫn đạt 10/10; phải ghi n=1 để giải thích giới hạn dữ liệu. Không coi key chưa có dữ liệu là khớp. Đây là quyết định v1 cần review khi có bộ dữ liệu demo lớn hơn.

## 7. Ngưỡng và thứ tự xếp hạng

| Điểm tổng đã làm tròn | Kết quả |
|---|---|
| 75–100 | Đề xuất gợi ý, nhãn mức tương đồng cao |
| 50–dưới 75 | Đề xuất gợi ý, nhãn có thể liên quan |
| Dưới 50 | Không đưa vào danh sách gợi ý |

Thứ tự: score giảm dần → abs(Δ) tăng dần → ID tin đối ứng tăng dần (UUID theo thứ tự native PostgreSQL nếu dùng UUID). Dùng ID tin đối ứng, không dùng ID match được sinh mới, để tính lại không làm đảo thứ tự khi điểm và thời gian bằng nhau. Xếp hạng toàn bộ tập đủ điều kiện trước khi phân trang.

Không gắn nhãn đã xác minh cho bất kỳ mức điểm nào. Các ngưỡng chỉ là đề xuất, phải đánh giá trên dữ liệu demo. V1 không loại cứng cặp khác khu vực, khác danh mục hoặc cách nhau hơn 7 ngày; các tiêu chí còn lại vẫn có thể đưa tổng vượt ngưỡng. Nếu nhóm muốn loại cứng, cần sửa điều kiện và đổi phiên bản quy tắc.

## 8. Giải thích và dữ liệu lưu trong matches

Mỗi kết quả có điểm từng tiêu chí và lý do: matched, different, missing hoặc out_of_window; điểm thời gian có thể dùng within_1_day, within_3_days, within_7_days. Chỉ phản ánh trường được phép công khai.

Ví dụ explanation: "Cùng danh mục (+25), cùng khu vực (+25), nhặt sau thời điểm mất 4 giờ (+20); chưa có màu để so sánh (+0). Đây là gợi ý, cần xác minh qua claim."

Ví dụ cấu trúc score_details đề xuất cho cặp đủ 100 điểm:

```json
{
  "category": {"points": 25, "max_points": 25, "reason": "matched"},
  "location": {"points": 25, "max_points": 25, "reason": "matched"},
  "time": {"points": 20, "max_points": 20, "reason": "within_1_day", "delta_seconds": 14400},
  "color": {"points": 10, "max_points": 10, "reason": "matched"},
  "keywords": {"points": 10, "max_points": 10, "reason": "matched", "intersection_count": 2, "union_count": 2},
  "public_attributes": {"points": 10, "max_points": 10, "reason": "matched", "matched_count": 2, "compared_count": 2}
}
```

Dùng các cột trong DB dự thảo: lost_post_id, found_post_id, score, score_details, explanation, rule_version, calculated_at. Không thêm trạng thái duyệt claim vào matches. Bản này dùng rule_version=rules-v1-draft; phiên bản chính thức được đặt khi nhóm duyệt.

Chỉ lưu các cặp đạt ngưỡng 50 theo v1. Tính lại phải upsert theo cặp, đồng thời xóa/vô hiệu hóa kết quả cũ không còn đủ điều kiện hoặc dưới ngưỡng trong cùng phạm vi tính lại. Không trộn các phiên bản quy tắc trong cùng danh sách sau một đợt tính lại toàn phần. Khi đọc, luôn kiểm tra lại visibility/eligibility của Posts; kết quả lưu không bảo đảm tin vẫn công khai. Quyền gọi tính lại và phạm vi xử lý thuộc API contract.

## 9. Bộ ví dụ tính tay

Tất cả tên, mã và dữ liệu dưới đây là dữ liệu demo giả. Các tin đều công khai, đúng loại và đủ điều kiện trừ khi ghi khác. Bộ ví dụ dùng title công khai "ví gấp", description công khai "ví gấp", nên tập từ thực tế sau chuẩn hóa là {ví, gấp}; màu và thuộc tính lưu riêng. Các ID như L1/F1 là nhãn minh họa, không phải UUID dùng insert DB.

### A. Cặp khớp — 100 điểm

| Trường | LOST L1 | FOUND F1 |
|---|---|---|
| category_id | WALLET | WALLET |
| location_code | AREA_A | AREA_A |
| event_time | 2026-11-10T08:00:00+07:00 | 2026-11-10T12:00:00+07:00 |
| color_code | BLACK | BLACK |
| Tập từ | {ví, gấp} | {ví, gấp} |
| public_attributes | brand=demo-a, material=da | brand=demo-a, material=da |

Δ=4 giờ. Điểm = 25 + 25 + 20 + 10 + 10×(2/2) + 10×(2/2) = **100,00**. Được gợi ý, mức tương đồng cao. Không đồng nghĩa xác nhận chủ sở hữu.

### B. Cặp không phù hợp — 0 điểm

Giữ LOST L1; FOUND F2 có category_id=HEADPHONES, location_code=AREA_B, event_time=2026-11-20T08:00:00+07:00, color_code=WHITE, title/description="tai nghe", public_attributes={brand: demo-b, material: nhựa}.

- Danh mục khác: 0; khu vực khác: 0.
- Δ=10 ngày: 0; màu khác: 0.
- A={ví,gấp}, B={tai,nghe}; giao=0, hợp=4: 10×0/4=0.
- Hai thuộc tính so sánh được, không thuộc tính nào giống: 10×0/2=0.
- Tổng = **0,00**; không lưu/không gợi ý. Đây là cặp được chấm điểm rồi dưới ngưỡng, khác với trường hợp bị loại do đầu vào không hợp lệ.

### C. Thiếu màu — 90 điểm

Giữ cặp L1–F1 nhưng F1 không có color_code. Điểm màu=0, reason=missing; các tiêu chí còn lại giữ nguyên. Tổng = 25+25+20+0+10+10 = **90,00**. Không tăng trọng số tiêu chí khác để bù màu thiếu.

### D. Khớp một phần — 61,67 điểm

Giữ LOST L1. FOUND F3: cùng danh mục; AREA_B; nhặt 2026-11-12T08:00:00+07:00; màu BLACK; title/description="ví gấp khóa"; brand=demo-a, material=vải.

- Danh mục 25; khu vực 0; Δ=2 ngày nên thời gian 15; màu 10.
- Từ khóa: giao={ví,gấp} có 2; hợp={ví,gấp,khóa} có 3 → 20/3 điểm.
- Thuộc tính: brand giống, material khác → 10×1/2=5.
- Tổng chính xác = 25+0+15+10+20/3+5 = 61,666… → **61,67**. Được gợi ý ở mức có thể liên quan.


### E. Biên thời gian và dữ liệu không hợp lệ

| Tình huống | Kết quả mong đợi |
|---|---|
| Δ=0 hoặc đúng 24 giờ | 20 điểm thời gian |
| Δ=24 giờ + 1 giây | 15 điểm thời gian |
| Δ=đúng 72 giờ | 15 điểm thời gian |
| Δ=72 giờ + 1 giây | 5 điểm thời gian |
| Δ=đúng 168 giờ | 5 điểm thời gian |
| Δ=168 giờ + 1 giây hoặc -1 giây | 0 điểm thời gian |
| Thiếu event_time hoặc khu vực bắt buộc | Không chấm, không tạo match |
| Hai tin đều FOUND hoặc cùng ID | Loại trước chấm điểm |
| Một tin bị ẩn/xóa mềm | Loại dù điểm cũ đạt 100 |
| Hai tập từ đều rỗng | Từ khóa 0 điểm, reason=missing |
| Không có key thuộc tính chung | Thuộc tính 0 điểm, reason=missing |

### F. Kiểm tra xếp hạng và tìm kiếm

- Hai ứng viên cùng điểm: ứng viên có abs(Δ)=4 giờ xếp trước ứng viên có abs(Δ)=6 giờ. Nếu thời gian cũng bằng nhau, ID tin đối ứng nhỏ hơn xếp trước. Tính lại không đổi thứ tự này.
- Điểm đúng 50 được gợi ý; 49,99 không được gợi ý; đúng 75 mang nhãn tương đồng cao. Tổng thô 49,995 làm tròn thành 50,00 và được xét theo điểm đã làm tròn.
- Lọc category=WALLET và location=AREA_A và khoảng [2026-11-10T00:00:00+07:00, 2026-11-11T00:00:00+07:00): F1 thỏa; F2 và F3 không thỏa.
- q="TÌM ví gấp!" chuẩn hóa thành {ví,gấp}; F1 và F3 thỏa từ khóa, F2 không thỏa. Nếu thêm khu vực AREA_A thì chỉ F1 thỏa.

## 10. Bảo vệ dữ liệu và giới hạn nghiệp vụ

- Không dùng nội dung claim, đặc điểm bí mật, ảnh bằng chứng, số định danh riêng tư hoặc dữ liệu xác minh do Claims quản lý. Không tạo suy luận từ các trường đó dù chỉ trả điểm tổng.
- Không đọc ảnh, tạo embedding, OCR, dùng LLM hoặc huấn luyện mô hình.
- Không tự duyệt claim, xác nhận chủ sở hữu, tạo return hoặc đóng tin. Claims vẫn kiểm tra bằng chứng và quyền riêng.
- Điểm thấp có thể do thiếu dữ liệu; v1 ưu tiên dễ giải thích hơn việc bù thiếu bằng suy đoán. Điểm cao có thể là đồ cùng loại phổ biến. Tất cả kết quả vẫn cần xác minh.

## 11. Checklist bàn giao và các quyết định cần review

- [x] Có bảng tiêu chí, tổng trọng số 100 và quy tắc dữ liệu thiếu.
- [x] Có ví dụ khớp, không khớp, khớp một phần và thiếu dữ liệu tính bằng tay.
- [x] Phân biệt bộ lọc, điều kiện loại cặp, điểm và ngưỡng.
- [x] Đối chiếu trường Posts sơ bộ và chỉ rõ trường đề xuất chưa tồn tại.
- [x] Nêu rõ không sử dụng dữ liệu bí mật, matching chỉ là gợi ý.
- [ ] Posts xác nhận ID, mã khu vực, độ chính xác thời gian, màu và public_attributes.
- [ ] Posts xác nhận policy hiển thị/đủ điều kiện và nguồn văn bản công khai.
- [ ] Claims xác nhận whitelist công khai và ranh giới dữ liệu riêng tư.
- [ ] Nhóm duyệt trọng số, ngưỡng, từ dừng, chính sách khác danh mục/thời gian âm và thuộc tính thiếu.
- [ ] Chuyển các quy tắc đã duyệt thành contract KAN-24, code KAN-26 và test KAN-27.

Các mục hoàn thành chỉ xác nhận nội dung tài liệu đã có, không thay thế review nhóm hoặc kết quả kiểm thử phần mềm.

