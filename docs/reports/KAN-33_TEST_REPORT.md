# BÁO CÁO KẾT QUẢ KIỂM THỬ TOÀN DIỆN (TEST EXECUTION REPORT)
## JIRA KAN-33: NOTIFICATION & ADMIN UNIT TESTING

**Dự án:** FindBack – Smart Lost & Found Management System
**Repository:** `FindBack-Smart-Lost-Found-Management-System`
**Nhánh làm việc:** `vu`
**Ngày thực hiện:** 17/11/2026
**Môi trường thực thi:** Python 3.11.9, pytest 9.1.1, pytest-asyncio 1.4.1, PostgreSQL 16 (findback_test)
**Trạng thái kiểm thử:** **100% PASSED (95/95 test cases)**

---

## 1. TỔNG QUAN VÀ MỤC TIÊU KIỂM THỬ

Jira KAN-33 đặt ra yêu cầu thiết lập hệ thống kiểm thử toàn diện cho hai phân hệ cốt lõi đã phát triển trong KAN-31 (Notifications) và KAN-32 (Admin Post Moderation, Audit Log, Posts Schema hoàn thiện).

Sau khi hoàn thành Phase 2 (Lập kế hoạch và Ma trận bao phủ A–H), Phase 3 đã tiến hành lập trình mã nguồn kiểm thử và thực thi nghiêm ngặt theo các tiêu chuẩn kiến trúc Modular Monolith của dự án:
1. **Kiểm thử Đơn vị Độc lập (Unit Tests):** Đóng gói toàn bộ logic nghiệp vụ của `PostModerationService` và `NotificationService` bằng Mock (`AsyncMock`, `MagicMock`), cách ly 100% khỏi cơ sở dữ liệu.
2. **Kiểm thử Tích hợp Cơ sở Dữ liệu (Database Integration Tests):** Kiểm tra trực tiếp trên PostgreSQL các ràng buộc toàn vẹn dữ liệu: `event_id UNIQUE`, `ON DELETE CASCADE`, `ON DELETE RESTRICT`, `ck_posts_moderation`, lưu trữ JSONB, và cơ chế khóa dòng độc quyền (`SELECT ... FOR UPDATE`).
3. **Kiểm thử Giao tiếp API & Giá trị Biên (API Edge Cases):** Xác thực định dạng tham số phân trang (`page <= 0`, `limit <= 0`, `limit > 100`), validate UUID không hợp lệ, lọc kết hợp 3 điều kiện, và bảo mật dữ liệu tuyệt đối (Zero sensitive leakage).

---

## 2. BẢNG THỐNG KÊ ĐỊNH LƯỢNG TỔNG QUAN

| Tiêu chí | Trước KAN-33 (Baseline Phase 1) | Sau KAN-33 (Hoàn thành Phase 3) | Biến động |
| :--- | :---: | :---: | :---: |
| **Tổng số test cases** | **68** | **95** | **+27 test cases (+39.7%)** |
| **Passed** | 68 | **95** | **+27 passed** |
| **Failed** | 0 | **0** | Giữ vững 0 lỗi |
| **Skipped** | 0 | **0** | 0 bỏ qua |
| **Errors** | 0 | **0** | 0 lỗi runtime |
| **Tỷ lệ vượt qua (Pass Rate)** | **100%** | **100%** | **Tuyệt đối** |
| **Tổng thời gian thực thi** | 37.13s | 55.53s | Toàn bộ 95 test suite |

---

## 3. KẾT QUẢ CHI TIẾT THEO PHÂN TẦNG KIỂM THỬ

### 3.1. Phân tầng Unit Tests (20/20 PASSED – Thời gian: 7.67s)
Cách ly hoàn toàn khỏi Database, sử dụng `AsyncMock` và `MagicMock` để đạt tốc độ phản hồi tính bằng mili-giây:

