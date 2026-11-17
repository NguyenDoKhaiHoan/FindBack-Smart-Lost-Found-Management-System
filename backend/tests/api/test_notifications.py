import asyncio
from datetime import datetime, timedelta, timezone
import uuid
from httpx import AsyncClient
import jwt
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.modules.identity.models.user import User
from app.modules.notifications_admin.models.notification import Notification
from app.modules.notifications_admin.schemas.notification import NotificationCreateInternal
from app.modules.notifications_admin.services.notification_service import NotificationService
from tests.conftest import create_test_jwt


# ============================================================================
# 1. Health Check
# ============================================================================

@pytest.mark.asyncio
async def test_health_check(client: AsyncClient):
    """Verifies health check endpoint returns healthy status."""
    res = await client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert data["database"] == "healthy"

    res_v1 = await client.get("/api/v1/health")
    assert res_v1.status_code == 200


# ============================================================================
# 2. Authentication & Authorization Security Tests (SEC-01 & SEC-02)
# ============================================================================

@pytest.mark.asyncio
async def test_unauthenticated_request_rejected(client: AsyncClient):
    """Requests without credentials must be rejected with 401 Unauthorized."""
    res = await client.get("/api/v1/notifications")
    assert res.status_code == 401
    assert "detail" in res.json()


@pytest.mark.asyncio
async def test_bearer_raw_uuid_rejected(client: AsyncClient, test_user_a: User):
    """
    SEC-01: Raw UUID passed directly in Authorization Bearer must NOT be accepted.
    Must return 401 Unauthorized.
    """
    headers = {"Authorization": f"Bearer {test_user_a.id}"}
    res = await client.get("/api/v1/notifications", headers=headers)
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_jwt_invalid_signature_rejected(client: AsyncClient, test_user_a: User):
    """JWT signed with an unauthorized secret key must be rejected with 401."""
    fake_token = create_test_jwt(test_user_a.id, secret_key="wrong_fake_secret_key_1234567890123")
    headers = {"Authorization": f"Bearer {fake_token}"}
    res = await client.get("/api/v1/notifications", headers=headers)
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_jwt_expired_rejected(client: AsyncClient, test_user_a: User):
    """Expired JWT must be rejected with 401."""
    expired_token = create_test_jwt(test_user_a.id, expires_delta=timedelta(seconds=-10))
    headers = {"Authorization": f"Bearer {expired_token}"}
    res = await client.get("/api/v1/notifications", headers=headers)
    assert res.status_code == 401
    assert "hết hạn" in res.json().get("detail", "").lower()


@pytest.mark.asyncio
async def test_jwt_invalid_algorithm_rejected(client: AsyncClient, test_user_a: User):
    """JWT signed with algorithm other than the configured algorithm must be rejected."""
    # Attempt with 'none' or incompatible algorithm
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(test_user_a.id),
        "role": test_user_a.role,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=1)).timestamp()),
    }
    # Encode with HS384 using a >= 48-byte key when server expects HS256
    token_diff_alg = jwt.encode(payload, "secure_testing_hmac_key_for_different_algorithm_at_least_48_bytes", algorithm="HS384")
    headers = {"Authorization": f"Bearer {token_diff_alg}"}
    res = await client.get("/api/v1/notifications", headers=headers)
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_jwt_unknown_user_rejected(client: AsyncClient):
    """Valid JWT pointing to a non-existent user UUID must return 401."""
    random_user_id = uuid.uuid4()
    token = create_test_jwt(random_user_id)
    headers = {"Authorization": f"Bearer {token}"}
    res = await client.get("/api/v1/notifications", headers=headers)
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_inactive_user_suspended_forbidden(client: AsyncClient, test_inactive_user: User):
    """Suspended user account with valid JWT must receive 403 Forbidden."""
    token = create_test_jwt(test_inactive_user.id, role=test_inactive_user.role)
    headers = {"Authorization": f"Bearer {token}"}
    res = await client.get("/api/v1/notifications", headers=headers)
    assert res.status_code == 403
    assert "SUSPENDED" in res.json().get("detail", "")


@pytest.mark.asyncio
async def test_inactive_user_disabled_forbidden(client: AsyncClient, test_disabled_user: User):
    """Disabled user account with valid JWT must receive 403 Forbidden."""
    token = create_test_jwt(test_disabled_user.id, role=test_disabled_user.role)
    headers = {"Authorization": f"Bearer {token}"}
    res = await client.get("/api/v1/notifications", headers=headers)
    assert res.status_code == 403
    assert "DISABLED" in res.json().get("detail", "")


