# API contract Claims và xác minh sở hữu

Đây là đầu ra thiết kế, chưa phải API đang chạy hoặc quyết định đã được các nhóm phê duyệt.

## 1. Cơ sở và phạm vi

Phạm vi bàn giao gồm đúng sáu endpoint:

| Method | URL | Thành công | Quyền |
| --- | --- | --- | --- |
| POST | `/api/v1/claims` | 201 `ClaimSummary` | User đang hoạt động, claim tin FOUND của người khác |
| GET | `/api/v1/claims/me` | 200 `ClaimPage` | Danh sách có quan hệ với user hiện tại |
| GET | `/api/v1/claims/{id}` | 200 `ClaimDetail` | Người yêu cầu hoặc chủ tin FOUND tương ứng |
| PATCH | `/api/v1/claims/{id}/approve` | 200 `ClaimSummary` | Chủ tin FOUND, khác người yêu cầu |
| PATCH | `/api/v1/claims/{id}/reject` | 200 `ClaimSummary` | Chủ tin FOUND, khác người yêu cầu |
| PATCH | `/api/v1/claims/{id}/complete` | 200 `ClaimSummary` | Chính người yêu cầu xác nhận đã nhận đồ |

Ba quyết định chuẩn hóa API: dùng prefix `/api/v1`; tách `decision` thành `approve`/`reject`;
`complete` là xác nhận nhận đồ, không gộp việc duyệt, lập lịch và giao đồ.
Không còn coi bảy endpoint sơ bộ của TV4 là contract hiện hành cho sáu thao tác này.
Luồng tạo Return/ghi nhận giao và upload file là phụ thuộc ngoài sáu endpoint, chưa được đặc tả ở đây.

## 2. Danh tính và ma trận quyền

Tất cả endpoint yêu cầu `Authorization: Bearer <access_token>`. Identity kiểm tra chữ ký,
hạn dùng, thu hồi token và user còn hoạt động. Thiếu/token sai/hết hạn: 401;
token hợp lệ nhưng tài khoản bị khóa hoặc thiếu quyền: 403. 401 có header
`WWW-Authenticate: Bearer`. Actor chỉ lấy từ danh tính server, không nhận từ body/query.

Trong MVP, **người xem xét/trao trả = chủ hiện tại của FOUND post** (`post.owner_id`).
Điều phối viên, nhân viên địa điểm hoặc admin không có quyền thay thế chỉ nhờ tên vai trò.
Nếu bổ sung ủy quyền, Identity/Posts phải có quan hệ phân công theo post và audit, rồi sửa contract.
Không cho đổi chủ tin khi có claim PENDING/APPROVED hoặc Return chưa kết thúc trước khi có chính sách chuyển giao.

| Hành động | Người yêu cầu claim | Chủ FOUND post | User khác / claimant cạnh tranh | Admin chỉ có role quản trị | Chưa đăng nhập |
| --- | --- | --- | --- | --- | --- |
| Tạo claim | Có, nếu tin của người khác | Không tự claim tin mình | Có nếu đủ điều kiện tạo | Như user thường | 401 |
| Liệt kê `/me?relation=claimant` | Chỉ claim của mình | Chỉ claim bản thân đã gửi ở tin khác | Chỉ dữ liệu của mình | Như user thường | 401 |
| Liệt kê `/me?relation=reviewer` | Không xem claim khác nếu không là chủ tin | Các claim trên tin mình | Không | Không mặc định | 401 |
| Xem chi tiết/bằng chứng | Claim của mình | Các claim trên tin mình | 404 | 404 nếu không có quan hệ | 401 |
| Approve/reject | 403 trên claim mình | Có nếu khác claimant | 404 | 404 nếu không có quan hệ | 401 |
| Complete | Có, sau HANDED_OVER | 403, không xác nhận thay người nhận | 404 | 404 nếu không có quan hệ | 401 |
| Lập lịch/ghi nhận giao (ngoài sáu API) | Không | Dự kiến người đã duyệt `decided_by` | Không | Không mặc định | 401 |

