# Yêu cầu nghiệp vụ

Nguồn: [Tài liệu phân tích FindBack](https://docs.google.com/document/d/1F8Ngu5ViIxa2_9FLnt-T6s5GJ4o-B8GCtC_KmvlPFOg/edit?usp=sharing).

## Phạm vi

MVP phục vụ người mất đồ, người nhặt được đồ và quản trị viên. Một tài khoản user có thể đăng tin LOST hoặc FOUND; người giữ đồ xem xét bằng chứng để xác minh. Vai trò đơn vị quản lý địa điểm được mở rộng sau MVP.

Luồng nghiệm thu: đăng tin → tìm kiếm/matching → claim → xác minh → trao trả → đóng hồ sơ. Matching dựa trên quy tắc và điểm tương đồng; AI hình ảnh/LLM là P2.

| Mã | Nhóm | Kết quả mong đợi |
| --- | --- | --- |
| BR-01 | Identity | Đăng ký, đăng nhập, hồ sơ, phân quyền user/admin |
| BR-02 | Posts | Tạo, xem, sửa, ẩn tin LOST/FOUND; chỉ chủ tin được sửa |
| BR-03 | Search | Lọc theo danh mục, khu vực, thời gian, trạng thái |
| BR-04 | Matching | Gợi ý LOST–FOUND và giải thích tiêu chí |
| BR-05 | Claims | Gửi yêu cầu nhận đồ với bằng chứng sở hữu riêng tư |
| BR-06 | Verification | Người giữ đồ/điều phối viên xem xét, duyệt hoặc từ chối |
| BR-07 | Returns | Theo dõi bàn giao, xác nhận hoàn thành, lưu lịch sử |
| BR-08 | Notifications | Thông báo trong ứng dụng khi có claim hoặc đổi trạng thái |
| BR-09 | Moderation | Báo cáo vi phạm, ẩn tin và thống kê quản trị |

## Quy tắc bắt buộc

1. Chỉ người đăng nhập được đăng tin, gửi claim hoặc xác nhận trao trả.
2. Tin phải có danh mục, mô tả, thời gian và khu vực. Dữ liệu nhạy cảm không hiển thị công khai.
3. Chỉ chủ tin được chỉnh sửa; thao tác kiểm duyệt của admin là luồng riêng, phải kiểm tra quyền.
4. Không cho phép tự claim tin của mình; hạn chế claim trùng đang mở.
5. Bằng chứng chỉ người có quyền được xem. Không dùng đặc điểm bí mật làm thông tin công khai hoặc giải thích matching.
6. Claim bắt đầu `PENDING`, chuyển sang `APPROVED`, `REJECTED` hoặc `CANCELLED` theo điều kiện hợp lệ.
7. Chỉ tạo return từ claim được duyệt. Return đi qua `ARRANGED → HANDED_OVER → CONFIRMED`.
8. Chỉ đóng tin khi xác nhận hợp lệ. Duyệt, từ chối và trao trả đều ghi audit log.
9. Xử lý nhiều claim trên một đồ vật bằng transaction/constraint; không chỉ kiểm tra ở UI.
10. Cần hỗ trợ hủy hoặc báo cáo tranh chấp theo chính sách được thống nhất.

## Điểm cần chốt trước khi triển khai

Tài liệu hiện là phân tích sơ bộ; các quyết định sau chưa được quy định đầy đủ:

- Tên trạng thái tin, điều kiện ẩn/đóng/mở lại và quan hệ với trạng thái claim/return.
- Ai có quyền xem bằng chứng, duyệt claim và xác nhận từng bước bàn giao; vai trò điều phối viên ánh xạ ra sao trong MVP chỉ có user/admin.
- Quy tắc xử lý claim cạnh tranh, số claim được duyệt trên một tin và phạm vi của claim đang mở.
- Luồng hủy, tranh chấp, bước `HANDED_OVER` và endpoint tương ứng; danh mục 30 API chưa mô tả đầy đủ các thao tác này.
- Kiểu dữ liệu vị trí, trọng số/điểm ngưỡng matching và quyền gọi tính lại điểm.
- Phân trang, schema lỗi, vòng đời token, upload ảnh/bằng chứng và giới hạn file.

Những điểm này cần được đưa vào API contract và thiết kế dữ liệu trước khi viết logic, không được coi là hành vi đã triển khai.