@pytest.mark.asyncio
async def test_valid_jwt_active_user_success(client: AsyncClient, auth_headers_user_a: dict[str, str]):
    """Active user with valid JWT receives 200 OK."""
    res = await client.get("/api/v1/notifications", headers=auth_headers_user_a)
    assert res.status_code == 200
    assert "items" in res.json()
    assert "pagination" in res.json()


# ============================================================================
# 3. Notification Query & Ownership Isolation Tests
# ============================================================================

@pytest.mark.asyncio
async def test_user_only_sees_own_notifications(
    client: AsyncClient,
    db_session: AsyncSession,
    test_user_a: User,
    test_user_b: User,
    auth_headers_user_a: dict[str, str],
    auth_headers_user_b: dict[str, str],
):
    """A user must only see their own notifications, never those of another user."""
    service = NotificationService()

    notif_a = await service.create_notification(
        db_session,
        NotificationCreateInternal(
            recipient_id=test_user_a.id,
            event_type="CLAIM_CREATED",
            title="Thông báo cho User A",
            message="Nội dung cho User A",
        ),
    )

    notif_b = await service.create_notification(
        db_session,
        NotificationCreateInternal(
            recipient_id=test_user_b.id,
            event_type="POST_HIDDEN",
            title="Thông báo cho User B",
            message="Nội dung cho User B",
        ),
    )

    res_a = await client.get("/api/v1/notifications", headers=auth_headers_user_a)
    assert res_a.status_code == 200
    ids_a = [item["id"] for item in res_a.json()["items"]]
    assert str(notif_a.id) in ids_a
    assert str(notif_b.id) not in ids_a

    res_b = await client.get("/api/v1/notifications", headers=auth_headers_user_b)
    assert res_b.status_code == 200
    ids_b = [item["id"] for item in res_b.json()["items"]]
    assert str(notif_b.id) in ids_b
    assert str(notif_a.id) not in ids_b


@pytest.mark.asyncio
async def test_pagination(
    client: AsyncClient,
    db_session: AsyncSession,
    test_user_a: User,
    auth_headers_user_a: dict[str, str],
):
    """Pagination query params limit and page must be respected."""
    service = NotificationService()

    for i in range(5):
        await service.create_notification(
            db_session,
            NotificationCreateInternal(
                recipient_id=test_user_a.id,
                event_type="SYSTEM_NOTICE",
                title=f"Notification {i}",
                message=f"Message {i}",
            ),
        )

    res = await client.get(
        "/api/v1/notifications?page=1&limit=2",
        headers=auth_headers_user_a,
    )
    assert res.status_code == 200
    data = res.json()
    assert len(data["items"]) == 2
    assert data["pagination"]["page"] == 1
    assert data["pagination"]["limit"] == 2
    assert data["pagination"]["total"] == 5
    assert data["pagination"]["total_pages"] == 3


@pytest.mark.asyncio
async def test_filter_by_is_read(
    client: AsyncClient,
    db_session: AsyncSession,
    test_user_a: User,
    auth_headers_user_a: dict[str, str],
):
    """Filter parameter is_read=true/false works as expected."""
    service = NotificationService()

    notif_unread = await service.create_notification(
        db_session,
        NotificationCreateInternal(
            recipient_id=test_user_a.id,
            event_type="SYSTEM_NOTICE",
            title="Unread item",
            message="Still unread",
        ),
    )

    notif_read = await service.create_notification(
        db_session,
        NotificationCreateInternal(
            recipient_id=test_user_a.id,
            event_type="SYSTEM_NOTICE",
            title="Read item",
            message="To be read",
        ),
    )
    await service.mark_as_read(db_session, notif_read.id, test_user_a.id)

    # Query unread only
    res_unread = await client.get(
        "/api/v1/notifications?is_read=false",
        headers=auth_headers_user_a,
    )
    assert res_unread.status_code == 200
    unread_ids = [item["id"] for item in res_unread.json()["items"]]
    assert str(notif_unread.id) in unread_ids
    assert str(notif_read.id) not in unread_ids

    # Query read only
    res_read = await client.get(
        "/api/v1/notifications?is_read=true",
        headers=auth_headers_user_a,
    )
    assert res_read.status_code == 200
    read_ids = [item["id"] for item in res_read.json()["items"]]
    assert str(notif_read.id) in read_ids
    assert str(notif_unread.id) not in read_ids