Nếu tài khoản admin đồng thời là một bên hợp lệ thì áp dụng quyền theo quan hệ đó.
Tuyệt đối không tự phê duyệt: `actor_id != claimant_id` **và** `actor_id == post.owner_id`.
Chỉ kiểm tra khác claimant là chưa đủ. Khi dữ liệu cũ khiến owner = claimant, chặn cả approve/reject.

Che giấu sự tồn tại: claim không tồn tại hoặc người gọi không có quan hệ đọc đều trả cùng 404
`CLAIM_NOT_FOUND`, cùng cấu trúc lỗi. Người có quyền đọc nhưng gọi sai vai trò thao tác nhận 403.
Kiểm tra quyền trước khi trả trạng thái/version/lý do từ chối. `/me` lọc quyền ở truy vấn DB
trước phân trang, không lọc ở frontend. Đăng ký `/claims/me` trước `/claims/{id}`.

## 3. Schema và quy ước chung

- UUID cho mọi ID; timestamp RFC 3339 UTC do server tạo. Đây là lựa chọn contract cần Identity/Posts thống nhất.
- JSON body có `additionalProperties: false`; trường lạ (ví dụ `claimant_id`, `decided_by`,
  `returned_by`, `status`, `file_path`, `role`) trả 422, không bị lặng lẽ bỏ qua.
- Chuỗi người dùng được trim rồi kiểm tra độ dài, không cho nội dung chỉ có khoảng trắng.
  Giới hạn dưới đây tính theo ký tự. Hiển thị như văn bản, escape khi render.
- `version` là số nguyên >= 1, bắt đầu 1. Mọi thay đổi claim/bằng chứng/Return có thể ảnh hưởng
  quyết định phải tăng version của claim trong cùng transaction, kể cả các API Return tương lai.
  Thêm cột version là thay đổi persistence cần migration; tài liệu DB hiện chưa có cột này.
- Tất cả response, kể cả lỗi: `Cache-Control: no-store`. Không có endpoint công khai cho Claims.
- Không có idempotency key trong phiên bản này. POST lặp khi claim đang mở trả 409.
  PATCH lặp khi đã chuyển trạng thái cũng trả 409; client GET lại trước khi quyết định retry.

| Schema | Nội dung |
| --- | --- |
| `CreateClaimRequest` | `found_post_id: uuid`, `evidence_description: string[10..5000]`, đều bắt buộc |
| `ApproveClaimRequest` | `expected_version: integer >= 1`, bắt buộc |
| `RejectClaimRequest` | `expected_version`, `reason: string[1..1000]`, đều bắt buộc |
| `CompleteClaimRequest` | `expected_version`, `receipt_confirmed: true`, đều bắt buộc; false bị 422 |
| `ClaimSummary` | `id`, `found_post_id`, `claimant_id`, `status`, `version`, `created_at`, `updated_at`, `decided_by`, `decided_at`, `rejection_reason`, `returned_by`, `returned_at`, `return_summary`; tất cả trường có mặt, metadata chưa phát sinh là null |
| `ClaimDetail` | Mọi trường của summary cộng `evidence: Evidence[]` |
| `Evidence` | `id`, `private_content`, `created_at`; không chứa storage path, URL file hoặc thông tin của claim khác |
| `ReturnSummary` | `id`, `status: ARRANGED/HANDED_OVER/CONFIRMED`, `handed_over_at: timestamp/null`, `confirmed_at: timestamp/null` |
| `ClaimPage` | `items: ClaimSummary[]`, `page`, `page_size`, `has_next`; không có bằng chứng |
| `ApiError` | `error: {code, message, request_id, details: [{field, issue}]}`; không trả SQL/stacktrace/bằng chứng |

Metadata theo trạng thái:

| Claim status | Quyết định | Hoàn tất | Return |
| --- | --- | --- | --- |
| PENDING | decided_by/at, rejection_reason null | returned_by/at null | null |
| APPROVED | decided_by/at có giá trị, reason null | returned_by/at null | null, ARRANGED hoặc HANDED_OVER |
| REJECTED | decided_by/at và reason có giá trị | returned_by/at null | null |
| RETURNED | giữ nguyên metadata APPROVED | returned_by = claimant_id; returned_at = confirmed_at | bắt buộc CONFIRMED |

