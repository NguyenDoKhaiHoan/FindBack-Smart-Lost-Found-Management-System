from datetime import datetime, timezone
import uuid
import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.identity.models.user import User
from app.modules.notifications_admin.models.notification import Notification
from app.modules.notifications_admin.repositories.notification_repository import NotificationRepository
from app.modules.notifications_admin.schemas.notification import NotificationCreateInternal
from app.modules.notifications_admin.services.notification_service import NotificationService
from tests.conftest import TestingSessionLocal


@pytest.mark.asyncio
async def test_notification_event_id_unique_constraint(
    db_session: AsyncSession,
    test_user_a: User,
):
    """
    Verifies that the database enforces UNIQUE constraint on event_id.
    Directly inserting two notifications with the same event_id must raise IntegrityError.
    """
    shared_event_id = uuid.uuid4()
    notif1 = Notification(
        id=uuid.uuid4(),
        recipient_id=test_user_a.id,
        event_id=shared_event_id,
        event_type="POST_HIDDEN",
        title="Thông báo 1",
        message="Nội dung 1",
    )
    db_session.add(notif1)
    await db_session.commit()

    # Second insert with the identical event_id must fail at the database level
    notif2 = Notification(
        id=uuid.uuid4(),
        recipient_id=test_user_a.id,
        event_id=shared_event_id,
        event_type="POST_HIDDEN",
        title="Thông báo 2",
        message="Nội dung 2",
    )
    db_session.add(notif2)
    with pytest.raises(IntegrityError):
        await db_session.flush()

    await db_session.rollback()


@pytest.mark.asyncio
async def test_notification_recipient_fk_cascade_delete(
    db_session: AsyncSession,
):
    """
    Verifies that deleting a User cascades to delete all their notifications (ON DELETE CASCADE).
    """
    temp_user = User(
        id=uuid.uuid4(),
        email=f"cascade_test_{uuid.uuid4().hex[:8]}@example.com",
        password_hash="secret_cascade",
        role="USER",
        status="ACTIVE",
    )
    db_session.add(temp_user)
    await db_session.commit()

    user_id = temp_user.id

    notif1 = Notification(
        id=uuid.uuid4(),
        recipient_id=user_id,
        event_type="CLAIM_UPDATE",
        title="Thông báo Cascade 1",
        message="Nội dung",
    )
    notif2 = Notification(
        id=uuid.uuid4(),
        recipient_id=user_id,
        event_type="CLAIM_UPDATE",
        title="Thông báo Cascade 2",
        message="Nội dung",
    )
    db_session.add_all([notif1, notif2])
    await db_session.commit()

    # Delete user
    await db_session.delete(temp_user)
    await db_session.commit()

    # Verify notifications were deleted automatically
    async with TestingSessionLocal() as session:
        stmt = select(func.count()).select_from(Notification).where(Notification.recipient_id == user_id)
        res = await session.execute(stmt)
        assert res.scalar_one() == 0


@pytest.mark.asyncio
async def test_notification_auto_commit_false_rollback(
    db_session: AsyncSession,
    test_user_a: User,
):
    """
    Verifies that when auto_commit=False, an external transaction rollback
    leaves NO persisted notification record in the database.
    """
    service = NotificationService()
    notif_data = NotificationCreateInternal(
        recipient_id=test_user_a.id,
        event_type="POST_HIDDEN",
        title="Thông báo kiểm thử rollback",
        message="Nội dung không được tồn tại sau khi rollback",
    )

    created_notif = await service.create_notification(
        session=db_session,
        data=notif_data,
        auto_commit=False,
    )
    notif_id = created_notif.id

    # Simulate caller transaction rollback
    await db_session.rollback()

    # Verify in a fresh session that the record does NOT exist
    async with TestingSessionLocal() as session:
        stmt = select(Notification).where(Notification.id == notif_id)
        res = await session.execute(stmt)
        assert res.scalars().first() is None


@pytest.mark.asyncio
async def test_multi_user_notification_isolation(
    db_session: AsyncSession,
    test_user_a: User,
    test_user_b: User,
):
    """
    Verifies that notifications for multiple users remain strictly isolated
    and query results never leak cross-tenant data.
    """
    repo = NotificationRepository()

    # Create 3 notifications for User A
    for i in range(3):
        n = Notification(
            id=uuid.uuid4(),
            recipient_id=test_user_a.id,
            event_type="USER_A_EVENT",
            title=f"User A Notice {i}",
            message="Private message for A",
        )
        db_session.add(n)

    # Create 2 notifications for User B
    for j in range(2):
        n = Notification(
            id=uuid.uuid4(),
            recipient_id=test_user_b.id,
            event_type="USER_B_EVENT",
            title=f"User B Notice {j}",
            message="Private message for B",
        )
        db_session.add(n)

    await db_session.commit()

    # Query for User A
    items_a, total_a = await repo.list_by_recipient(
        session=db_session,
        recipient_id=test_user_a.id,
        page=1,
        limit=10,
    )
    assert total_a == 3
    assert len(items_a) == 3
    assert all(item.recipient_id == test_user_a.id for item in items_a)
    assert all("User A" in item.title for item in items_a)

    # Query for User B
    items_b, total_b = await repo.list_by_recipient(
        session=db_session,
        recipient_id=test_user_b.id,
        page=1,
        limit=10,
    )
    assert total_b == 2
    assert len(items_b) == 2
    assert all(item.recipient_id == test_user_b.id for item in items_b)
    assert all("User B" in item.title for item in items_b)


@pytest.mark.asyncio
async def test_notification_metadata_jsonb_storage_and_unread_count(
    db_session: AsyncSession,
    test_user_a: User,
):
    """
    Verifies JSONB metadata persistence (nested types, Vietnamese text)
    and accuracy of unread vs read notifications filtering.
    """
    repo = NotificationRepository()

    # 1. Unread notification with complex JSONB metadata
    metadata_payload = {
        "resource_type": "POST",
        "action": "HIDE",
        "nested_details": {
            "department": "Quản trị an toàn",
            "reference_number": 12345,
            "tags": ["lost", "electronics", "urgent"],
        },
    }
    unread_notif = Notification(
        id=uuid.uuid4(),
        recipient_id=test_user_a.id,
        event_type="POST_HIDDEN",
        title="Chứa metadata JSONB",
        message="Nội dung kiểm tra JSONB",
        metadata_json=metadata_payload,
        is_read=False,
    )

    # 2. Read notification
    read_notif = Notification(
        id=uuid.uuid4(),
        recipient_id=test_user_a.id,
        event_type="POST_HIDDEN",
        title="Thông báo đã đọc",
        message="Nội dung đã đọc",
        is_read=True,
        read_at=datetime.now(timezone.utc),
    )
    db_session.add_all([unread_notif, read_notif])
    await db_session.commit()

    # Query unread only
    unread_items, unread_total = await repo.list_by_recipient(
        session=db_session,
        recipient_id=test_user_a.id,
        page=1,
        limit=10,
        is_read=False,
    )
    assert unread_total == 1
    retrieved = unread_items[0]
    assert retrieved.id == unread_notif.id
    assert retrieved.is_read is False
    assert retrieved.metadata_json == metadata_payload
    assert retrieved.metadata_json["nested_details"]["department"] == "Quản trị an toàn"

    # Query read only
    read_items, read_total = await repo.list_by_recipient(
        session=db_session,
        recipient_id=test_user_a.id,
        page=1,
        limit=10,
        is_read=True,
    )
    assert read_total == 1
    assert read_items[0].id == read_notif.id