| File kiểm thử | Số test | Kết quả | Nội dung nghiệp vụ xác minh |
| :--- | :---: | :---: | :--- |
| `tests/unit/notifications_admin/test_notification_service.py` | 10 | 10/10 PASS | Làm sạch dữ liệu metadata (allowlist, cấm token/password ở root, nested object, nested array, uppercase/variant keys, recursion limit), xác thực recipient ACTIVE, quyền sở hữu thông báo. |
| `tests/unit/notifications_admin/test_post_moderation_service.py` | 10 | 10/10 PASS | **Mới:** Validate `status`/`type` không hợp lệ; tính toán số trang `total_pages = math.ceil(total / limit)` (total=0 -> 0, total lẻ, total chẵn); từ chối action khác HIDE; từ chối lý do rỗng; xử lý 404 post không tồn tại; từ chối post CLOSED (400); tính idempotent khi post đã HIDDEN; luồng thành công gọi audit repo và notify service với `auto_commit=False` và UUIDv5 deterministic; kích hoạt `session.rollback()` khi có lỗi. |

### 3.2. Phân tầng API Tests (63/63 PASSED – Thời gian: 43.87s)
Kiểm thử HTTP API thông qua `httpx.AsyncClient` có gắn token xác thực JWT:

| File kiểm thử | Số test | Kết quả | Nội dung nghiệp vụ xác minh |
| :--- | :---: | :---: | :--- |
| `tests/api/test_admin_posts.py` | 28 | 28/28 PASS | Phân quyền RBAC (ADMIN vs USER); phân trang; lọc status/type; tìm kiếm từ khóa `q`; ẩn bài viết thành công; ghi nhận audit log và notification; tính idempotent; rollback khi lỗi commit/notify; khóa tranh chấp đồng thời giữa 2 admin. <br>**3 Test Mới:** Giá trị biên phân trang (`page=0, -5`, `limit=0, 101`); lọc kết hợp đồng thời (`status=ACTIVE & type=LOST & q=ví da`); từ chối path param không phải UUID (422). |
| `tests/api/test_notifications.py` | 20 | 20/20 PASS | Endpoint health check; bảo mật xác thực (no token, malformed UUID, bad signature, expired token, alg none, unknown user); kiểm soát truy cập (user SUSPENDED/DISABLED); cách ly tenant (chỉ thấy thông báo của mình); đánh dấu đã đọc idempotent; khử trùng lặp sự kiện tuần tự và đồng thời (CONC-01). <br>**2 Test Mới:** Giá trị biên phân trang (`page=0, -1`, `limit=0, 101`); xác minh phản hồi không chứa dữ liệu nhạy cảm (`password_hash`, tokens, private evidence). |
| `tests/api/test_posts_schema.py` | 15 | 15/15 PASS | Kiểm tra hồi quy toàn diện Posts Schema KAN-32: Categories slug unique (`uq_categories_slug`), category delete SET NULL, post delete CASCADE post_images, ràng buộc tọa độ GPS (`ck_posts_latitude`, `ck_posts_longitude`, `ck_posts_gps_pair`), trường item nullable, tương thích Admin listing và moderation. |

### 3.3. Phân tầng Database Integration Tests (12/12 PASSED – Thời gian: 8.26s)
Kiểm tra trực tiếp các ràng buộc toàn vẹn tầng lưu trữ PostgreSQL trên cơ sở dữ liệu `findback_test`:

