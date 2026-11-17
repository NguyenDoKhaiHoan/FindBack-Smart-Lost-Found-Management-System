# Thuật toán matching và API gợi ý — bàn giao triển khai

## Phạm vi đã xây dựng

- [scoring.py](../backend/app/modules/matching/services/scoring.py): chuẩn hóa, chấm cặp LOST–FOUND, giải thích và xếp hạng thuần, không AI/ML.
- [contracts.py](../backend/app/modules/matching/schemas/contracts.py): DTO công khai, query và response Pydantic, từ chối field ngoài whitelist.
- [snapshots.py](../backend/app/modules/matching/repositories/snapshots.py): interface snapshot cho Posts/generation và adapter bộ nhớ dùng trong demo/test, tính lại tường minh.
- [matches.py service](../backend/app/modules/matching/services/matches.py): kiểm tra nguồn, trạng thái kết quả, visibility, ngưỡng và phân trang.
- [matches.py router](../backend/app/modules/matching/routers/matches.py): `GET /api/v1/matches`, kiểm tra query/lỗi theo contract; OpenAPI tại `/docs`.

Đây là triển khai matching độc lập có API chạy được với dữ liệu demo. Chưa có adapter Posts/PostgreSQL, migration hoặc lưu kết quả bền vững. Ứng dụng mặc định trả `503 SERVICE_UNAVAILABLE` cho request matches hợp lệ khi chưa cấu hình adapter; không tự dùng seed giả làm dữ liệu thật. Search và ba API TV3 còn lại chưa triển khai.

## Cách tính điểm

Dùng cấu hình hiện có `rules-v1-draft`: danh mục 25, khu vực 25, thời gian 20, màu 10, từ khóa 10, thuộc tính công khai 10. Giữ tên phiên bản dự thảo để không tự tuyên bố nhóm đã phê duyệt. Nội dung chi tiết tại [matching-rules.md](matching-rules.md); API tại [contract](api/search-matching-contract.md).

1. Chỉ nhận hai DTO đã được Posts xác nhận công khai, đủ điều kiện, OPEN, khác ID và đúng một LOST/một FOUND. Model bắt buộc category/location hợp lệ và timestamp có timezone; adapter phải loại dữ liệu đầu vào thiếu hoặc chưa có độ chính xác phù hợp.
2. Chuẩn hóa UTC, từ khóa NFC/chữ thường/dấu câu thành khoảng trắng/từ dừng; thuộc tính chỉ brand/material. Không đọc dữ liệu claim hoặc tự suy màu/thuộc tính từ văn bản.
3. Danh mục/khu vực/màu giống mã thì nhận toàn bộ điểm tương ứng. Thiếu màu nhận 0. Thời gian FOUND trừ LOST: từ 0 đến 1 ngày nhận 20; trên 1 đến 3 ngày nhận 15; trên 3 đến 7 ngày nhận 5; ngoài khoảng nhận 0. Cận tính chính xác đến microsecond.
4. Từ khóa = 10 × giao/hợp hai tập từ; một tập rỗng nhận 0. Thuộc tính = 10 × số khớp/số key có ở cả hai; không có key chung nhận 0. Không phân bổ lại trọng số khi thiếu.
5. Tính bằng `Fraction` để giữ chính xác tỷ lệ; tổng làm tròn ROUND_HALF_UP đến 2 chữ số, rồi xét ngưỡng 50 và nhãn HIGH từ 75. Breakdown làm tròn riêng khi hiển thị.
6. Xếp điểm giảm dần → chênh lệch thời gian tuyệt đối tăng dần → UUID tin đối ứng tăng dần, trước phân trang. Match ID demo sinh UUIDv5 từ cặp có thứ tự LOST/FOUND để ổn định giữa các lần tính; adapter DB có thể dùng ID lưu thực tế, không dùng nó để xếp hạng.

