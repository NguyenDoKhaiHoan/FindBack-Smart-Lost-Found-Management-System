from datetime import datetime, timezone
import math
from unittest.mock import AsyncMock, MagicMock
import uuid
import pytest
from pydantic import ValidationError as PydanticValidationError

from app.modules.identity.models.user import User
from app.modules.notifications_admin.schemas.admin_post import PostModerationRequest
from app.modules.notifications_admin.services.post_moderation_service import PostModerationService
from app.modules.posts.models.post import Post
from app.shared.errors import BadRequestError, NotFoundError, ValidationError


@pytest.mark.asyncio
async def test_list_posts_invalid_status_raises_validation_error():
    """list_posts must raise ValidationError when an unsupported status is provided."""
    service = PostModerationService(
        post_repository=MagicMock(),
        audit_log_repository=MagicMock(),
        notification_service=MagicMock(),
    )
    mock_session = AsyncMock()

    with pytest.raises(ValidationError) as exc_info:
        await service.list_posts(session=mock_session, status="INVALID_STATUS")

    assert "Trạng thái 'INVALID_STATUS' không hợp lệ" in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_list_posts_invalid_type_raises_validation_error():
    """list_posts must raise ValidationError when an unsupported post type is provided."""
    service = PostModerationService(
        post_repository=MagicMock(),
        audit_log_repository=MagicMock(),
        notification_service=MagicMock(),
    )
    mock_session = AsyncMock()

    with pytest.raises(ValidationError) as exc_info:
        await service.list_posts(session=mock_session, type_="UNKNOWN_TYPE")

    assert "Loại bài đăng 'UNKNOWN_TYPE' không hợp lệ" in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_list_posts_pagination_math_calculation():
    """list_posts must correctly compute total_pages for 0 items, exact multiples, and partial pages."""
    mock_repo = MagicMock()
    service = PostModerationService(
        post_repository=mock_repo,
        audit_log_repository=MagicMock(),
        notification_service=MagicMock(),
    )
    mock_session = AsyncMock()

    # Case 1: total = 0 -> total_pages = 0
    mock_repo.list_admin_posts = AsyncMock(return_value=([], 0))
    res0 = await service.list_posts(session=mock_session, page=1, limit=20)
    assert res0.pagination.total == 0
    assert res0.pagination.total_pages == 0

    # Case 2: total = 45, limit = 20 -> total_pages = 3
    mock_repo.list_admin_posts = AsyncMock(return_value=([], 45))
    res45 = await service.list_posts(session=mock_session, page=1, limit=20)
    assert res45.pagination.total == 45
    assert res45.pagination.total_pages == 3

    # Case 3: total = 40, limit = 20 -> total_pages = 2 (exact multiple)
    mock_repo.list_admin_posts = AsyncMock(return_value=([], 40))
    res40 = await service.list_posts(session=mock_session, page=1, limit=20)
    assert res40.pagination.total == 40
    assert res40.pagination.total_pages == 2

    # Case 4: total = 1, limit = 20 -> total_pages = 1
    mock_repo.list_admin_posts = AsyncMock(return_value=([], 1))
    res1 = await service.list_posts(session=mock_session, page=1, limit=20)
    assert res1.pagination.total == 1
    assert res1.pagination.total_pages == 1


