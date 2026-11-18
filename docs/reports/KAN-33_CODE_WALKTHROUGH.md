# HƯỚNG DẪN ĐỌC VÀ HIỂU MÃ NGUỒN KIỂM THỬ (CODE WALKTHROUGH)
## JIRA KAN-33: NOTIFICATION & ADMIN UNIT TESTING

**Dự án:** FindBack – Smart Lost & Found Management System
**Dành cho:** Kỹ sư phát triển Backend mới gia nhập dự án (Onboarding Developers) & Code Reviewers
**Ngôn ngữ:** Tiếng Việt
**Phiên bản tài liệu:** 1.0 (Hoàn thành Phase 3)

---

## MỤC LỤC
1. [Giới thiệu & Triết lý Kiểm thử FindBack](#1-giới-thiệu--triết-lý-kiểm-thử-findback)
2. [Bản đồ Cấu trúc Thư mục Kiểm thử](#2-bản-đồ-cấu-trúc-thư-mục-kiểm-thử)
3. [Tìm hiểu Tầng Nền tảng: `conftest.py`](#3-tìm-hiểu-tầng-nền-tảng-conftestpy)
4. [Hướng dẫn Chi tiết Từng File Kiểm thử](#4-hướng-dẫn-chi-tiết-từng-file-kiểm-thử)
   - [4.1. Unit Tests: `test_post_moderation_service.py`](#41-unit-tests-test_post_moderation_servicepy)
   - [4.2. Unit Tests: `test_notification_service.py`](#42-unit-tests-test_notification_servicepy)
   - [4.3. Database Integration: `test_notification_database.py`](#43-database-integration-test_notification_databasepy)
   - [4.4. Database Integration: `test_admin_audit_database.py`](#44-database-integration-test_admin_audit_databasepy)
   - [4.5. API End-to-End: `test_admin_posts.py`](#45-api-end-to-end-test_admin_postspy)
   - [4.6. API End-to-End: `test_notifications.py`](#46-api-end-to-end-test_notificationspy)
   - [4.7. Schema Regression: `test_posts_schema.py`](#47-schema-regression-test_posts_schemapy)
5. [Cẩm nang Thực thi & Gỡ lỗi (Debugging Guide)](#5-cẩm-nang-thực-thi--gỡ-lỗi-debugging-guide)

---

## 1. GIỚI THIỆU & TRIẾT LÝ KIỂM THỬ FINDBACK

Dự án FindBack được thiết kế theo kiến trúc **Modular Monolith**, phân lớp nghiêm ngặt:
$$\text{Router (API Layer)} \longrightarrow \text{Service (Business Logic)} \longrightarrow \text{Repository (Data Access)} \longrightarrow \text{Database (PostgreSQL)}$$

Khi kiểm thử hệ thống, chúng ta áp dụng mô hình **Kim tự tháp Kiểm thử (Testing Pyramid)** với 3 phân tầng rõ rệt:
1. **Unit Tests (Đỉnh tháp - Tốc độ cao):** Kiểm tra logic nghiệp vụ nội tại của các Service bằng cách thay thế các thành phần phụ thuộc (Repository, External Services, Database Session) bằng **Mock Objects** (`unittest.mock.AsyncMock`, `MagicMock`). Thời gian chạy tính bằng mili-giây, độc lập 100% với môi trường bên ngoài.
2. **Integration Tests (Thân tháp - Tính toàn vẹn):** Kiểm tra trực tiếp các ràng buộc toàn vẹn của Cơ sở dữ liệu PostgreSQL (Foreign Key RESTRICT, CASCADE, Check Constraints, Row Locking `SELECT FOR UPDATE`, Unique Constraints, JSONB). Chạy trên cơ sở dữ liệu kiểm thử cô lập `findback_test`.
3. **API / End-to-End Tests (Đáy tháp - Luồng người dùng):** Sử dụng `httpx.AsyncClient` gửi HTTP request có gắn JWT token đến FastAPI app, kiểm tra toàn bộ chu trình từ Router qua Service xuống Database và phản hồi mã trạng thái HTTP.

---

## 2. BẢN ĐỒ CẤU TRÚC THƯ MỤC KIỂM THỬ

Toàn bộ mã kiểm thử được lưu trữ tập trung tại thư mục `backend/tests/`:

```
backend/tests/
│
├── conftest.py                                       # [Cốt lõi] Fixtures dùng chung, thiết lập DB test, tạo JWT
│
├── unit/                                             # [Tầng Unit] Kiểm thử logic thuần túy với Mock (Không đụng DB)
│   └── notifications_admin/
│       ├── test_notification_service.py              # 10 tests: Làm sạch metadata nhạy cảm, validate người nhận
│       └── test_post_moderation_service.py           # 10 tests: Nghiệp vụ duyệt bài Admin, phân trang, rollback
│
├── integration/                                      # [Tầng Integration] Tương tác trực tiếp PostgreSQL test
│   ├── test_notification_database.py                 # 5 tests: Unique event_id, cascade delete, JSONB, unread count
│   └── test_admin_audit_database.py                  # 7 tests: Restrict delete, check constraint, lock FOR UPDATE
│
└── api/                                              # [Tầng API] Kiểm thử endpoint HTTP và RBAC
    ├── test_admin_posts.py                           # 28 tests: Quản trị bài viết, tìm kiếm, ẩn bài, atomicity
    ├── test_notifications.py                         # 20 tests: Lấy thông báo, đánh dấu đã đọc, an ninh JWT
    └── test_posts_schema.py                          # 15 tests: Hồi quy schema Posts (Categories, Images, GPS)
```

---

## 3. TÌM HIỂU TẦNG NỀN TẢNG: `conftest.py`

File `backend/tests/conftest.py` là trái tim của hệ thống kiểm thử, cung cấp các công cụ và cơ chế an toàn:

### 3.1. Cơ chế Bảo vệ An toàn Cơ sở Dữ liệu (Database Safety Guard)
Hệ thống kiểm tra nghiêm ngặt biến môi trường `DATABASE_URL` trước khi bất kỳ bài test nào được chạy. Nếu tên cơ sở dữ liệu không chứa từ khóa `"test"` hoặc trỏ nhầm vào `"findback"` (cơ sở dữ liệu phát triển), test runner sẽ **lập tức ném ngoại lệ và dừng chạy**:
```python
db_name = test_engine.url.database
if not db_name or "test" not in db_name.lower() or db_name.lower() == "findback":
    raise RuntimeError("CRITICAL TEST CONFIG ERROR: Refusing to execute tests against development database!")
```

### 3.2. Fixture Tự động Dọn dẹp (`prepare_and_clean_database`)
Được gắn cờ `autouse=True`, tự động chạy trước và sau mỗi test case:
- **Trước test:** Đảm bảo tất cả các bảng tồn tại qua `Base.metadata.create_all`.
- **Sau test:** Thực thi `TRUNCATE TABLE ... CASCADE;` dọn sạch dữ liệu trong các bảng `audit_logs`, `notifications`, `post_images`, `posts`, `categories`, `users`. Nhờ đó, mỗi test case luôn có môi trường sạch sẽ, không bị ảnh hưởng bởi dữ liệu của test case trước.

### 3.3. Các Fixture Dữ liệu Mẫu (Test Users & Auth Headers)
- `test_user_a`, `test_user_b`: Người dùng thông thường (`role="USER"`), trạng thái `ACTIVE`.
- `test_admin_user`: Quản trị viên (`role="ADMIN"`), trạng thái `ACTIVE`.
- `test_inactive_user`, `test_disabled_user`: Người dùng bị khóa (`SUSPENDED`, `DISABLED`).
- `auth_headers_user_a`, `auth_headers_admin`: Header `{"Authorization": "Bearer <jwt>"}` hợp lệ được ký mã hóa bằng thuật toán HS256.

---

## 4. HƯỚNG DẪN CHI TIẾT TỪNG FILE KIỂM THỬ

---

### 4.1. Unit Tests: `test_post_moderation_service.py`
**Đường dẫn:** `backend/tests/unit/notifications_admin/test_post_moderation_service.py`
**Đối tượng kiểm thử:** Class `PostModerationService` trong `app/modules/notifications_admin/services/post_moderation_service.py`.
**Đặc điểm:** Toàn bộ dependencies được mock qua `unittest.mock.AsyncMock`.

| Tên hàm kiểm thử | Nghiệp vụ kiểm tra | Cách đọc code |
| :--- | :--- | :--- |
| `test_list_posts_invalid_status_raises_validation_error` | Kiểm tra validate tham số `status` | Truyền `status="INVALID_STATUS"`, assert ném lỗi `ValidationError` kèm câu thông báo tiếng Việt. |
| `test_list_posts_invalid_type_raises_validation_error` | Kiểm tra validate tham số `type_` | Truyền `type_="UNKNOWN_TYPE"`, assert ném lỗi `ValidationError`. |
| `test_list_posts_pagination_math_calculation` | Kiểm tra công thức tính `total_pages` | Kiểm tra 4 tình huống toán học: `total=0` -> 0 trang, `total=45, limit=20` -> 3 trang, `total=40, limit=20` -> 2 trang, `total=1, limit=20` -> 1 trang. |
| `test_moderate_post_unsupported_action_raises_bad_request` | Kiểm tra hành động kiểm duyệt | Truyền `action="DELETE"`, assert ném `BadRequestError` vì phạm vi KAN-32 chỉ hỗ trợ `HIDE`. |
| `test_moderate_post_empty_reason_raises_validation_error` | Kiểm tra lý do kiểm duyệt rỗng | Kiểm tra 2 lớp bảo vệ: Lớp 1 (Pydantic Schema validator) và Lớp 2 (Service defense-in-depth với `model_construct`). |
| `test_moderate_post_nonexistent_post_raises_not_found` | Kiểm tra bài viết không tồn tại | Mock `post_repository.get_by_id` trả về `None`, assert ném `NotFoundError` (404) và xác nhận gọi `for_update=True`. |
| `test_moderate_post_closed_post_raises_bad_request` | Kiểm tra bài viết đã đóng | Mock bài viết có `status="CLOSED"`, assert ném `BadRequestError` (400) không cho phép kiểm duyệt bài đã đóng. |
| `test_moderate_post_already_hidden_is_idempotent` | Kiểm tra tính Idempotent khi duyệt lặp | Mock bài viết đã ở trạng thái `HIDDEN`. Assert hàm trả về dữ liệu kiểm duyệt ban đầu, KHÔNG gọi tạo audit log mới, KHÔNG tạo notification mới, KHÔNG commit session. |
| `test_moderate_post_success_flow` | Kiểm tra luồng kiểm duyệt thành công | Mock bài viết `ACTIVE`. Assert: status đổi thành `HIDDEN`; gọi `audit_log_repository.create` đúng tham số; gọi `notification_service.create_notification` với `auto_commit=False` và mã định danh sự kiện xác định UUIDv5 `uuid5(NAMESPACE_OID, "POST_HIDDEN:<post_id>")`. |
| `test_moderate_post_exception_triggers_session_rollback` | Kiểm tra Rollback khi có lỗi | Giả lập `create_notification` ném `RuntimeError`. Assert service kích hoạt `await session.rollback()` và KHÔNG gọi `session.commit()`. |

---

### 4.2. Unit Tests: `test_notification_service.py`
**Đường dẫn:** `backend/tests/unit/notifications_admin/test_notification_service.py`
**Đối tượng kiểm thử:** Class `NotificationService` và phương thức tĩnh `sanitize_metadata`.
**Mục tiêu bảo mật:** Đảm bảo không bao giờ có dữ liệu nhạy cảm (token, mật khẩu, PII) lọt vào cơ sở dữ liệu thông báo (theo điều khoản PRIV-01).

- `test_metadata_sanitization_1_valid_metadata`: Dữ liệu chứa các trường trong whitelist (`post_id`, `resource_type`, `action`) được giữ nguyên.
- `test_metadata_sanitization_2_token_at_root`: Tự động loại bỏ key `token` ở root level.
- `test_metadata_sanitization_3_token_in_nested_object`: Quét đệ quy object con và loại bỏ `access_token`.
- `test_metadata_sanitization_4_password_in_nested_array`: Quét đệ quy mảng danh sách và loại bỏ `password_hash`.
- `test_metadata_sanitization_5_uppercase_keys`: Chuẩn hóa chữ thường các key viết hoa (`PASSWORD`, `TOKEN`) để ngăn chặn vượt rào.
- `test_metadata_sanitization_6_variant_key_names`: Nhận diện các biến thể như `client_secret`, `auth_key`.
- `test_metadata_sanitization_7_unapproved_fields_rejected`: Loại bỏ tất cả các trường tùy tiện không nằm trong whitelist.
- `test_metadata_sanitization_8_deeply_nested_levels`: Ngăn chặn tấn công DoS đệ quy lồng sâu.
- `test_unit_service_ownership_enforcement`: Chặn người dùng A truy cập thông báo của người dùng B.
- `test_unit_service_inactive_recipient_rejected`: Từ chối tạo thông báo cho người dùng `SUSPENDED` hoặc `DISABLED`.

---

### 4.3. Database Integration: `test_notification_database.py`
**Đường dẫn:** `backend/tests/integration/test_notification_database.py`
**Đối tượng kiểm thử:** Bảng `notifications`, quan hệ khóa ngoại, và `NotificationRepository` tương tác trực tiếp với PostgreSQL test DB.

- `test_notification_event_id_unique_constraint`: Thêm trực tiếp 2 bản ghi có cùng `event_id`. PostgreSQL lập tức ném lỗi `IntegrityError` từ chỉ mục `ix_notifications_event_id_unique`.
- `test_notification_recipient_fk_cascade_delete`: Tạo người dùng và thông báo. Xóa người dùng khỏi bảng `users`. Xác nhận toàn bộ thông báo của người dùng đó bị xóa tự động theo nhờ ràng buộc `fk_notifications_recipient` (`ON DELETE CASCADE`).
- `test_notification_auto_commit_false_rollback`: Gọi `create_notification` với `auto_commit=False`, sau đó gọi `session.rollback()`. Mở một session mới xác nhận bản ghi thông báo hoàn toàn không tồn tại trong DB.
- `test_multi_user_notification_isolation`: Tạo 3 thông báo cho User A và 2 thông báo cho User B. Gọi hàm `list_by_recipient` cho từng user, xác nhận kết quả trả về đúng số lượng và tuyệt đối không lộ dữ liệu của nhau.
- `test_notification_metadata_jsonb_storage_and_unread_count`: Lưu trữ payload JSONB phức tạp (chứa tiếng Việt có dấu, mảng, số nguyên). Đọc lại từ DB xác minh không bị lỗi encoding Unicode và kiểm tra bộ lọc `is_read=False`.

---

### 4.4. Database Integration: `test_admin_audit_database.py`
**Đường dẫn:** `backend/tests/integration/test_admin_audit_database.py`
**Đối tượng kiểm thử:** Bảng `audit_logs`, `posts`, tính toàn vẹn giao dịch và khóa dòng cạnh tranh.

- `test_audit_log_actor_fk_restrict_delete`: Thử xóa tài khoản Admin đã từng ghi log kiểm toán. Bị PostgreSQL chặn lại với `IntegrityError` (`fk_audit_logs_actor ON DELETE RESTRICT`), bảo vệ dữ liệu audit không thể bị phá hủy.
- `test_post_moderated_by_fk_restrict_delete`: Thử xóa Admin đã duyệt bài viết. Bị PostgreSQL chặn lại với `IntegrityError` (`fk_posts_moderated_by ON DELETE RESTRICT`).
- `test_post_moderation_check_constraint_integrity`: Kiểm tra ràng buộc `ck_posts_moderation`:
  - Từ chối khi có `moderated_by` nhưng thiếu `moderated_at`.
  - Từ chối khi có `moderated_at` nhưng thiếu `moderated_by`.
  - Từ chối khi lý do kiểm duyệt chỉ chứa khoảng trắng rỗng (`"     "`).
  - Chấp nhận khi cả 3 trường cùng `NULL` (bài viết chưa duyệt).
  - Chấp nhận khi cả 3 trường cùng có dữ liệu hợp lệ.
- `test_audit_log_jsonb_metadata_storage`: Kiểm tra lưu trữ JSONB trong bảng `audit_logs` (thông tin IP, cờ bảo mật PII, tiêu đề bài viết).
- `test_audit_log_index_target_type_id_created`: Truy vấn trực tiếp view hệ thống `pg_indexes` của PostgreSQL, khẳng định index tổng hợp `ix_audit_logs_target` trên các cột `(target_type, target_id, created_at DESC)` tồn tại và hoạt động.
- `test_admin_post_moderation_service_atomicity_on_failure`: **Kiểm thử ACID Transaction thực tế:** Cho service chạy trên PostgreSQL thật nhưng mock bước gửi thông báo bị crash. Khẳng định trong DB: bài viết vẫn giữ nguyên trạng thái `ACTIVE`, không có audit log nào được tạo, không có thông báo nào được lưu.
- `test_concurrent_row_lock_select_for_update_between_two_sessions`: **Kiểm thử Khóa dòng đồng thời:**
  - `session1` truy vấn bài viết với `SELECT ... FOR UPDATE`.
  - `session2` cố gắng truy vấn cùng bài viết đó với `SELECT ... FOR UPDATE NOWAIT`.
  - PostgreSQL lập tức ném lỗi `OperationalError` (không lấy được khóa).
  - Bọc trong `asyncio.wait_for(..., timeout=3.0)` để đảm bảo an toàn, không bao giờ làm treo test runner.
  - Sau khi `session1` rollback giải phóng khóa, `session2` lấy khóa thành công.

---

### 4.5. API End-to-End: `test_admin_posts.py`
**Đường dẫn:** `backend/tests/api/test_admin_posts.py`
**Đối tượng kiểm thử:** Các endpoint `/api/v1/admin/posts` và `/api/v1/admin/posts/{id}/moderation`.

- **Phân quyền RBAC:** Người dùng chưa đăng nhập nhận 401; Người dùng thường nhận 403; Quản trị viên (ADMIN) truy cập thành công 200.
- **Phân trang & Tìm kiếm:** Lọc bài viết theo `status`, theo `type`, tìm kiếm từ khóa `q`.
- **Thực hiện ẩn bài viết (HIDE):** Cập nhật trạng thái `HIDDEN`, ghi nhận Admin kiểm duyệt, thời gian duyệt, lý do duyệt.
- **Rollback khi xảy ra sự cố:** Giả lập lỗi ở bước tạo thông báo hoặc lỗi commit DB, đảm bảo trạng thái bài viết không bị thay đổi dở dang.
- **Xử lý giá trị biên (Mới):**
  - `test_admin_posts_pagination_boundary_values`: Gửi `page=0`, `page=-5`, `limit=0`, `limit=101` đều nhận về mã lỗi HTTP 422.
  - `test_admin_posts_combined_filters_and_search`: Kết hợp đồng thời 3 điều kiện: `status=ACTIVE` + `type=LOST` + `q="ví da"`, trả về kết quả chính xác duy nhất.
  - `test_admin_posts_invalid_uuid_param_rejected`: Gửi chuỗi không phải UUID (ví dụ `not-a-valid-uuid-format`), FastAPI tự động chặn và trả về lỗi 422.

---

### 4.6. API End-to-End: `test_notifications.py`
**Đường dẫn:** `backend/tests/api/test_notifications.py`
**Đối tượng kiểm thử:** Các endpoint `/api/v1/notifications` và `/api/v1/notifications/{id}/read`.

- **Bảo mật JWT:** Từ chối token UUID thô, token sai chữ ký, token hết hạn, token sử dụng thuật toán `none`, token chứa user ID không tồn tại.
- **Kiểm soát người dùng:** Chặn tài khoản `SUSPENDED` và `DISABLED` với mã lỗi 403.
- **Cách ly dữ liệu:** Người dùng chỉ xem được thông báo của chính mình; không thể đánh dấu đọc thông báo của người khác.
- **Khử trùng lặp sự kiện:** Khi nhận nhiều sự kiện có cùng `event_id` (tuần tự hoặc chạy đồng thời 5 luồng), hệ thống chỉ sinh ra đúng 1 bản ghi thông báo trong DB.
- **Xử lý giá trị biên & Bảo mật dữ liệu (Mới):**
  - `test_notifications_pagination_invalid_params_rejected`: Gửi `page=0`, `page=-1`, `limit=0`, `limit=101` đều nhận về mã lỗi HTTP 422.
  - `test_notification_response_never_leaks_private_fields`: Rà soát toàn bộ chuỗi JSON phản hồi, khẳng định không chứa các từ khóa cấm như `password_hash`, `access_token`, `refresh_token`, `private_evidence`, `client_secret`.

---

### 4.7. Schema Regression: `test_posts_schema.py`
**Đường dẫn:** `backend/tests/api/test_posts_schema.py`
**Đối tượng kiểm thử:** Bảo đảm tính ổn định hồi quy của schema Posts hoàn thiện trong KAN-32:
- Ràng buộc duy nhất `slug` danh mục (`uq_categories_slug`).
- Xóa danh mục thì bài viết tự động chuyển `category_id` thành `NULL` (`SET NULL`).
- Xóa bài viết thì các ảnh liên quan tự động bị xóa theo (`CASCADE`).
- Ràng buộc tọa độ GPS: Vĩ độ [-90, 90], Kinh độ [-180, 180], và cặp tọa độ phải cùng có hoặc cùng `NULL` (`ck_posts_coordinates`).
- Các trường chi tiết cho phép `NULL` (`brand`, `color`, `event_time`).

---

## 5. CẨM NANG THỰC THI & GỠ LỖI (DEBUGGING GUIDE)

### 5.1. Các lệnh chạy test thông dụng

```bash
# 1. Chạy toàn bộ 95 test cases (Khuyến nghị trước khi commit)
python -m pytest -v

# 2. Chạy riêng tầng Unit Tests (Siêu tốc, < 8s, không phụ thuộc DB)
python -m pytest tests/unit/ -v

# 3. Chạy riêng tầng Database Integration Tests
python -m pytest tests/integration/ -v

# 4. Chạy riêng tầng API Tests
python -m pytest tests/api/ -v

# 5. Chạy đích danh một test case cụ thể để debug
python -m pytest tests/integration/test_admin_audit_database.py::test_concurrent_row_lock_select_for_update_between_two_sessions -v -s
```

### 5.2. Các cạm bẫy kỹ thuật thường gặp và cách khắc phục

1. **Lỗi `MissingGreenlet: greenlet_spawn has not been called`:**
   - *Nguyên nhân:* Truy cập thuộc tính của một đối tượng SQLAlchemy (ví dụ `user.id` hoặc `post.title`) sau khi session đã `rollback()` hoặc `commit()`. Khi đó đối tượng đã bị expire và SQLAlchemy cố gắng lazy-load bất đồng bộ nhưng không nằm trong greenlet context.
   - *Khắc phục:* Luôn lưu giá trị scalar vào biến cục bộ trước khi phát sinh lỗi/rollback:
     ```python
     # Đúng chuẩn:
     user_id = test_user.id
     await session.rollback()
     stmt = select(Post).where(Post.user_id == user_id)
     ```

2. **Lỗi `InFailedSQLTransactionError: current transaction is aborted`:**
   - *Nguyên nhân:* Một câu lệnh trong session gặp lỗi (ví dụ vi phạm Unique Constraint hoặc Check Constraint) khiến PostgreSQL chuyển transaction sang trạng thái hỏng. Các lệnh tiếp theo trong cùng session đó sẽ bị từ chối.
   - *Khắc phục:* Luôn gọi `await session.rollback()` ngay sau khối `with pytest.raises(...)` để dọn sạch trạng thái trước khi thực hiện câu lệnh mới.

3. **Lỗi treo Runner khi test Concurrency Lock:**
   - *Nguyên nhân:* Hai coroutine cùng chờ khóa trên một session hoặc tranh chấp connection pool gây deadlock vô thời hạn.
   - *Khắc phục:* Luôn dùng hai session độc lập khởi tạo từ `TestingSessionLocal()`, sử dụng cờ `with_for_update(nowait=True)` và bọc trong `asyncio.wait_for(..., timeout=3.0)`.

---
**KẾT THÚC TÀI LIỆU HƯỚNG DẪN CODE WALKTHROUGH**
