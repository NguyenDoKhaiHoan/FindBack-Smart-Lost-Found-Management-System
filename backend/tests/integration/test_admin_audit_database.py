import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock
import uuid
import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError, IntegrityError, OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.identity.models.user import User
from app.modules.notifications_admin.models.audit_log import AuditLog
from app.modules.notifications_admin.models.notification import Notification
from app.modules.notifications_admin.repositories.audit_log_repository import AuditLogRepository
from app.modules.notifications_admin.repositories.notification_repository import NotificationRepository
from app.modules.notifications_admin.schemas.admin_post import PostModerationRequest
from app.modules.notifications_admin.services.notification_service import NotificationService
from app.modules.notifications_admin.services.post_moderation_service import PostModerationService
from app.modules.posts.models.post import Post
from app.modules.posts.repositories.post_repository import PostRepository
from tests.conftest import TestingSessionLocal


@pytest.mark.asyncio
async def test_audit_log_actor_fk_restrict_delete(
    db_session: AsyncSession,
    test_admin_user: User,
):
    """
    Verifies that deleting an Admin user who has generated audit logs is RESTRICTED
    at the database level (fk_audit_logs_actor ON DELETE RESTRICT).
    """
    admin_id = test_admin_user.id
    audit = AuditLog(
        id=uuid.uuid4(),
        actor_id=admin_id,
        action="HIDE",
        target_type="POST",
        target_id=uuid.uuid4(),
        reason="Vi phạm quy tắc cộng đồng",
        old_status="ACTIVE",
        new_status="HIDDEN",
    )
    db_session.add(audit)
    await db_session.commit()

    # Attempting to delete the admin user must fail with IntegrityError
    await db_session.delete(test_admin_user)
    with pytest.raises(IntegrityError):
        await db_session.flush()

    await db_session.rollback()


@pytest.mark.asyncio
async def test_post_moderated_by_fk_restrict_delete(
    db_session: AsyncSession,
    test_admin_user: User,
    test_user_a: User,
):
    """
    Verifies that deleting an Admin user who moderated a post is RESTRICTED
    at the database level (fk_posts_moderated_by ON DELETE RESTRICT) to preserve audit history.
    """
    admin_id = test_admin_user.id
    user_id = test_user_a.id
    now = datetime.now(timezone.utc)
    post = Post(
        id=uuid.uuid4(),
        user_id=user_id,
        title="Bài viết đã được kiểm duyệt",
        description="Mô tả bài viết",
        type="LOST",
        status="HIDDEN",
        moderated_by=admin_id,
        moderated_at=now,
        moderation_reason="Nội dung spam",
    )
    db_session.add(post)
    await db_session.commit()

    # Attempting to delete the moderating admin user must fail with IntegrityError
    await db_session.delete(test_admin_user)
    with pytest.raises(IntegrityError):
        await db_session.flush()

    await db_session.rollback()