Các ràng buộc chéo trạng thái này phải được service/DB kiểm tra; schema kiểm tra kiểu dữ liệu.
MVP chưa trả CANCELLED; không ánh xạ dữ liệu CANCELLED cũ sang REJECTED một cách tự động.

## 4. Contract từng endpoint

### POST /api/v1/claims

Request `CreateClaimRequest`. Post phải tồn tại, có thể được actor truy cập, loại FOUND,
đang nhận claim, chưa có claim APPROVED/RETURNED. Owner phải khác actor.
Tên trạng thái Post cụ thể chờ Posts; dùng predicate tích hợp `can_accept_claims(post)`.
LOST trả 422; post không tồn tại/đã xóa mềm/bị ẩn với actor trả 404;
tin tồn tại có thể xem nhưng đóng/ngừng nhận claim trả 409.

Trong một transaction: tạo Claim PENDING, version=1; claimant_id từ token;
tạo Evidence.private_content từ evidence_description; audit và outbox.
Không cho tạo claim rỗng bằng chứng. Thành công 201 `ClaimSummary`, header
`Location: /api/v1/claims/{id}`. Summary không lặp lại bằng chứng trong response.

Claim trùng: cùng `(found_post_id, claimant_id)` có PENDING hoặc APPROVED trả 409
`DUPLICATE_ACTIVE_CLAIM`. Cho gửi mới sau REJECTED (ID mới, bằng chứng mới, giữ lịch sử),
chỉ khi post còn nhận claim và không có người thắng. RETURNED không cho tạo lại.
Một FOUND post được giả định là một đồ vật; chưa chống trùng giữa nhiều post cùng đồ vật.

Lỗi: 401 `UNAUTHENTICATED`; 403 `ACCOUNT_FORBIDDEN`/`SELF_CLAIM_FORBIDDEN`;
404 `POST_NOT_FOUND`; 409 `DUPLICATE_ACTIVE_CLAIM`/`POST_NOT_CLAIMABLE`/`POST_ALREADY_ASSIGNED`;
422 `VALIDATION_ERROR`/`POST_TYPE_NOT_FOUND`.

### GET /api/v1/claims/me

Không có body. Query `relation=claimant|reviewer|all` mặc định `claimant`;
`status=PENDING|APPROVED|REJECTED|RETURNED` tùy chọn;
`page` mặc định 1, >=1; `page_size` mặc định 20, 1..100. Từ chối query không khai báo bằng 422.
`reviewer` lọc theo chủ FOUND post; `all` là hợp của hai quan hệ, loại trùng theo claim ID.
Không nhận `user_id`, không có chế độ admin xem tất cả. Sắp xếp cố định
`created_at DESC, id DESC`, phân trang sau lọc quyền và status. Page vượt cuối trả items rỗng,
has_next=false. Offset pagination không bảo đảm snapshot khi có claim mới; UI tải lại từ page=1.
Thành công 200 `ClaimPage`; không có bằng chứng hoặc file reference trong items.

Lỗi: 401 `UNAUTHENTICATED`; 403 `ACCOUNT_FORBIDDEN`; 422 `VALIDATION_ERROR`.

### GET /api/v1/claims/{id}

`id` UUID, không body/query. 200 `ClaimDetail`, chỉ trả evidence sau khi kiểm tra quyền
người yêu cầu hoặc owner của đúng post. Metadata không cho biết claim cạnh tranh khác.
Lỗi: 401 `UNAUTHENTICATED`; 403 `ACCOUNT_FORBIDDEN`; 404 `CLAIM_NOT_FOUND`;
422 `VALIDATION_ERROR` khi id sai định dạng hoặc query thừa.

### PATCH /api/v1/claims/{id}/approve

Request `ApproveClaimRequest`. Chỉ reviewer hợp lệ được chuyển PENDING → APPROVED.
Đọc và xem xét bằng chứng trước quyết định; matching không phải bằng chứng xác thực,
không được dùng để tự động phê duyệt. Claim phải có ít nhất một bằng chứng hợp lệ.
Ghi decided_by từ actor, decided_at từ server, giữ rejection_reason=null; tăng version.
Post phải chưa đóng, chưa có claim APPROVED/RETURNED khác. Không tạo Return hoặc đóng Post.
Các claim PENDING cạnh tranh được giữ nguyên để reviewer xử lý; không tự từ chối hàng loạt.
Thành công 200 `ClaimSummary`.

