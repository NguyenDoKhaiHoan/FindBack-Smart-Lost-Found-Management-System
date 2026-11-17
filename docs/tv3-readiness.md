# TV3 — Rà soát phạm vi Search & Matching

## 1. Cơ sở và trạng thái

Đối chiếu tài liệu tổng quát FINDBACK được cung cấp với [README](../README.md), [yêu cầu nghiệp vụ](requirements.md), [API sơ bộ](api/endpoints.md), [quy tắc matching](matching-rules.md), [DDL đề xuất](database/matching-schema.sql) và [ghi chú DB](database/matching-db-jira.md).

Đây là checklist được cập nhật theo yêu cầu mới. Các lựa chọn trong bản `rules-v1-draft` chưa được coi là quyết định đã duyệt. Backend đã có thuật toán, API matches, dependency và test unit/API chạy với adapter bộ nhớ; frontend còn bộ khung. Chưa có adapter Posts/DB thật hoặc migration tích hợp. File SQL đề xuất không đồng nghĩa database đã được tạo. Xem [bàn giao matching](matching-implementation.md).

## 2. “Lọc, xếp hạng theo quy tắc” là gì?

**Search:** người dùng nhập điều kiện để lấy các tin thỏa điều kiện. Ví dụ chọn FOUND, danh mục ví, khu vực A và khoảng thời gian thì chỉ trả tin đáp ứng đồng thời các bộ lọc đó. Search không cần một tin nguồn và không dùng ngưỡng matching để loại kết quả.

**Matching:** từ một tin LOST hoặc FOUND, lấy các tin đối ứng đủ điều kiện, tính điểm tương đồng rồi sắp xếp. Theo bản dự thảo: danh mục 25, khu vực 25, thời gian 20, màu 10, từ khóa 10, thuộc tính công khai 10; tổng tối đa 100. Điểm từ 50 được gợi ý, từ 75 có nhãn tương đồng cao. Thứ tự: điểm giảm dần → chênh lệch thời gian tuyệt đối tăng dần → ID tin đối ứng tăng dần.

Ví dụ hai tin cùng danh mục, khu vực, cách nhau 4 giờ, cùng từ khóa nhưng thiếu màu và thuộc tính: 25 + 25 + 20 + 0 + 10 + 0 = 80 điểm. Đây chỉ là gợi ý; người dùng vẫn phải đi qua claim và xác minh.

Trong dự thảo, khác danh mục hoặc FOUND sớm hơn LOST chỉ làm tiêu chí tương ứng nhận 0, chưa loại cả cặp. Cần review rõ lựa chọn này trước khi triển khai. Công thức, chuẩn hóa và các biên thời gian chi tiết nằm trong [matching-rules.md](matching-rules.md).

## 3. Phạm vi 5 API và phần còn thiếu

| API TV3 | Đã có trong tài liệu | Còn cần để xây dựng |
| --- | --- | --- |
| `GET /categories` | Danh sách endpoint, DDL categories | Contract response, quyền đọc, xử lý danh mục inactive, thứ tự, seed danh mục, model/repository/router và test |
| `GET /api/v1/search` | [Contract query/response và bộ lọc](api/search-matching-contract.md), chuẩn hóa dự thảo | Review adapter/policy Posts, truy vấn DB, router và test |
| `GET /api/v1/matches` | Contract, thuật toán, readiness bộ nhớ, hai chiều LOST/FOUND, router và test | Review liên module, adapter Posts/PostgreSQL và metadata lưu bền vững |
| `POST /matches/recalculate` | Upsert và loại kết quả mất hiệu lực | Ai được gọi, phạm vi một tin/toàn bộ, body/response, chạy đồng bộ hay nền, transaction, xử lý gọi đồng thời/thất bại, giới hạn tải và test |
| `GET /matches/{id}` | Dữ liệu matches dự kiến | Response chi tiết và breakdown điểm, kiểm tra quyền/visibility cả hai tin, xử lý cặp mất hiệu lực/không tồn tại và test |

GET matches đã triển khai độc lập; bốn API còn lại chưa triển khai. Không thêm endpoint quản trị danh mục hoặc AI matching vào MVP TV3 khi chưa có yêu cầu bổ sung.

## 4. Các điểm cần chốt khi phối hợp