@pytest.mark.asyncio
async def test_post_moderation_check_constraint_integrity(
    db_session: AsyncSession,
    test_admin_user: User,
    test_user_a: User,
):
    """
    Verifies check constraint ck_posts_moderation:
    - Allows all moderation fields to be NULL.
    - Allows all moderation fields to be NOT NULL with non-empty reason.
    - Rejects partial nulls or empty reasons with IntegrityError.
    """
    admin_id = test_admin_user.id
    user_id = test_user_a.id
    now = datetime.now(timezone.utc)

    # 1. Partial null: moderated_by & reason provided, but moderated_at is NULL
    invalid_post1 = Post(
        id=uuid.uuid4(),
        user_id=user_id,
        title="Bài viết vi phạm 1",
        description="Mô tả",
        type="LOST",
        status="HIDDEN",
        moderated_by=admin_id,
        moderated_at=None,
        moderation_reason="Lý do hợp lệ nhưng thiếu thời gian",
    )
    db_session.add(invalid_post1)
    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()

    # 2. Partial null: reason & moderated_at provided, but moderated_by is NULL
    invalid_post2 = Post(
        id=uuid.uuid4(),
        user_id=user_id,
        title="Bài viết vi phạm 2",
        description="Mô tả",
        type="LOST",
        status="HIDDEN",
        moderated_by=None,
        moderated_at=now,
        moderation_reason="Lý do không có admin",
    )
    db_session.add(invalid_post2)
    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()

    # 3. Empty whitespace reason with moderated_by and moderated_at provided
    invalid_post3 = Post(
        id=uuid.uuid4(),
        user_id=user_id,
        title="Bài viết vi phạm 3",
        description="Mô tả",
        type="LOST",
        status="HIDDEN",
        moderated_by=admin_id,
        moderated_at=now,
        moderation_reason="     ",
    )
    db_session.add(invalid_post3)
    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()

    # 4. Valid all-NULL moderation fields (unmoderated post)
    valid_unmoderated_post = Post(
        id=uuid.uuid4(),
        user_id=user_id,
        title="Bài viết chưa kiểm duyệt",
        description="Mô tả",
        type="LOST",
        status="ACTIVE",
        moderated_by=None,
        moderated_at=None,
        moderation_reason=None,
    )
    db_session.add(valid_unmoderated_post)
    await db_session.commit()
    assert valid_unmoderated_post.id is not None

    # 5. Valid fully-populated moderation fields
    valid_moderated_post = Post(
        id=uuid.uuid4(),
        user_id=user_id,
        title="Bài viết đã kiểm duyệt hợp lệ",
        description="Mô tả",
        type="LOST",
        status="HIDDEN",
        moderated_by=admin_id,
        moderated_at=now,
        moderation_reason="Lý do hợp lệ rõ ràng",
    )
    db_session.add(valid_moderated_post)
    await db_session.commit()
    assert valid_moderated_post.id is not None


@pytest.mark.asyncio
async def test_audit_log_jsonb_metadata_storage(
    db_session: AsyncSession,
    test_admin_user: User,
):
    """
    Verifies that audit log JSONB metadata preserves complex structures,
    numbers, lists, and Vietnamese Unicode characters.
    """
    admin_id = test_admin_user.id
    metadata_content = {
        "action": "HIDE",
        "post_title": "Tìm thấy căn cước công dân tại bến xe Mỹ Đình",
        "admin_ip": "192.168.1.100",
        "details": {
            "severity": "HIGH",
            "flags": ["PII", "ID_CARD"],
            "attempt_count": 1,
        },
    }

    audit = AuditLog(
        id=uuid.uuid4(),
        actor_id=admin_id,
        action="HIDE",
        target_type="POST",
        target_id=uuid.uuid4(),
        reason="Bảo vệ thông tin cá nhân (PII)",
        old_status="ACTIVE",
        new_status="HIDDEN",
        metadata_json=metadata_content,
    )
    db_session.add(audit)
    await db_session.commit()

    async with TestingSessionLocal() as session:
        stmt = select(AuditLog).where(AuditLog.id == audit.id)
        res = await session.execute(stmt)
        retrieved = res.scalars().first()
        assert retrieved is not None
        assert retrieved.metadata_json == metadata_content
        assert retrieved.metadata_json["details"]["severity"] == "HIGH"
        assert retrieved.metadata_json["details"]["flags"] == ["PII", "ID_CARD"]


@pytest.mark.asyncio
async def test_audit_log_index_target_type_id_created(
    db_session: AsyncSession,
):
    """
    Verifies that the composite index ix_audit_logs_target
    (target_type, target_id, created_at DESC) exists in PostgreSQL.
    """
    stmt = text(
        """
        SELECT indexname, indexdef
        FROM pg_indexes
        WHERE tablename = 'audit_logs' AND indexname = 'ix_audit_logs_target';
        """
    )
    res = await db_session.execute(stmt)
    row = res.first()
    assert row is not None, "Index ix_audit_logs_target not found in PostgreSQL!"
    indexdef = row[1].lower()
    assert "target_type" in indexdef
    assert "target_id" in indexdef
    assert "created_at desc" in indexdef