Lỗi: 401 `UNAUTHENTICATED`; 403 `ACCOUNT_FORBIDDEN`/`CLAIM_ACTION_FORBIDDEN`;
404 `CLAIM_NOT_FOUND`; 409 `CLAIM_STATE_CONFLICT`/`CLAIM_VERSION_CONFLICT`/
`POST_NOT_CLAIMABLE`/`POST_ALREADY_ASSIGNED`; 422 `VALIDATION_ERROR`/`EVIDENCE_REQUIRED`.

### PATCH /api/v1/claims/{id}/reject

Request `RejectClaimRequest`. Chỉ reviewer hợp lệ được chuyển PENDING → REJECTED.
Ghi decided_by/at, rejection_reason = reason đã trim và tăng version; không có Return.
Cho từ chối claim PENDING tồn đọng kể cả khi post đã đóng hoặc có người thắng;
không được sửa/xóa quyết định cũ. Lý do chỉ hai bên đọc được, tránh chép bí mật của claim khác.
Thành công 200 `ClaimSummary`.

Lỗi: 401 `UNAUTHENTICATED`; 403 `ACCOUNT_FORBIDDEN`/`CLAIM_ACTION_FORBIDDEN`;
404 `CLAIM_NOT_FOUND`; 409 `CLAIM_STATE_CONFLICT`/`CLAIM_VERSION_CONFLICT`;
422 `VALIDATION_ERROR` (bao gồm reason rỗng).

### PATCH /api/v1/claims/{id}/complete

Request `CompleteClaimRequest`. Chỉ claimant của chính claim, `receipt_confirmed=true`,
claim APPROVED và Return HANDED_OVER mới được xác nhận. Không nhận ID Return từ client;
tra Return bằng claim_id. Chủ tin/admin không xác nhận thay, kể cả đã duyệt claim.

Một transaction: Return → CONFIRMED với confirmed_by=actor, confirmed_at=server time;
Claim → RETURNED với returned_by=claimant_id, returned_at=confirmed_at; tăng version;
đóng FOUND post qua service Posts, audit, outbox. Lỗi ở bất kỳ bước nào rollback tất cả.
Không tự tạo ARRANGED/HANDED_OVER, không dựng lịch sử bàn giao giả. Post đã có cờ hoàn tất
nhất quán được giữ nguyên; bị xóa/ẩn quản trị hoặc trạng thái mâu thuẫn trả 409 `POST_STATE_CONFLICT`.
Thành công 200 `ClaimSummary`, return_summary.status=CONFIRMED.

Lỗi: 401 `UNAUTHENTICATED`; 403 `ACCOUNT_FORBIDDEN`/`CLAIM_ACTION_FORBIDDEN`;
404 `CLAIM_NOT_FOUND`; 409 `CLAIM_STATE_CONFLICT`/`CLAIM_VERSION_CONFLICT`/
`RETURN_NOT_READY`/`POST_STATE_CONFLICT`; 422 `VALIDATION_ERROR`.

## 5. Bằng chứng và xác minh sở hữu

Người yêu cầu cung cấp đặc điểm không công khai, mô tả đồ vật hoặc bằng chứng sở hữu.
Reviewer đối chiếu với đồ đang giữ; không tiết lộ đáp án bí mật để claimant đoán theo.
Chấp nhận claim là quyết định của reviewer có quyền, không phải kết luận tự động từ điểm matching.
Nếu không đủ căn cứ thì reject có lý do; tranh chấp thực tế cần luồng xử lý riêng.

Phiên bản sáu endpoint nhận **bằng chứng văn bản** cùng POST, không nhận upload hoặc đường dẫn.
`evidence_description` ánh xạ tới `claim_evidence.private_content` theo tài liệu DB.
Chỉ GET detail trả nội dung; list, summary mutation, Posts, search, matching, notifications và
application/access/error logs không chứa nội dung/đặc điểm bí mật hoặc rejection_reason.
Audit chỉ lưu actor, action, claim/post ID, version trước/sau và thời gian; log request không ghi body.