@pytest.mark.asyncio
async def test_moderate_post_unsupported_action_raises_bad_request():
    """moderate_post must reject any action other than HIDE with BadRequestError."""
    service = PostModerationService(
        post_repository=MagicMock(),
        audit_log_repository=MagicMock(),
        notification_service=MagicMock(),
    )
    mock_session = AsyncMock()
    admin_user = User(id=uuid.uuid4(), role="ADMIN")
    req = PostModerationRequest(action="DELETE", reason="Spam")

    with pytest.raises(BadRequestError) as exc_info:
        await service.moderate_post(
            session=mock_session,
            post_id=uuid.uuid4(),
            admin_user=admin_user,
            request=req,
        )

    assert "không được hỗ trợ" in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_moderate_post_empty_reason_raises_validation_error():
    """moderate_post must reject an empty or whitespace-only reason with ValidationError."""
    service = PostModerationService(
        post_repository=MagicMock(),
        audit_log_repository=MagicMock(),
        notification_service=MagicMock(),
    )
    mock_session = AsyncMock()
    admin_user = User(id=uuid.uuid4(), role="ADMIN")

    # 1. Verify schema level rejection
    with pytest.raises(PydanticValidationError) as pydantic_err:
        PostModerationRequest(action="HIDE", reason="   \t  ")
    assert "Lý do kiểm duyệt không được để trống" in str(pydantic_err.value)

    # 2. Verify service level defense-in-depth using model_construct
    req_unvalidated = PostModerationRequest.model_construct(action="HIDE", reason="   \t  ")
    with pytest.raises(ValidationError) as exc_info:
        await service.moderate_post(
            session=mock_session,
            post_id=uuid.uuid4(),
            admin_user=admin_user,
            request=req_unvalidated,
        )

    assert "Lý do kiểm duyệt không được để trống" in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_moderate_post_nonexistent_post_raises_not_found():
    """moderate_post must raise NotFoundError (404) if the target post does not exist."""
    mock_repo = MagicMock()
    mock_repo.get_by_id = AsyncMock(return_value=None)
    service = PostModerationService(
        post_repository=mock_repo,
        audit_log_repository=MagicMock(),
        notification_service=MagicMock(),
    )
    mock_session = AsyncMock()
    admin_user = User(id=uuid.uuid4(), role="ADMIN")
    post_id = uuid.uuid4()
    req = PostModerationRequest(action="HIDE", reason="Spam")

    with pytest.raises(NotFoundError) as exc_info:
        await service.moderate_post(
            session=mock_session,
            post_id=post_id,
            admin_user=admin_user,
            request=req,
        )

    assert "Bài đăng không tồn tại" in str(exc_info.value.detail)
    mock_repo.get_by_id.assert_awaited_once_with(mock_session, post_id, for_update=True)


@pytest.mark.asyncio
async def test_moderate_post_closed_post_raises_bad_request():
    """moderate_post must reject moderating a CLOSED post with BadRequestError (400)."""
    closed_post = Post(
        id=uuid.uuid4(),
        status="CLOSED",
        title="Đã tìm thấy chìa khóa",
    )
    mock_repo = MagicMock()
    mock_repo.get_by_id = AsyncMock(return_value=closed_post)
    service = PostModerationService(
        post_repository=mock_repo,
        audit_log_repository=MagicMock(),
        notification_service=MagicMock(),
    )
    mock_session = AsyncMock()
    admin_user = User(id=uuid.uuid4(), role="ADMIN")
    req = PostModerationRequest(action="HIDE", reason="Chứa thông tin nhạy cảm")

    with pytest.raises(BadRequestError) as exc_info:
        await service.moderate_post(
            session=mock_session,
            post_id=closed_post.id,
            admin_user=admin_user,
            request=req,
        )

    assert "Không thể kiểm duyệt bài đăng đã đóng" in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_moderate_post_already_hidden_is_idempotent():
    """moderate_post must be idempotent: if already HIDDEN, preserves initial moderation data without duplicate logs or notifications."""
    existing_admin_id = uuid.uuid4()
    initial_moderated_at = datetime(2026, 11, 15, 10, 0, 0, tzinfo=timezone.utc)
    initial_reason = "Lý do ban đầu vi phạm quy tắc"

    hidden_post = Post(
        id=uuid.uuid4(),
        status="HIDDEN",
        title="Bài viết đã bị ẩn từ trước",
        moderated_by=existing_admin_id,
        moderated_at=initial_moderated_at,
        moderation_reason=initial_reason,
    )

    mock_repo = MagicMock()
    mock_repo.get_by_id = AsyncMock(return_value=hidden_post)
    mock_audit_repo = MagicMock()
    mock_audit_repo.create = AsyncMock()
    mock_notify_service = MagicMock()
    mock_notify_service.create_notification = AsyncMock()
    mock_session = AsyncMock()

    service = PostModerationService(
        post_repository=mock_repo,
        audit_log_repository=mock_audit_repo,
        notification_service=mock_notify_service,
    )

    second_admin = User(id=uuid.uuid4(), role="ADMIN")
    req = PostModerationRequest(action="HIDE", reason="Lý do mới không được ghi đè")

    res = await service.moderate_post(
        session=mock_session,
        post_id=hidden_post.id,
        admin_user=second_admin,
        request=req,
    )

    # Asserts initial moderation metadata is preserved
    assert res.id == hidden_post.id
    assert res.status == "HIDDEN"
    assert res.moderated_by == existing_admin_id
    assert res.moderated_at == initial_moderated_at
    assert res.moderation_reason == initial_reason

    # Audit log and notification must NOT be created again
    mock_audit_repo.create.assert_not_called()
    mock_notify_service.create_notification.assert_not_called()
    mock_session.commit.assert_not_called()