| File kiểm thử | Số test | Kết quả | Nội dung nghiệp vụ xác minh |
| :--- | :---: | :---: | :--- |
| `tests/integration/test_notification_database.py` | 5 | 5/5 PASS | **Mới:** <br>1. Ràng buộc `event_id UNIQUE` ở PostgreSQL ném `IntegrityError` khi chèn trùng.<br>2. Xóa User kích hoạt `ON DELETE CASCADE` tự động dọn sạch notifications liên quan.<br>3. Cơ chế `auto_commit=False`: khi transaction bên ngoài rollback, notification hoàn toàn không tồn tại trong DB.<br>4. Cách ly dữ liệu đa người dùng: user A và user B không bị lẫn dữ liệu.<br>5. Lưu trữ JSONB Unicode phức tạp và lọc chính xác thông báo chưa đọc (`is_read=False`). |
| `tests/integration/test_admin_audit_database.py` | 7 | 7/7 PASS | **Mới:** <br>1. Xóa Admin đã tạo audit log bị chặn bởi `fk_audit_logs_actor` (`ON DELETE RESTRICT`).<br>2. Xóa Admin đã kiểm duyệt post bị chặn bởi `fk_posts_moderated_by` (`ON DELETE RESTRICT`).<br>3. Ràng buộc `ck_posts_moderation` từ chối các trường hợp khuyết thiếu `moderated_at`, khuyết thiếu `moderated_by`, hoặc lý do rỗng/khoảng trắng.<br>4. Lưu trữ JSONB metadata của Audit Log (hỗ trợ cờ cảnh báo PII, IP, tiếng Việt có dấu).<br>5. Kiểm tra sự tồn tại của index tổng hợp `ix_audit_logs_target` `(target_type, target_id, created_at DESC)` trong PostgreSQL system catalog.<br>6. **Atomicity thực tế cấp Service:** Khi `NotificationService` phát sinh lỗi, toàn bộ thay đổi trên `posts` và `audit_logs` đều bị rollback, post giữ nguyên `ACTIVE`.<br>7. **Khóa dòng cạnh tranh `SELECT ... FOR UPDATE`:** Hai session async độc lập khóa cùng một post; session 2 với `nowait=True` bị chặn ngay lập tức (`OperationalError`), khi session 1 rollback thì session 2 lấy khóa thành công. Có timeout 3s chống treo test runner. |

---

## 4. BẰNG CHỨNG KỸ THUẬT CHUYÊN SÂU (TECHNICAL EVIDENCE)

### 4.1. Bằng chứng Tính Nguyên tử Giao dịch (Transaction Rollback & Atomicity)
- **Cấp độ Unit:** Hàm `test_moderate_post_exception_triggers_session_rollback` chứng minh khi có ngoại lệ phát sinh trong `create_notification`, phương thức `moderate_post` lập tức gọi `await session.rollback()` và không bao giờ gọi `session.commit()`.
- **Cấp độ Database PostgreSQL:** Hàm `test_admin_post_moderation_service_atomicity_on_failure` chạy thực tế trên cơ sở dữ liệu `findback_test`:
  - Khởi tạo bài viết có trạng thái `ACTIVE`.
  - Gọi `service.moderate_post` với mock `NotificationService` ném `RuntimeError`.
  - Bắt ngoại lệ và mở một session độc lập mới (`TestingSessionLocal()`) để truy vấn database:
    $$\text{post.status} = \text{"ACTIVE"} \quad \land \quad \text{post.moderated\_by} = \text{None}$$
    $$\text{COUNT(audit\_logs WHERE target\_id = post.id)} = 0$$
    $$\text{COUNT(notifications WHERE resource\_id = post.id)} = 0$$
  - Khẳng định 100% không phát sinh dữ liệu rác hoặc dữ liệu mồ côi (orphaned record) trong DB.

### 4.2. Bằng chứng Khóa Dòng Tranh chấp Đồng thời (`SELECT ... FOR UPDATE`)
- Hàm `test_concurrent_row_lock_select_for_update_between_two_sessions` sử dụng 2 `AsyncSession` độc lập kết nối vào PostgreSQL:
  1. `session1` thực thi `SELECT * FROM posts WHERE id = :id FOR UPDATE`, giữ khóa dòng độc quyền.
  2. `session2` cố gắng thực thi `SELECT * FROM posts WHERE id = :id FOR UPDATE NOWAIT`.
  3. PostgreSQL ngay lập tức ném lỗi `OperationalError` (mã lỗi `55P03: lock_not_available`).
  4. Lệnh chờ được bọc trong `asyncio.wait_for(..., timeout=3.0)` bảo đảm không phụ thuộc vào thời gian cứng và không bao giờ làm treo pytest runner.
  5. Sau khi `session1.rollback()`, khóa được giải phóng và `session2` truy vấn thành công.

### 4.3. Bằng chứng Bảo vệ Lịch sử Kiểm toán (`ON DELETE RESTRICT`)
- Hàm `test_audit_log_actor_fk_restrict_delete`: Thực hiện lệnh xóa người dùng Admin đã ghi log kiểm toán. PostgreSQL kích hoạt khóa ngoại `fk_audit_logs_actor` và từ chối thao tác với `IntegrityError`.
- Hàm `test_post_moderated_by_fk_restrict_delete`: Thực hiện lệnh xóa Admin đã duyệt ẩn một bài viết. PostgreSQL kích hoạt khóa ngoại `fk_posts_moderated_by` và từ chối thao tác với `IntegrityError`.