Bằng chứng đóng băng sau quyết định; sáu API chưa có chỉnh sửa/bổ sung evidence.
Nếu tích hợp endpoint evidence cũ, chỉ claimant khi PENDING được bổ sung, cùng khóa/version;
reviewer không sửa bằng chứng của người yêu cầu.
Không trả `file_path`, storage key hay public URL, kể cả file đã tồn tại từ dữ liệu cũ.
Upload/download cần contract riêng: private storage, kiểm tra quyền từng lần tải, kiểm tra MIME/
kích thước/nội dung, không nhận tùy ý URL hoặc đường dẫn filesystem từ client.
Không đưa file thật hoặc dữ liệu sở hữu vào ví dụ/seed trong Git.
Chính sách lưu trữ/xóa bằng chứng và quyền truy cập quản trị ngoại lệ cần các nhóm xác nhận riêng.

## 6. Lỗi, ưu tiên kiểm tra và cạnh tranh

Lỗi chung dùng ApiError; `details` có thể rỗng. `message` chỉ phục vụ hiển thị, client dựa vào code.
422 có field như `body.reason`, `path.id`, `query.page_size`; không lặp lại input nhạy cảm.
Không đưa ID người thắng, nội dung bằng chứng hoặc version hiện tại vào lỗi gửi người không có quyền.

| HTTP | Code | Ý nghĩa / xử lý client |
| --- | --- | --- |
| 401 | UNAUTHENTICATED | Đăng nhập hoặc làm mới token theo Identity |
| 403 | ACCOUNT_FORBIDDEN | User bị khóa/không được dùng tính năng |
| 403 | SELF_CLAIM_FORBIDDEN | Actor là owner tin muốn claim |
| 403 | CLAIM_ACTION_FORBIDDEN | Có quyền đọc nhưng sai vai trò; gồm tự duyệt claim |
| 404 | POST_NOT_FOUND / CLAIM_NOT_FOUND | Không tồn tại hoặc bị che theo quyền |
| 409 | DUPLICATE_ACTIVE_CLAIM | Đã có claim đang mở của cùng người trên cùng post; tải `/me` |
| 409 | POST_ALREADY_ASSIGNED | Post đã có claim APPROVED/RETURNED, không lộ claim thắng |
| 409 | POST_NOT_CLAIMABLE / POST_STATE_CONFLICT | Post không nhận claim hoặc không thể đóng nhất quán |
| 409 | CLAIM_STATE_CONFLICT | Thao tác sai trạng thái, kể cả PATCH lặp đã thành công |
| 409 | CLAIM_VERSION_CONFLICT | expected_version cũ; GET rồi yêu cầu user xem lại trước quyết định |
| 409 | RETURN_NOT_READY | Không có Return hoặc chưa HANDED_OVER; không retry mù |
| 422 | VALIDATION_ERROR | Body/query/path sai kiểu, thiếu, thừa, chuỗi rỗng hoặc quá dài |
| 422 | POST_TYPE_NOT_FOUND | Post có thể xem nhưng không phải FOUND |
| 422 | EVIDENCE_REQUIRED | Claim cũ thiếu bằng chứng, không thể duyệt |

Ưu tiên với input hợp lệ: xác thực → kiểm tra quyền đọc/che 404 → quyền thao tác →
kiểm tra trạng thái claim → expected_version → điều kiện nghiệp vụ còn lại.
POST sau kiểm tra quyền/tin FOUND: self-claim → trùng active → người thắng → trạng thái post.
Validation cú pháp có thể trả 422 sau auth trước khi đọc tài nguyên; lỗi schema không tiết lộ sự tồn tại.
Nếu vừa sai trạng thái vừa stale version thì trả CLAIM_STATE_CONFLICT.