| Ưu tiên | Nội dung | Phối hợp | Đầu ra cần có |
| --- | --- | --- | --- |
| Trước contract | Kiểu ID, enum loại/trạng thái tin, xóa mềm, tin nào được search/matching | TV2 | DTO công khai và policy hiển thị/eligibility dùng chung |
| Trước thuật toán | Khu vực là mã hay văn bản; event_time là thời điểm, ngày hay khoảng ước lượng | TV2 | Quy tắc dữ liệu, timezone, validation và ví dụ |
| Trước thuật toán | Có hỗ trợ color_code, brand, material không; nguồn title/description nào được công khai | TV2, TV4 | Whitelist đầu vào; cách xử lý trường chưa hỗ trợ |
| Trước contract | Search có cho khách dùng; ai xem matches; ai được tính lại và tính lại phạm vi nào | TV1, TV2 | Ma trận quyền và dependency xác thực |
| Trước code | Duyệt trọng số, ngưỡng, từ dừng, khác danh mục, thời gian âm, cùng người đăng | Nhóm, TV3 chủ trì | Phiên bản quy tắc được thống nhất và bộ ví dụ chuẩn |
| Trước tích hợp | Phân định `GET /posts` của TV2 và `/api/v1/search` của TV3 | TV2 | Dùng chung policy/DTO và logic lọc phù hợp; dùng đường dẫn mới theo contract |
| Trước migration | Ai tạo categories, thứ tự migration categories → posts → matches | TV2, người phụ trách DB | Chuỗi Alembic, FK, index và seed thống nhất |
| Trước tích hợp | Khi tạo/sửa/ẩn/xóa/đóng tin, gợi ý được cập nhật vào lúc nào | TV2, TV4, TV5 khi kiểm duyệt | Cơ chế tính lại/vô hiệu hóa và kiểm tra visibility lúc đọc |

Không sử dụng claim_evidence, đặc điểm bí mật, ảnh bằng chứng hoặc dữ liệu xác minh để tìm kiếm, tính điểm, giải thích hay ghi log.

## 5. Điểm cần lưu ý trong thiết kế hiện có

1. **Index chưa bao phủ thứ tự xếp hạng:** SQL dùng `(post_id, score DESC, id)` với `id` là match ID; quy tắc yêu cầu thêm `abs(Δ)` rồi ID tin đối ứng. Index này vẫn có thể hỗ trợ truy vấn theo tin/điểm nhưng không thay thế `ORDER BY` đúng quy tắc. Khi triển khai, chọn join dữ liệu Posts để tính Δ hoặc thiết kế dữ liệu phụ trợ; kiểm tra truy vấn thực tế trước khi tối ưu index.
2. **SQL chưa thể tích hợp độc lập:** script nguyên khối yêu cầu bảng posts tồn tại, trong khi Posts cần categories trước. Cần tách đúng thứ tự migration; không chạy nguyên script làm bước khởi tạo toàn hệ thống.
3. **Thiếu các trường đầu vào đề xuất:** schema Posts sơ bộ chưa có màu/thuộc tính công khai/mã khu vực chuẩn. Nếu chưa hỗ trợ màu và thuộc tính thì tối đa chỉ đạt 80 theo trọng số dự thảo; cần đánh giá lại trên seed demo, không tự phân bổ lại trọng số.
4. **Điểm lưu có thể cũ:** kiểm tra visibility lúc đọc ngăn lộ tin bị ẩn nhưng chưa bảo đảm điểm phản ánh nội dung vừa sửa. Cần chốt chính sách tính lại sau thay đổi, quản lý rule_version và việc trả gợi ý trong lúc tính lại.
5. **Recalculate cần tính nhất quán:** upsert cặp hiện có chưa đủ; phải xóa/vô hiệu hóa cặp dưới ngưỡng hoặc mất điều kiện trong cùng phạm vi. Cần tránh hai lần tính đồng thời ghi đè kết quả mới hoặc xóa nhầm phạm vi của nhau.
6. **Nền tảng chạy mới có một phần:** đã có entrypoint FastAPI, dependency và fixture/test matching. Còn cấu hình/session DB, Alembic và tích hợp Posts. Đây là dependency chung của nhóm, không mặc định toàn bộ thuộc TV3.

## 6. Backlog triển khai đề xuất

Mã KAN dưới đây được tham chiếu từ tài liệu hiện có; không xác nhận trạng thái trên Jira.