@pytest.mark.asyncio
async def test_admin_post_moderation_service_atomicity_on_failure(
    db_session: AsyncSession,
    test_admin_user: User,
    test_user_a: User,
):
    """
    Verifies service-level ACID transaction atomicity against PostgreSQL:
    If NotificationService raises an unhandled exception during moderate_post,
    the post remains ACTIVE and NO audit log or notification entries are committed.
    """
    admin_id = test_admin_user.id
    user_id = test_user_a.id

    post = Post(
        id=uuid.uuid4(),
        user_id=user_id,
        title="Bài viết kiểm thử tính nguyên tử thực tế",
        description="Nội dung",
        type="LOST",
        status="ACTIVE",
    )
    db_session.add(post)
    await db_session.commit()
    post_id = post.id

    # Create mock NotificationService that simulates failure
    failing_notify_service = NotificationService()
    failing_notify_service.create_notification = AsyncMock(
        side_effect=RuntimeError("Simulated external notification service crash")
    )

    service = PostModerationService(
        post_repository=PostRepository(),
        audit_log_repository=AuditLogRepository(),
        notification_service=failing_notify_service,
    )

    req = PostModerationRequest(
        action="HIDE",
        reason="Vi phạm quy định giao dịch nguyên tử",
    )

    with pytest.raises(RuntimeError) as exc_info:
        await service.moderate_post(
            session=db_session,
            post_id=post_id,
            admin_user=test_admin_user,
            request=req,
        )

    assert "Simulated external notification service crash" in str(exc_info.value)

    # In a clean, isolated session, verify database state
    async with TestingSessionLocal() as session:
        # 1. Post MUST remain ACTIVE
        post_stmt = select(Post).where(Post.id == post_id)
        post_res = await session.execute(post_stmt)
        persisted_post = post_res.scalars().first()
        assert persisted_post is not None
        assert persisted_post.status == "ACTIVE"
        assert persisted_post.moderated_by is None
        assert persisted_post.moderated_at is None
        assert persisted_post.moderation_reason is None

        # 2. Audit log MUST NOT exist
        audit_stmt = select(AuditLog).where(AuditLog.target_id == post_id)
        audit_res = await session.execute(audit_stmt)
        assert audit_res.scalars().first() is None

        # 3. Notification MUST NOT exist
        notif_stmt = select(Notification).where(Notification.resource_id == post_id)
        notif_res = await session.execute(notif_stmt)
        assert notif_res.scalars().first() is None


@pytest.mark.asyncio
async def test_concurrent_row_lock_select_for_update_between_two_sessions(
    test_user_a: User,
):
    """
    Verifies PostgreSQL row-level locking behavior (SELECT ... FOR UPDATE)
    between two independent AsyncSessions with timeout protection against deadlocks.
    """
    user_id = test_user_a.id
    # Create target post
    post_id = uuid.uuid4()
    async with TestingSessionLocal() as init_session:
        post = Post(
            id=post_id,
            user_id=user_id,
            title="Bài viết kiểm tra khóa dòng đồng thời",
            description="Nội dung",
            type="LOST",
            status="ACTIVE",
        )
        init_session.add(post)
        await init_session.commit()

    # Session 1: Acquire row lock on target post
    session1 = TestingSessionLocal()
    session2 = TestingSessionLocal()

    try:
        # Session 1 locks the row
        stmt1 = select(Post).where(Post.id == post_id).with_for_update()
        res1 = await session1.execute(stmt1)
        locked_post1 = res1.scalars().first()
        assert locked_post1 is not None

        # Session 2 attempts to acquire lock on the SAME row with nowait=True
        # With nowait=True, PostgreSQL immediately raises OperationalError (code 55P03: lock_not_available)
        stmt2 = select(Post).where(Post.id == post_id).with_for_update(nowait=True)

        async def attempt_session2_lock():
            return await session2.execute(stmt2)

        # Timeout protection ensures test runner never hangs
        with pytest.raises((OperationalError, DBAPIError)):
            await asyncio.wait_for(attempt_session2_lock(), timeout=3.0)

        # Reset session2's aborted transaction state
        await session2.rollback()

        # When Session 1 rolls back, the row lock is released
        await session1.rollback()

        # Session 2 now succeeds acquiring the row lock
        res2 = await asyncio.wait_for(session2.execute(stmt2), timeout=3.0)
        locked_post2 = res2.scalars().first()
        assert locked_post2 is not None
        assert locked_post2.id == post_id

        await session2.rollback()

    finally:
        await session1.close()
        await session2.close()
