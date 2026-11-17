# Thiết kế DB categories và matches — nội dung đính kèm Jira

## Mục tiêu
Thiết kế dữ liệu danh mục và liên kết gợi ý LOST–FOUND cho module Search & Matching trước khi triển khai thuật toán. Matching chỉ là gợi ý, không xác nhận chủ sở hữu hoặc duyệt claim.

## Trạng thái và phạm vi
Đề xuất để review với Posts và Claims, chưa phải migration đã tích hợp. File kèm theo: `matching-schema.sql`. Không triển khai endpoint, thuật toán chấm điểm hoặc bảng Posts/Claims trong task này. Ước lượng 5 giờ của KAN-23 không bao gồm công việc DB bổ sung.

## Thiết kế
- `categories`: id UUID, name, slug unique, is_active, created_at, updated_at. Danh mục một cấp; dùng is_active để ngừng sử dụng. Ứng dụng cập nhật updated_at khi sửa.
- `matches`: id UUID, lost_post_id, found_post_id, score 0–100, score_details JSONB, explanation, rule_version, calculated_at.
- Quan hệ: categories 1–N posts; posts (LOST) 1–N matches; posts (FOUND) 1–N matches. Một tin có nhiều gợi ý, mỗi cặp chỉ có một kết quả hiện hành.
- Khóa ngoại matches trỏ posts.id; không cho xóa cứng tin còn được tham chiếu. Không tự thay đổi cơ chế xóa mềm của Posts.
- Unique (lost_post_id, found_post_id); hai ID phải khác nhau. Index xếp hạng theo từng chiều: (post_id, score DESC, id).
- score_details phải là JSON object; cấu trúc tiêu chí/trọng số/cách xử lý thiếu dữ liệu chốt trong KAN-23. Không lưu bằng chứng hoặc đặc điểm bí mật.

## Phối hợp và điều kiện tích hợp
1. Posts xác nhận dùng UUID và các giá trị LOST/FOUND. Nếu khác, sửa DDL trước khi chạy.
2. Tạo categories trước; Posts tạo bảng posts và FK category_id; sau đó mới tạo matches. Script nguyên khối yêu cầu posts đã tồn tại và không tự thêm FK category_id để tránh sửa schema của module khác.
3. Posts phụ trách FK posts.category_id → categories.id (RESTRICT), index category_id và chính sách NOT NULL/backfill dữ liệu cũ.
4. Service Matching kiểm tra đúng loại LOST–FOUND và trạng thái hiển thị/đủ điều kiện. FK không kiểm tra loại tin. Posts phải ngăn đổi loại tin đang được tham chiếu, hoặc vô hiệu hóa matching liên quan trong cùng transaction trước khi đổi.
5. Tính lại cập nhật cặp hiện có bằng upsert và cập nhật calculated_at. Loại bỏ hoặc vô hiệu hóa cặp không còn đủ điều kiện; truy vấn gợi ý luôn kiểm tra lại khả năng hiển thị của tin.
6. Claims xác nhận phân biệt trường công khai với bằng chứng riêng tư. Không truy vấn claim_evidence để tính điểm, giải thích hay lưu score_details.
7. Thống nhất với Posts các trường: title/description, category_id, location, event_time, status. Màu và đặc điểm công khai chưa có cột riêng trong schema sơ bộ, cần chốt trước KAN-23.
8. Sau khi review, chuyển DDL thành Alembic migration theo dependency; chưa chạy script trực tiếp trên DB đang dùng chung.

## Tiêu chí nghiệm thu
- Có thiết kế hai bảng, quan hệ, kiểu dữ liệu, constraint và index được Posts thống nhất.
- Migration tương lai upgrade/downgrade được trên DB phát triển; downgrade matches trước posts/categories theo dependency.
- Kiểm chứng tạo cặp hợp lệ, chặn ID không tồn tại, cặp trùng, tự ghép, điểm âm/trên 100 và score_details không phải object.
- Service kiểm chứng loại LOST/FOUND; truy vấn không trả tin ẩn/xóa mềm hoặc trạng thái không đủ điều kiện theo contract.
- Tính lại không tạo cặp trùng và không giữ gợi ý đã mất hiệu lực.
- Danh mục đang được tin tham chiếu không bị xóa cứng; slug không trùng.
- Không lưu hoặc trả về bằng chứng bí mật; match không thay đổi claim/return.
- Có seed danh mục giả sau khi danh sách được nhóm thống nhất; không dùng dữ liệu cá nhân thật.

## Đầu ra
DDL đề xuất, tài liệu thiết kế và danh sách điểm cần thống nhất. Model, Alembic migration, seed và kết quả kiểm thử là đầu ra triển khai tiếp theo sau review.

## Kiểm chứng hiện tại
Đã đối chiếu với README và tài liệu trong repo. Chưa chạy DDL trên PostgreSQL: workspace chưa có bảng posts, cấu hình DB hoặc psql. Không coi các tiêu chí nghiệm thu ở trên là đã đạt.