Transaction thống nhất khóa **Post → Claim → Return**, kiểm tra lại quyền/trạng thái/version
sau khi khóa. Dùng version trong điều kiện UPDATE; không dựa vào kiểm tra ở UI.
Mọi đường ghi Posts/Returns/evidence phải tuân cùng giao thức khóa/version để không có cửa đi vòng.
Giữ unique constraint: (post, claimant) với PENDING/APPROVED; một người thắng APPROVED/RETURNED
trên mỗi post; tối đa một Return cho mỗi claim. Ánh xạ unique violation có tên sang 409 tương ứng;
không gom tất cả lỗi SQL thành 409. Lỗi DB không nhận diện là lỗi server đã làm sạch.

Hai approve trên cùng post: một thành công, bên kia sau khóa nhận 409 POST_ALREADY_ASSIGNED.
Approve và reject cùng claim: một thành công, bên còn lại 409 CLAIM_STATE_CONFLICT.
Hai complete: một thành công, bên kia 409 CLAIM_STATE_CONFLICT; chỉ một audit/outbox hoàn tất.
Evidence cập nhật trong khi reviewer xem: version tăng, approve dùng bản cũ trả 409 CLAIM_VERSION_CONFLICT.
Deadlock/serialization failure chỉ retry transaction có giới hạn ở server trước khi có tác dụng phụ;
không trả SQL thô hoặc giả thành lỗi nghiệp vụ.

Audit và outbox ghi cùng commit; lỗi ghi audit/outbox rollback mutation. Notifications tiêu thụ sau commit,
dedupe bằng event_id; sự cố gửi thông báo không đảo ngược giao dịch đã commit. Payload sự kiện chỉ
event_id, type, claim_id, found_post_id, recipient_id, version, occurred_at, không có evidence/lý do.
created gửi owner; approved/rejected gửi claimant; completed gửi owner. Người thao tác xem kết quả qua response.

## 7. RETURNED và mô hình Return: quyết định cần thống nhất

| Khía cạnh | Yêu cầu/tài liệu gốc | Nháp DB được mô tả trong repo | Đề xuất contract này |
| --- | --- | --- | --- |
| Claim status | PENDING, APPROVED, REJECTED, CANCELLED | PENDING, APPROVED, REJECTED, RETURNED | Dùng bốn trạng thái nháp; CANCELLED chưa hỗ trợ |
| Kết thúc trao trả | Return.ARRANGED → HANDED_OVER → CONFIRMED | CONFIRMED đồng bộ Claim.RETURNED | Giữ Return là nguồn lịch sử; RETURNED là kết quả tổng hợp |
| Complete | Danh sách cũ có `/returns/{id}/confirm` | claimant xác nhận sau HANDED_OVER | `/claims/{id}/complete` gọi cùng use case xác nhận theo claim_id |
| Ghi trực tiếp RETURNED | Không được quy định | Tài liệu nói trigger chặn nếu không có CONFIRMED | Không UPDATE đơn lẻ hoặc bỏ bước bàn giao |
| Actor giao/nhận | Chưa chốt rõ | arrange/hand-over = decided_by, confirm = claimant | Giữ đề xuất này, thêm kiểm tra owner hiện tại |
| Retry quyết định/confirm | Chưa chốt | Hàm nháp mô tả trả lại kết quả khi gọi lặp cùng payload | HTTP contract chọn 409 khi trạng thái đã đổi; service kiểm tra trước khi gọi hàm |
| Version | Chưa quy định | Chưa có trong schema được mô tả | Thêm version; mọi thao tác liên quan phải tăng |

Không diễn giải RETURNED như một Return mới hay trạng thái của Post.
Nếu nhóm muốn bỏ bảng Return và cho reviewer complete trực tiếp thì đó là thiết kế khác,
cần sửa state machine, quyền, migration và tiêu chí nghiệm thu trước triển khai.
Sáu endpoint hiện **chưa đủ để chạy end-to-end** nếu chưa có cách lập Return và ghi nhận HANDED_OVER.
Không tự thêm hai thao tác đó vào complete để che thiếu API.

## 8. Phối hợp và điều kiện triển khai