---

## 5. XÁC MINH AN TOÀN CƠ SỞ DỮ LIỆU (DATABASE SAFETY VERIFICATION)

Tuân thủ nghiêm ngặt quy định an toàn dữ liệu:
1. **Kiểm tra URL kết nối:** Cấu hình trong `backend/tests/conftest.py` kiểm tra tự động trước mỗi phiên chạy:
   ```python
   db_name = test_engine.url.database
   if not db_name or "test" not in db_name.lower() or db_name.lower() == "findback":
       raise RuntimeError("Refusing to execute tests against development database!")
   ```
2. **Cơ sở dữ liệu phát triển:** Database `findback` hoàn toàn không bị ảnh hưởng, giữ nguyên version migration `20261117_04 (head)`.
3. **Cơ sở dữ liệu kiểm thử:** Toàn bộ test chạy trên `findback_test` và được dọn dẹp sạch sẽ sau mỗi test case thông qua fixture `prepare_and_clean_database` (`autouse=True`).

---

## 6. DANH MỤC FILE TẠO MỚI VÀ CHỈNH SỬA

### File tạo mới (3 files):
1. `backend/tests/unit/notifications_admin/test_post_moderation_service.py` (10 Unit tests độc lập cho PostModerationService)
2. `backend/tests/integration/test_notification_database.py` (5 Database Integration tests cho Notifications)
3. `backend/tests/integration/test_admin_audit_database.py` (7 Database Integration tests cho Admin Audit & Constraints)

### File chỉnh sửa bổ sung (2 files):
1. `backend/tests/api/test_notifications.py` (Bổ sung 2 tests: phân trang biên và rà soát dữ liệu nhạy cảm)
2. `backend/tests/api/test_admin_posts.py` (Bổ sung 3 tests: phân trang biên, lọc kết hợp 3 tiêu chí, validate UUID)

### Tài liệu tạo mới (3 files):
1. `docs/reports/KAN-33_TEST_PLAN.md` (Kế hoạch kiểm thử & Ma trận bao phủ A–H)
2. `docs/reports/KAN-33_TEST_REPORT.md` (Báo cáo kết quả kiểm thử này)
3. `docs/reports/KAN-33_CODE_WALKTHROUGH.md` (Tài liệu hướng dẫn đọc mã nguồn kiểm thử)

---

## 7. ĐÁNH GIÁ ĐỘ BAO PHỦ VÀ CÁC TEST CHƯA THỰC HIỆN

- **Về công cụ đo coverage:** Môi trường kiểm thử hiện tại không cài đặt thư viện bên thứ ba `pytest-cov`. Do đó, theo nguyên tắc minh bạch kỹ thuật, báo cáo **không tự ý tuyên bố con số 100% coverage**.
- **Về độ bao phủ nghiệp vụ:**
  - Toàn bộ các nhánh logic chính, nhánh ngoại lệ (`ValidationError`, `BadRequestError`, `NotFoundError`), toán học phân trang, cơ chế bảo vệ metadata, và các ràng buộc toàn vẹn cơ sở dữ liệu đã được bao phủ toàn diện bởi 95 test case.
  - Không có test case nào bị bỏ sót hoặc chưa thực hiện.

---

## 8. TRẠNG THÁI GIT VÀ SẴN SÀNG REVIEW

- **Nhánh hiện tại:** `vu` (đồng bộ với `origin/vu`).
- **Trạng thái Git:**
  - Files modified (unstaged): `backend/tests/api/test_admin_posts.py`, `backend/tests/api/test_notifications.py`.
  - Files untracked: Các file test mới trong `backend/tests/unit/` và `backend/tests/integration/`, tài liệu báo cáo trong `docs/reports/`.
- **Quy tắc tuân thủ:** Không có lệnh `git commit`, `git push`, `git merge`, hay `git rebase` nào được thực hiện. Toàn bộ mã nguồn sẵn sàng chờ chỉ đạo tiếp theo từ Tech Lead / User.

---
**KẾT THÚC BÁO CÁO KẾT QUẢ KIỂM THỬ KAN-33**