@pytest.mark.asyncio
async def test_moderate_post_success_flow():
    """moderate_post must update status to HIDDEN, create audit log, and notify owner with auto_commit=False and deterministic UUID5."""
    post_owner_id = uuid.uuid4()
    active_post = Post(
        id=uuid.uuid4(),
        user_id=post_owner_id,
        status="ACTIVE",
        title="Ví tiền bị rơi tại công viên",
    )

    mock_repo = MagicMock()
    mock_repo.get_by_id = AsyncMock(return_value=active_post)
    mock_audit_repo = MagicMock()
    mock_audit_repo.create = AsyncMock()
    mock_notify_service = MagicMock()
    mock_notify_service.create_notification = AsyncMock()

    mock_session = AsyncMock()

    service = PostModerationService(
        post_repository=mock_repo,
        audit_log_repository=mock_audit_repo,
        notification_service=mock_notify_service,
    )

    admin_user = User(id=uuid.uuid4(), role="ADMIN")
    reason = "Bài viết chứa nội dung quảng cáo trái phép"
    req = PostModerationRequest(action="HIDE", reason=reason)

    res = await service.moderate_post(
        session=mock_session,
        post_id=active_post.id,
        admin_user=admin_user,
        request=req,
    )

    # 1. State updated
    assert res.status == "HIDDEN"
    assert active_post.status == "HIDDEN"
    assert active_post.moderated_by == admin_user.id
    assert active_post.moderation_reason == reason
    assert active_post.moderated_at is not None

    # 2. Audit log recorded with correct arguments
    mock_audit_repo.create.assert_awaited_once()
    audit_call_kwargs = mock_audit_repo.create.call_args.kwargs
    assert audit_call_kwargs["actor_id"] == admin_user.id
    assert audit_call_kwargs["action"] == "HIDE"
    assert audit_call_kwargs["target_type"] == "POST"
    assert audit_call_kwargs["target_id"] == active_post.id
    assert audit_call_kwargs["old_status"] == "ACTIVE"
    assert audit_call_kwargs["new_status"] == "HIDDEN"
    assert audit_call_kwargs["reason"] == reason

    # 3. Notification emitted with auto_commit=False and deterministic UUIDv5 event_id
    mock_notify_service.create_notification.assert_awaited_once()
    notify_call_kwargs = mock_notify_service.create_notification.call_args.kwargs
    assert notify_call_kwargs["auto_commit"] is False

    notification_data = notify_call_kwargs["data"]
    assert notification_data.recipient_id == post_owner_id
    assert notification_data.event_type == "POST_HIDDEN"
    assert notification_data.resource_type == "POST"
    assert notification_data.resource_id == active_post.id

    expected_event_id = uuid.uuid5(uuid.NAMESPACE_OID, f"POST_HIDDEN:{active_post.id}")
    assert notification_data.event_id == expected_event_id

    # 4. Atomic transaction commit
    mock_session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_moderate_post_exception_triggers_session_rollback():
    """moderate_post must roll back the transaction if notification or audit log emission fails."""
    active_post = Post(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        status="ACTIVE",
        title="Bài viết gặp sự cố khi duyệt",
    )

    mock_repo = MagicMock()
    mock_repo.get_by_id = AsyncMock(return_value=active_post)
    mock_audit_repo = MagicMock()
    mock_audit_repo.create = AsyncMock()

    # Simulate unexpected failure during notification creation
    mock_notify_service = MagicMock()
    mock_notify_service.create_notification = AsyncMock(
        side_effect=RuntimeError("Simulated notification service failure")
    )

    mock_session = AsyncMock()

    service = PostModerationService(
        post_repository=mock_repo,
        audit_log_repository=mock_audit_repo,
        notification_service=mock_notify_service,
    )

    admin_user = User(id=uuid.uuid4(), role="ADMIN")
    req = PostModerationRequest(action="HIDE", reason="Vi phạm điều khoản")

    with pytest.raises(RuntimeError) as exc_info:
        await service.moderate_post(
            session=mock_session,
            post_id=active_post.id,
            admin_user=admin_user,
            request=req,
        )

    assert "Simulated notification service failure" in str(exc_info.value)
    # Session rollback must be called
    mock_session.rollback.assert_awaited_once()
    # Commit must NOT be called
    mock_session.commit.assert_not_called()