| Nhóm | Nội dung bàn giao/điểm cần xác nhận |
| --- | --- |
| Claims | State machine, quyền reviewer/claimant, tạo evidence nguyên tử, retry, policy gửi mới sau REJECTED |
| Cấu hình và tích hợp | UUID/schema/error envelope chung, prefix, migration version/FK/unique, transaction/session, chuyển draft SQL thành Alembic và kiểm chứng trigger thực tế |
| Identity | Actor từ JWT, tài khoản khóa, không tin actor/role do client gửi; admin không có quyền claim mặc định |
| Posts | owner_id, FOUND, mapping can_accept_claims/đóng/ẩn/xóa mềm; cấm chuyển owner khi claim mở; khóa Post trước các thao tác |
| Returns/Claims + tích hợp | Endpoint lập lịch và ghi HANDED_OVER; dùng cùng use case khi còn giữ confirm cũ; Claim version phải tăng khi Return đổi |
| Notifications | Schema sự kiện, outbox/dedupe, đúng recipient, không chuyển bằng chứng hoặc lý do qua thông báo |

Những mục cần xác nhận trước code: giữ Return và mapping RETURNED; không hỗ trợ CANCELLED ở sáu API;
MVP không ủy quyền admin/điều phối viên; text-only evidence; chính sách gửi lại REJECTED;
tên trạng thái Post và kiểu ID; bổ sung version; HTTP retry 409 khác hàm SQL nháp.
Đây là danh sách phối hợp trong repo, chưa gửi thông báo hoặc cập nhật issue bên ngoài.

## 9. Kịch bản nghiệm thu cho triển khai sau

1. Sáu route match OpenAPI, `/me` không bị parse thành UUID; success/error đúng schema, auth và no-store.
2. Tạo hợp lệ 201 + Location; actor server, evidence lưu cùng claim; lỗi evidence rollback cả claim.
3. Thiếu/sai token 401; user khóa 403; self-claim 403; LOST 422; post không thấy 404; post đóng 409.
4. POST đồng thời cùng người/post: đúng một 201, một 409; REJECTED cho tạo ID mới nếu post còn hợp lệ.
5. `/me` mỗi relation chỉ trả dữ liệu được phép, lọc trước phân trang; không lộ evidence; page rỗng hợp lệ.
6. Claimant và owner xem detail; người ngoài/admin không có quan hệ cùng 404; không lộ file_path trên mọi response/log.
7. Claimant tự approve/reject 403; user bất kỳ không thành reviewer chỉ vì khác claimant;
   owner chỉ được quyết định PENDING; reason trắng/thừa actor ID đều 422.
8. Hai approve cạnh tranh cùng post chỉ một người thắng; approve/reject cùng claim không ghi đè quyết định.
9. Stale version khi claim vẫn đúng trạng thái nhận 409; GET rồi xem lại; evidence/Return đổi cũng làm version thay đổi.
10. Owner complete 403; claimant complete khi thiếu Return/ARRANGED 409; false receipt_confirmed 422;
    HANDED_OVER hợp lệ → CONFIRMED/RETURNED/đóng Post cùng transaction và cùng mốc thời gian.
11. Complete lặp 409, không thêm Return/audit/event; lỗi đóng Post hoặc audit rollback toàn bộ.
12. Notifications chỉ phát sau commit, dedupe event, không chứa bằng chứng/lý do hoặc thông tin claim cạnh tranh.

OpenAPI và ví dụ có thể được kiểm tra tĩnh; các ca quyền, transaction và race ở trên cần backend,
migration và DB tích hợp thật, không được coi là đã pass nhờ có tài liệu.

Kiểm tra tĩnh khi bàn giao: OpenAPI 3.1 hợp lệ qua `openapi-spec-validator`; đủ sáu operation,
11 schema; 52 ví dụ request/response qua JSON Schema với kiểm tra UUID/timestamp;
15 ca dữ liệu không hợp lệ bị từ chối (gồm giả mạo actor, version sai, lý do trắng,
xác nhận false, status ngoài enum, bằng chứng lọt vào summary và error code sai endpoint).
Đã kiểm tra security, header cache/auth, liên kết nội bộ và `git diff --check`.
Có thể kiểm tra lại cấu trúc bằng `python -m openapi_spec_validator docs/api/claims.openapi.json`
sau khi cài `openapi-spec-validator` trong môi trường công cụ riêng.