Cặp khác danh mục hoặc FOUND trước LOST vẫn được chấm theo quy tắc hiện có, nhận 0 ở tiêu chí tương ứng. Cùng người đăng không phải điều kiện loại trong rules; Claims phải chặn tự claim độc lập. Không có output xác nhận chủ sở hữu hoặc thay đổi claim/return.

## Phối hợp Posts và vòng đời kết quả

`create_app(reader)` nhận implementation của `SnapshotReader.read(source_id)`; method trả snapshot tách rời, nhất quán gồm các PublicPostInput hiện tại và Generation đã tính hoàn tất. Trong DB, cần transaction/snapshot đọc nhất quán và truy vấn tập dữ liệu theo phạm vi; không tải toàn bộ bảng trong production chỉ vì adapter bộ nhớ làm vậy.

Posts chịu trách nhiệm ánh xạ trạng thái sang OPEN/CLOSED, xác nhận catalog category/location/color, precision của event_time, policy hiển thị/xóa mềm/kiểm duyệt và whitelist văn bản công khai. Cờ is_public/matching_eligible mặc định false; không truyền model ORM có bằng chứng vào matching. Text đã chứa bí mật phải bị loại tại nguồn, tên trường description không bảo đảm an toàn.

Generation chứa source_id, rule_version, calculated_at, fingerprint đầu vào công khai và các cặp đủ ngưỡng. Adapter bộ nhớ chỉ publish generation sau khi tính hoàn tất dưới lock; lưu metadata ngay cả khi không có cặp. Snapshot và dữ liệu đưa vào store được deep-copy để caller không thể sửa snapshot đang phục vụ.

GET không tính lại. Chưa có generation, phiên bản sai, nguồn thay đổi hoặc ứng viên đủ điều kiện mới/thay đổi thì trả 409 MATCHES_NOT_READY. Ứng viên bị ẩn/đóng/không còn đủ điều kiện được loại khỏi cả items và total. Một generation đã tính xong không có kết quả trả 200 với danh sách rỗng. Chỉnh dữ liệu chỉ để hiển thị cũng làm adapter demo yêu cầu tính lại vì fingerprint dùng toàn bộ DTO công khai; adapter production có thể tách content revision và scoring revision nếu vẫn bảo đảm contract.

Chức năng `MemoryMatchingStore.recalculate()` là lời gọi Python cho demo/test, không phải endpoint recalculate được bàn giao. Cần thiết kế persistence metadata, invalidation khi Posts thay đổi, locking/upsert và cập nhật nguyên tử khi tích hợp PostgreSQL. Không dùng fingerprint như cơ chế cấp quyền; GET vẫn kiểm tra policy hiện tại.

## Kiểm chứng

Chạy theo [backend README](../backend/README.md). Bộ unit/API test đối chiếu các ví dụ A–D của tài liệu quy tắc: 100, 0, 90, 61.67 điểm; biên 1/3/7 ngày, timezone, microsecond, dữ liệu thiếu, ngưỡng 50/75, ROUND_HALF_UP, hai chiều LOST/FOUND, tie-break và phân trang. Test API còn kiểm tra lỗi query, hidden/not-found cùng response, kết quả cũ/chưa tính, adapter chưa cấu hình và không lộ dữ liệu lỗi riêng tư.

Workspace chưa có tài liệu riêng tên SEARCH-01; bộ ví dụ trong matching-rules.md được dùng làm nguồn fixture hiện có. Nếu SEARCH-01 có bộ fixture bổ sung, cần đối chiếu thêm khi tài liệu đó được cung cấp.

Kết quả chạy hiện tại: **44 passed**, gồm unit và API TestClient; có một DeprecationWarning từ Starlette/AnyIO test tooling, không làm test thất bại. Lệnh từ thư mục gốc: `backend/.venv/Scripts/python -m pytest -c backend/pytest.ini backend/tests -q`.

Chưa kiểm chứng trên PostgreSQL hoặc tích hợp Posts thực tế. Không coi kết quả test bộ nhớ là bằng chứng đã hoàn thành các dependency này.