| Thứ tự | Công việc | Đầu ra / điều kiện hoàn thành |
| --- | --- | --- |
| 1 | Review KAN-23 và giao diện dữ liệu liên module | Chốt các quyết định ở mục 4; cập nhật rules và ví dụ chuẩn |
| 2 | KAN-24: contract Search/Matches | Đã có bản thiết kế cho hai GET theo yêu cầu bổ sung; cần review. Ba API TV3 còn lại có contract riêng chưa hoàn tất |
| 3 | Tích hợp DB | SQLAlchemy categories/matches, Alembic theo dependency, seed giả, constraints và index theo truy vấn |
| 4 | Triển khai search | Repository lọc AND, chuẩn hóa từ khóa, thời gian `[from,to)`, visibility, sort/phân trang ổn định |
| 5 | KAN-26: thuật toán matching | Hàm chuẩn hóa/chấm điểm thuần, breakdown/explanation công khai, ngưỡng/làm tròn/xếp hạng đúng rules |
| 6 | Lưu và phục vụ gợi ý | Recalculate có transaction/upsert/dọn cặp cũ, đọc theo hai chiều, kiểm tra visibility hiện tại và quyền |
| 7 | KAN-27: kiểm thử và demo | Unit + API + PostgreSQL integration phù hợp; ghi lệnh/kết quả chạy thực tế |
| 8 | Bàn giao frontend/tài liệu | Mẫu response, tích hợp lọc/danh sách/giải thích, hướng dẫn seed và demo; phân công UI với nhóm |

## 7. Checklist nghiệm thu TV3

Checklist dưới đây dành cho tích hợp toàn module. Matching độc lập đã có 44 test unit/API đạt với adapter bộ nhớ; các mục phụ thuộc Posts/PostgreSQL chưa được coi là hoàn tất.

- [ ] Đủ 5 API theo contract và được mount trong ứng dụng chung.
- [ ] Search phối hợp nhiều bộ lọc đúng AND, chuẩn hóa từ khóa đúng; khoảng thời gian và đầu vào sai được kiểm tra.
- [ ] Quyền xem và dữ liệu trả về tuân thủ policy Posts; không lộ tin ẩn/xóa mềm hoặc bằng chứng riêng tư.
- [ ] Matching chỉ nhận đúng cặp LOST–FOUND đủ điều kiện; hoạt động từ cả hai chiều.
- [ ] Bộ ví dụ tính tay trong rules cho kết quả đúng; kiểm thử biên 1/3/7 ngày, điểm 50/75, thiếu dữ liệu, làm tròn và tie-break.
- [ ] Xếp hạng toàn bộ ứng viên trước phân trang; tính lại không làm đảo tie-break chỉ vì sinh match ID mới.
- [ ] Recalculate không tạo cặp trùng, dọn kết quả không hợp lệ, xử lý thất bại/gọi đồng thời theo contract.
- [ ] FK/unique/check và migration upgrade/downgrade được kiểm chứng trên PostgreSQL phát triển.
- [ ] Danh mục có seed demo và chính sách inactive thống nhất với Posts.
- [ ] Gợi ý có giải thích, rule_version và thời điểm tính; không tự duyệt claim, tạo return hoặc đóng tin.
- [x] Có hướng dẫn chạy và kết quả test matching độc lập; phạm vi, kết quả và giới hạn tích hợp ghi trong tài liệu bàn giao.

## 8. Yêu cầu bổ sung

Khi có yêu cầu mới, ghi nội dung, nguồn, API/dữ liệu bị ảnh hưởng, dependency và tiêu chí nghiệm thu vào bảng này; cập nhật lại backlog và contract tương ứng.

| Yêu cầu mới | Nguồn | Ảnh hưởng | Tiêu chí nghiệm thu | Trạng thái |
| --- | --- | --- | --- | --- |
| Thiết kế bộ lọc và đặc tả GET Search/Matches | Yêu cầu người dùng bổ sung | `/api/v1/search`, `/api/v1/matches`; thay hai đường dẫn sơ bộ; cần metadata readiness | Query/response, mặc định, phân trang, lỗi, thứ tự và whitelist công khai | Đã viết [contract](api/search-matching-contract.md); chờ review liên module |
| Xây dựng thuật toán gợi ý/xếp hạng và GET matches | Yêu cầu người dùng bổ sung | Thuật toán thuần, DTO công khai, API matches và snapshot generation | Fixture tính tay, thứ tự ổn định, schema đúng, không lộ bằng chứng | Đã triển khai và test với bộ nhớ; còn tích hợp Posts/PostgreSQL theo [bàn giao](matching-implementation.md) |