@pytest.mark.asyncio
async def test_mark_as_read_success_and_idempotent(
    client: AsyncClient,
    db_session: AsyncSession,
    test_user_a: User,
    auth_headers_user_a: dict[str, str],
):
    """Marking a notification as read must succeed and repeated calls must be idempotent."""
    service = NotificationService()
    notif = await service.create_notification(
        db_session,
        NotificationCreateInternal(
            recipient_id=test_user_a.id,
            event_type="CLAIM_CREATED",
            title="Yêu cầu kiểm tra",
            message="Vui lòng đọc thông báo",
        ),
    )

    # First call
    res1 = await client.patch(
        f"/api/v1/notifications/{notif.id}/read",
        headers=auth_headers_user_a,
    )
    assert res1.status_code == 200
    data1 = res1.json()
    assert data1["id"] == str(notif.id)
    assert data1["is_read"] is True
    assert data1["read_at"] is not None
    first_read_at = data1["read_at"]

    # Second call (Idempotency)
    res2 = await client.patch(
        f"/api/v1/notifications/{notif.id}/read",
        headers=auth_headers_user_a,
    )
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["id"] == str(notif.id)
    assert data2["is_read"] is True
    assert data2["read_at"] == first_read_at


@pytest.mark.asyncio
async def test_user_cannot_mark_other_user_notification(
    client: AsyncClient,
    db_session: AsyncSession,
    test_user_a: User,
    auth_headers_user_b: dict[str, str],
):
    """Attempting to mark another user's notification returns 404 Not Found (anti-enumeration)."""
    service = NotificationService()
    notif_a = await service.create_notification(
        db_session,
        NotificationCreateInternal(
            recipient_id=test_user_a.id,
            event_type="CLAIM_CREATED",
            title="Thuộc User A",
            message="Chỉ User A được đọc",
        ),
    )

    res = await client.patch(
        f"/api/v1/notifications/{notif_a.id}/read",
        headers=auth_headers_user_b,
    )
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_mark_nonexistent_notification_returns_404(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
):
    """Non-existent notification ID returns 404 Not Found."""
    random_id = uuid.uuid4()
    res = await client.patch(
        f"/api/v1/notifications/{random_id}/read",
        headers=auth_headers_user_a,
    )
    assert res.status_code == 404


# ============================================================================
# 4. Idempotency & Concurrency Tests (CONC-01)
# ============================================================================

@pytest.mark.asyncio
async def test_internal_event_sequential_deduplication(
    db_session: AsyncSession,
    test_user_a: User,
):
    """Internal event emission with the same event_id must not duplicate notifications."""
    service = NotificationService()
    shared_event_id = uuid.uuid4()

    n1 = await service.create_notification(
        db_session,
        NotificationCreateInternal(
            recipient_id=test_user_a.id,
            event_id=shared_event_id,
            event_type="CLAIM_APPROVED",
            title="Yêu cầu được duyệt 1",
            message="Claim của bạn đã được duyệt.",
        ),
    )

    n2 = await service.create_notification(
        db_session,
        NotificationCreateInternal(
            recipient_id=test_user_a.id,
            event_id=shared_event_id,
            event_type="CLAIM_APPROVED",
            title="Yêu cầu được duyệt 2",
            message="Claim của bạn đã được duyệt.",
        ),
    )

    assert n1.id == n2.id
    # Existing title should not be overwritten
    assert n2.title == "Yêu cầu được duyệt 1"


@pytest.mark.asyncio
async def test_internal_event_concurrent_deduplication(test_user_a: User):
    """
    CONC-01: Two concurrent requests with the SAME event_id:
    - Must NOT raise unhandled IntegrityError or HTTP 500.
    - Must only create 1 notification in the database.
    - Both callers receive a valid Notification instance with the same ID.
    """
    from tests.conftest import TestingSessionLocal
    shared_event_id = uuid.uuid4()

    async def emit_event(title: str) -> Notification:
        async with TestingSessionLocal() as session:
            service = NotificationService()
            return await service.create_notification(
                session,
                NotificationCreateInternal(
                    recipient_id=test_user_a.id,
                    event_id=shared_event_id,
                    event_type="CLAIM_CREATED",
                    title=title,
                    message="Concurrent test message",
                ),
            )

    # Run two concurrent emissions simultaneously
    res1, res2 = await asyncio.gather(
        emit_event("Emission Alpha"),
        emit_event("Emission Beta"),
    )

    assert res1 is not None
    assert res2 is not None
    assert res1.id == res2.id

    # Verify database has exactly 1 notification for this event_id
    async with TestingSessionLocal() as session:
        count_stmt = (
            select(func.count())
            .select_from(Notification)
            .where(Notification.event_id == shared_event_id)
        )
        count_res = await session.execute(count_stmt)
        total_count = count_res.scalar_one()
        assert total_count == 1
