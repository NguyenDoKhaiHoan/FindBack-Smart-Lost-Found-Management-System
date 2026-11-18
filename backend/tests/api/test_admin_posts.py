from datetime import datetime, timezone
from unittest.mock import patch
import uuid
from httpx import AsyncClient
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.identity.models.user import User
from app.modules.notifications_admin.models.audit_log import AuditLog
from app.modules.notifications_admin.models.notification import Notification
from app.modules.posts.models.post import Post


async def create_test_post(
    session: AsyncSession,
    user_id: uuid.UUID,
    title: str = "Ví da nam màu nâu",
    description: str = "Đánh rơi ví tại sảnh toà nhà FPT",
    type_: str = "LOST",
    status: str = "ACTIVE",
    location: str | None = "Tòa nhà FPT Cầu Giấy",
    area: str | None = "Cầu Giấy",
    moderated_by: uuid.UUID | None = None,
    moderated_at: datetime | None = None,
    moderation_reason: str | None = None,
) -> Post:
    """Helper to seed posts into the test database."""
    post = Post(
        id=uuid.uuid4(),
        user_id=user_id,
        title=title,
        description=description,
        type=type_,
        status=status,
        location=location,
        area=area,
        moderated_by=moderated_by,
        moderated_at=moderated_at,
        moderation_reason=moderation_reason,
    )
    session.add(post)
    await session.commit()
    await session.refresh(post)
    return post


# ==========================================
# 1. Authentication & RBAC Tests
# ==========================================

@pytest.mark.asyncio
async def test_unauthenticated_request_rejected(client: AsyncClient):
    """Req 1: Unauthenticated requests return 401."""
    # GET admin posts
    res_get = await client.get("/api/v1/admin/posts")
    assert res_get.status_code == 401

    # PATCH moderation
    random_id = uuid.uuid4()
    res_patch = await client.patch(
        f"/api/v1/admin/posts/{random_id}/moderation",
        json={"action": "HIDE", "reason": "Test reason"},
    )
    assert res_patch.status_code == 401


@pytest.mark.asyncio
async def test_normal_user_cannot_access_admin_post_listing(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
):
    """Req 2: Normal USER cannot access admin post listing (returns 403)."""
    res = await client.get("/api/v1/admin/posts", headers=auth_headers_user_a)
    assert res.status_code == 403
    assert "chỉ dành cho quản trị viên" in res.json()["detail"].lower() or "quản trị viên" in res.json()["detail"]


@pytest.mark.asyncio
async def test_normal_user_cannot_moderate_posts(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
):
    """Req 3: Normal USER cannot moderate posts (returns 403)."""
    random_id = uuid.uuid4()
    res = await client.patch(
        f"/api/v1/admin/posts/{random_id}/moderation",
        headers=auth_headers_user_a,
        json={"action": "HIDE", "reason": "Test reason"},
    )
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_admin_can_access_apis(
    client: AsyncClient,
    auth_headers_admin: dict[str, str],
):
    """Req 4: ADMIN can access the APIs (returns 200)."""
    res = await client.get("/api/v1/admin/posts", headers=auth_headers_admin)
    assert res.status_code == 200
    data = res.json()
    assert "items" in data
    assert "pagination" in data


# ==========================================
# 2. GET /api/v1/admin/posts Tests
# ==========================================

@pytest.mark.asyncio
async def test_admin_posts_pagination(
    client: AsyncClient,
    db_session: AsyncSession,
    test_user_a: User,
    auth_headers_admin: dict[str, str],
):
    """Req 5: Pagination works correctly."""
    for i in range(7):
        await create_test_post(db_session, test_user_a.id, title=f"Post Item {i}")

    # Page 1, limit 3
    res_p1 = await client.get("/api/v1/admin/posts?page=1&limit=3", headers=auth_headers_admin)
    assert res_p1.status_code == 200
    data_p1 = res_p1.json()
    assert len(data_p1["items"]) == 3
    assert data_p1["pagination"]["total"] == 7
    assert data_p1["pagination"]["total_pages"] == 3
    assert data_p1["pagination"]["page"] == 1

    # Page 3, limit 3
    res_p3 = await client.get("/api/v1/admin/posts?page=3&limit=3", headers=auth_headers_admin)
    assert res_p3.status_code == 200
    data_p3 = res_p3.json()
    assert len(data_p3["items"]) == 1


@pytest.mark.asyncio
async def test_admin_posts_status_filter(
    client: AsyncClient,
    db_session: AsyncSession,
    test_user_a: User,
    auth_headers_admin: dict[str, str],
):
    """Req 6: Status filter works correctly."""
    await create_test_post(db_session, test_user_a.id, title="Active 1", status="ACTIVE")
    await create_test_post(db_session, test_user_a.id, title="Active 2", status="ACTIVE")
    await create_test_post(
        db_session,
        test_user_a.id,
        title="Hidden 1",
        status="HIDDEN",
        moderated_by=test_user_a.id,
        moderated_at=datetime.now(timezone.utc),
        moderation_reason="Test moderation",
    )
    await create_test_post(db_session, test_user_a.id, title="Closed 1", status="CLOSED")

    # Filter ACTIVE
    res_active = await client.get("/api/v1/admin/posts?status=ACTIVE", headers=auth_headers_admin)
    assert res_active.status_code == 200
    items_active = res_active.json()["items"]
    assert len(items_active) == 2
    assert all(i["status"] == "ACTIVE" for i in items_active)

    # Filter HIDDEN
    res_hidden = await client.get("/api/v1/admin/posts?status=HIDDEN", headers=auth_headers_admin)
    assert res_hidden.status_code == 200
    items_hidden = res_hidden.json()["items"]
    assert len(items_hidden) == 1
    assert items_hidden[0]["status"] == "HIDDEN"


@pytest.mark.asyncio
async def test_admin_posts_type_filter(
    client: AsyncClient,
    db_session: AsyncSession,
    test_user_a: User,
    auth_headers_admin: dict[str, str],
):
    """Req 7: Type filter works correctly."""
    await create_test_post(db_session, test_user_a.id, title="Lost Item 1", type_="LOST")
    await create_test_post(db_session, test_user_a.id, title="Lost Item 2", type_="LOST")
    await create_test_post(db_session, test_user_a.id, title="Found Item 1", type_="FOUND")

    res_lost = await client.get("/api/v1/admin/posts?type=LOST", headers=auth_headers_admin)
    assert res_lost.status_code == 200
    items_lost = res_lost.json()["items"]
    assert len(items_lost) == 2
    assert all(i["type"] == "LOST" for i in items_lost)

    res_found = await client.get("/api/v1/admin/posts?type=FOUND", headers=auth_headers_admin)
    assert res_found.status_code == 200
    items_found = res_found.json()["items"]
    assert len(items_found) == 1
    assert items_found[0]["type"] == "FOUND"


@pytest.mark.asyncio
async def test_admin_posts_keyword_search(
    client: AsyncClient,
    db_session: AsyncSession,
    test_user_a: User,
    auth_headers_admin: dict[str, str],
):
    """Req 8: Keyword search works across title, description, and location."""
    await create_test_post(
        db_session,
        test_user_a.id,
        title="Mất chìa khóa xe máy Honda",
        description="Có móc khóa hình gấu bông",
        location="Bãi xe B1",
    )
    await create_test_post(
        db_session,
        test_user_a.id,
        title="Nhặt được ví nam Coach",
        description="Ví da màu đen có giấy tờ tùy thân",
        location="Căn tin tầng 5",
    )

    # Search title
    res_q1 = await client.get("/api/v1/admin/posts?q=chìa khóa", headers=auth_headers_admin)
    assert res_q1.status_code == 200
    assert len(res_q1.json()["items"]) == 1
    assert "chìa khóa" in res_q1.json()["items"][0]["title"]

    # Search description
    res_q2 = await client.get("/api/v1/admin/posts?q=gấu bông", headers=auth_headers_admin)
    assert res_q2.status_code == 200
    assert len(res_q2.json()["items"]) == 1

    # Search location
    res_q3 = await client.get("/api/v1/admin/posts?q=căn tin", headers=auth_headers_admin)
    assert res_q3.status_code == 200
    assert len(res_q3.json()["items"]) == 1

    # Search non-matching
    res_q4 = await client.get("/api/v1/admin/posts?q=khong_tim_thay_xyz", headers=auth_headers_admin)
    assert res_q4.status_code == 200
    assert len(res_q4.json()["items"]) == 0


@pytest.mark.asyncio
async def test_admin_posts_invalid_filters_validation_errors(
    client: AsyncClient,
    auth_headers_admin: dict[str, str],
):
    """Req 9: Invalid pagination/filter values return 422."""
    # Invalid page (< 1)
    res_page = await client.get("/api/v1/admin/posts?page=0", headers=auth_headers_admin)
    assert res_page.status_code == 422

    # Invalid limit (> 100)
    res_limit = await client.get("/api/v1/admin/posts?limit=101", headers=auth_headers_admin)
    assert res_limit.status_code == 422

    # Invalid status
    res_status = await client.get("/api/v1/admin/posts?status=INVALID_STATUS", headers=auth_headers_admin)
    assert res_status.status_code == 422

    # Invalid type
    res_type = await client.get("/api/v1/admin/posts?type=INVALID_TYPE", headers=auth_headers_admin)
    assert res_type.status_code == 422


@pytest.mark.asyncio
async def test_admin_posts_response_does_not_expose_sensitive_fields(
    client: AsyncClient,
    db_session: AsyncSession,
    test_user_a: User,
    auth_headers_admin: dict[str, str],
):
    """Req 10: Response does not expose private evidence, tokens, or password hashes."""
    await create_test_post(db_session, test_user_a.id, title="Public Post")

    res = await client.get("/api/v1/admin/posts", headers=auth_headers_admin)
    assert res.status_code == 200
    item = res.json()["items"][0]

    forbidden_fields = {"password", "password_hash", "token", "evidence", "private_evidence", "secret"}
    for key in item.keys():
        assert key.lower() not in forbidden_fields


# ==========================================
# 3. PATCH /api/v1/admin/posts/{id}/moderation Tests
# ==========================================

@pytest.mark.asyncio
async def test_successful_hide_changes_status_to_hidden(
    client: AsyncClient,
    db_session: AsyncSession,
    test_user_a: User,
    auth_headers_admin: dict[str, str],
):
    """Req 11: Successful HIDE changes status to HIDDEN."""
    post = await create_test_post(db_session, test_user_a.id, status="ACTIVE")

    res = await client.patch(
        f"/api/v1/admin/posts/{post.id}/moderation",
        headers=auth_headers_admin,
        json={"action": "HIDE", "reason": "Nội dung spam quảng cáo"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "HIDDEN"

    post_stmt = select(Post).where(Post.id == post.id)
    post_res = await db_session.execute(post_stmt)
    refreshed_post = post_res.scalars().first()
    assert refreshed_post.status == "HIDDEN"


@pytest.mark.asyncio
async def test_missing_reason_rejected(
    client: AsyncClient,
    db_session: AsyncSession,
    test_user_a: User,
    auth_headers_admin: dict[str, str],
):
    """Req 12: Missing reason in request body is rejected with 422."""
    post = await create_test_post(db_session, test_user_a.id)

    res = await client.patch(
        f"/api/v1/admin/posts/{post.id}/moderation",
        headers=auth_headers_admin,
        json={"action": "HIDE"},
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_empty_or_whitespace_reason_rejected(
    client: AsyncClient,
    db_session: AsyncSession,
    test_user_a: User,
    auth_headers_admin: dict[str, str],
):
    """Req 13: Empty or whitespace reason is rejected with 422."""
    post = await create_test_post(db_session, test_user_a.id)

    res = await client.patch(
        f"/api/v1/admin/posts/{post.id}/moderation",
        headers=auth_headers_admin,
        json={"action": "HIDE", "reason": "   "},
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_missing_post_returns_404(
    client: AsyncClient,
    auth_headers_admin: dict[str, str],
):
    """Req 14: Moderating nonexistent post returns 404."""
    nonexistent_id = uuid.uuid4()
    res = await client.patch(
        f"/api/v1/admin/posts/{nonexistent_id}/moderation",
        headers=auth_headers_admin,
        json={"action": "HIDE", "reason": "Vi phạm"},
    )
    assert res.status_code == 404
    assert "không tồn tại" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_closed_post_returns_400(
    client: AsyncClient,
    db_session: AsyncSession,
    test_user_a: User,
    auth_headers_admin: dict[str, str],
):
    """Req 15: Moderating a CLOSED post returns 400."""
    post = await create_test_post(db_session, test_user_a.id, status="CLOSED")

    res = await client.patch(
        f"/api/v1/admin/posts/{post.id}/moderation",
        headers=auth_headers_admin,
        json={"action": "HIDE", "reason": "Nội dung vi phạm"},
    )
    assert res.status_code == 400
    assert "closed" in res.json()["detail"].lower() or "đóng" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_moderated_by_is_correct(
    client: AsyncClient,
    db_session: AsyncSession,
    test_user_a: User,
    test_admin_user: User,
    auth_headers_admin: dict[str, str],
):
    """Req 16: moderated_by is set to current admin UUID."""
    post = await create_test_post(db_session, test_user_a.id)

    res = await client.patch(
        f"/api/v1/admin/posts/{post.id}/moderation",
        headers=auth_headers_admin,
        json={"action": "HIDE", "reason": "Bài đăng sai danh mục"},
    )
    assert res.status_code == 200
    assert res.json()["moderated_by"] == str(test_admin_user.id)

    post_stmt = select(Post).where(Post.id == post.id)
    post_res = await db_session.execute(post_stmt)
    refreshed_post = post_res.scalars().first()
    assert refreshed_post.moderated_by == test_admin_user.id


@pytest.mark.asyncio
async def test_moderated_at_is_recorded(
    client: AsyncClient,
    db_session: AsyncSession,
    test_user_a: User,
    auth_headers_admin: dict[str, str],
):
    """Req 17: moderated_at timestamp is accurately recorded."""
    post = await create_test_post(db_session, test_user_a.id)

    before = datetime.now(timezone.utc)
    res = await client.patch(
        f"/api/v1/admin/posts/{post.id}/moderation",
        headers=auth_headers_admin,
        json={"action": "HIDE", "reason": "Vi phạm quy định hình ảnh"},
    )
    assert res.status_code == 200
    moderated_at_str = res.json()["moderated_at"]
    assert moderated_at_str is not None

    post_stmt = select(Post).where(Post.id == post.id)
    post_res = await db_session.execute(post_stmt)
    refreshed_post = post_res.scalars().first()
    assert refreshed_post.moderated_at is not None
    assert refreshed_post.moderated_at >= before


@pytest.mark.asyncio
async def test_moderation_reason_is_stored(
    client: AsyncClient,
    db_session: AsyncSession,
    test_user_a: User,
    auth_headers_admin: dict[str, str],
):
    """Req 18: moderation_reason is stored in DB and returned in response."""
    post = await create_test_post(db_session, test_user_a.id)
    expected_reason = "Hình ảnh chứa thông tin nhạy cảm của bên thứ ba"

    res = await client.patch(
        f"/api/v1/admin/posts/{post.id}/moderation",
        headers=auth_headers_admin,
        json={"action": "HIDE", "reason": expected_reason},
    )
    assert res.status_code == 200
    assert res.json()["moderation_reason"] == expected_reason

    post_stmt = select(Post).where(Post.id == post.id)
    post_res = await db_session.execute(post_stmt)
    refreshed_post = post_res.scalars().first()
    assert refreshed_post.moderation_reason == expected_reason


@pytest.mark.asyncio
async def test_audit_log_is_created(
    client: AsyncClient,
    db_session: AsyncSession,
    test_user_a: User,
    test_admin_user: User,
    auth_headers_admin: dict[str, str],
):
    """Req 19: Audit log is created with actor, action, target, reason, and timestamps."""
    post = await create_test_post(db_session, test_user_a.id, status="ACTIVE")
    reason = "Nội dung vi phạm tiêu chuẩn cộng đồng"

    res = await client.patch(
        f"/api/v1/admin/posts/{post.id}/moderation",
        headers=auth_headers_admin,
        json={"action": "HIDE", "reason": reason},
    )
    assert res.status_code == 200

    # Query audit_logs
    stmt = select(AuditLog).where(
        AuditLog.target_type == "POST",
        AuditLog.target_id == post.id,
    )
    result = await db_session.execute(stmt)
    audit = result.scalars().first()

    assert audit is not None
    assert audit.actor_id == test_admin_user.id
    assert audit.action == "HIDE"
    assert audit.reason == reason
    assert audit.old_status == "ACTIVE"
    assert audit.new_status == "HIDDEN"


@pytest.mark.asyncio
async def test_post_owner_receives_post_hidden_notification(
    client: AsyncClient,
    db_session: AsyncSession,
    test_user_a: User,
    auth_headers_admin: dict[str, str],
):
    """Req 20: Post owner receives POST_HIDDEN notification."""
    post = await create_test_post(db_session, test_user_a.id, title="Điện thoại iPhone 13")

    res = await client.patch(
        f"/api/v1/admin/posts/{post.id}/moderation",
        headers=auth_headers_admin,
        json={"action": "HIDE", "reason": "Nội dung trùng lặp"},
    )
    assert res.status_code == 200

    # Query notifications for post owner
    stmt = select(Notification).where(
        Notification.recipient_id == test_user_a.id,
        Notification.resource_id == post.id,
    )
    result = await db_session.execute(stmt)
    notification = result.scalars().first()

    assert notification is not None
    assert notification.event_type == "POST_HIDDEN"
    assert notification.resource_type == "POST"
    assert "Điện thoại iPhone 13" in notification.message
    assert "Nội dung trùng lặp" in notification.message


@pytest.mark.asyncio
async def test_notification_failure_rolls_back_moderation_transaction(
    client: AsyncClient,
    db_session: AsyncSession,
    test_user_a: User,
    auth_headers_admin: dict[str, str],
):
    """Req 21: Notification failure rolls back the entire moderation transaction."""
    post = await create_test_post(db_session, test_user_a.id, status="ACTIVE")
    post_id = post.id

    # Patch NotificationService.create_notification to raise an exception
    with patch(
        "app.modules.notifications_admin.services.notification_service.NotificationService.create_notification",
        side_effect=RuntimeError("Simulated notification service failure"),
    ):
        with pytest.raises(RuntimeError, match="Simulated notification service failure"):
            await client.patch(
                f"/api/v1/admin/posts/{post_id}/moderation",
                headers=auth_headers_admin,
                json={"action": "HIDE", "reason": "Lỗi hệ thống"},
            )

    # Expunge identity map to cleanly load fresh attributes after rollback
    db_session.expunge_all()

    # Verify post remains ACTIVE and no moderation metadata saved
    post_stmt = select(Post).where(Post.id == post_id)
    post_res = await db_session.execute(post_stmt)
    refreshed_post = post_res.scalars().first()
    assert refreshed_post is not None
    assert refreshed_post.status == "ACTIVE"
    assert refreshed_post.moderated_by is None
    assert refreshed_post.moderation_reason is None

    # Verify no audit log was created
    audit_stmt = select(AuditLog).where(AuditLog.target_id == post_id)
    audit_res = await db_session.execute(audit_stmt)
    assert audit_res.scalars().first() is None


@pytest.mark.asyncio
async def test_repeated_moderation_is_deterministic_and_no_duplicate_notification(
    client: AsyncClient,
    db_session: AsyncSession,
    test_user_a: User,
    auth_headers_admin: dict[str, str],
):
    """Req 22: Repeated moderation is deterministic and does not duplicate notifications."""
    post = await create_test_post(db_session, test_user_a.id, status="ACTIVE")

    # Moderation 1
    res1 = await client.patch(
        f"/api/v1/admin/posts/{post.id}/moderation",
        headers=auth_headers_admin,
        json={"action": "HIDE", "reason": "Lần 1: vi phạm quy định"},
    )
    assert res1.status_code == 200
    assert res1.json()["status"] == "HIDDEN"
    assert res1.json()["moderation_reason"] == "Lần 1: vi phạm quy định"
    initial_moderated_at = res1.json()["moderated_at"]
    initial_moderated_by = res1.json()["moderated_by"]

    # Moderation 2 (repeated)
    res2 = await client.patch(
        f"/api/v1/admin/posts/{post.id}/moderation",
        headers=auth_headers_admin,
        json={"action": "HIDE", "reason": "Lần 2: tiếp tục ẩn"},
    )
    assert res2.status_code == 200
    assert res2.json()["status"] == "HIDDEN"
    # Idempotency check: verify initial moderation metadata is PRESERVED and not overwritten
    assert res2.json()["moderation_reason"] == "Lần 1: vi phạm quy định"
    assert res2.json()["moderated_at"] == initial_moderated_at
    assert res2.json()["moderated_by"] == initial_moderated_by

    # Verify audit_logs count: exactly 1 audit log exists
    audit_stmt = select(AuditLog).where(AuditLog.target_id == post.id)
    audit_res = await db_session.execute(audit_stmt)
    assert len(audit_res.scalars().all()) == 1

    # Verify notifications count: exactly 1 notification exists for this post
    stmt = select(Notification).where(
        Notification.recipient_id == test_user_a.id,
        Notification.resource_id == post.id,
    )
    result = await db_session.execute(stmt)
    notifications = result.scalars().all()
    assert len(notifications) == 1


@pytest.mark.asyncio
async def test_audit_log_failure_rolls_back_moderation_transaction(
    client: AsyncClient,
    db_session: AsyncSession,
    test_user_a: User,
    auth_headers_admin: dict[str, str],
):
    """Req 23: AuditLog failure rolls back the entire moderation transaction."""
    post = await create_test_post(db_session, test_user_a.id, status="ACTIVE")
    post_id = post.id

    # Patch AuditLogRepository.create to raise an exception
    with patch(
        "app.modules.notifications_admin.repositories.audit_log_repository.AuditLogRepository.create",
        side_effect=RuntimeError("Simulated audit log insertion failure"),
    ):
        with pytest.raises(RuntimeError, match="Simulated audit log insertion failure"):
            await client.patch(
                f"/api/v1/admin/posts/{post_id}/moderation",
                headers=auth_headers_admin,
                json={"action": "HIDE", "reason": "Lỗi audit log"},
            )

    db_session.expunge_all()

    # Verify post remains ACTIVE and no moderation metadata saved
    post_stmt = select(Post).where(Post.id == post_id)
    post_res = await db_session.execute(post_stmt)
    refreshed_post = post_res.scalars().first()
    assert refreshed_post is not None
    assert refreshed_post.status == "ACTIVE"
    assert refreshed_post.moderated_by is None

    # Verify no notification was created
    notif_stmt = select(Notification).where(Notification.resource_id == post_id)
    notif_res = await db_session.execute(notif_stmt)
    assert notif_res.scalars().first() is None


@pytest.mark.asyncio
async def test_commit_failure_rolls_back_moderation_transaction(
    client: AsyncClient,
    db_session: AsyncSession,
    test_user_a: User,
    auth_headers_admin: dict[str, str],
):
    """Req 24: Database commit failure rolls back the entire moderation transaction."""
    post = await create_test_post(db_session, test_user_a.id, status="ACTIVE")
    post_id = post.id

    # Patch AsyncSession.commit to raise an exception
    with patch.object(
        db_session,
        "commit",
        side_effect=RuntimeError("Simulated database commit failure"),
    ):
        with pytest.raises(RuntimeError, match="Simulated database commit failure"):
            await client.patch(
                f"/api/v1/admin/posts/{post_id}/moderation",
                headers=auth_headers_admin,
                json={"action": "HIDE", "reason": "Lỗi commit DB"},
            )

    db_session.expunge_all()

    # Verify post remains ACTIVE in the database
    post_stmt = select(Post).where(Post.id == post_id)
    post_res = await db_session.execute(post_stmt)
    refreshed_post = post_res.scalars().first()
    assert refreshed_post is not None
    assert refreshed_post.status == "ACTIVE"
    assert refreshed_post.moderated_by is None

    # Verify no audit log was committed
    audit_stmt = select(AuditLog).where(AuditLog.target_id == post_id)
    audit_res = await db_session.execute(audit_stmt)
    assert audit_res.scalars().first() is None

    # Verify no notification was committed
    notif_stmt = select(Notification).where(Notification.resource_id == post_id)
    notif_res = await db_session.execute(notif_stmt)
    assert notif_res.scalars().first() is None


@pytest.mark.asyncio
async def test_concurrent_moderation_from_two_admins(
    db_session: AsyncSession,
    test_user_a: User,
    test_admin_user: User,
    auth_headers_admin: dict[str, str],
):
    """Req 25: Concurrent moderation from two admins is race-free and deterministic."""
    import asyncio
    from httpx import ASGITransport, AsyncClient
    from app.db.session import get_db
    from app.main import app
    from tests.conftest import TestingSessionLocal, create_test_jwt

    post = await create_test_post(db_session, test_user_a.id, status="ACTIVE")
    post_id = post.id

    # Create a second admin user
    second_admin = User(
        id=uuid.uuid4(),
        email=f"admin2_{uuid.uuid4().hex[:8]}@example.com",
        password_hash="secret_admin_2",
        role="ADMIN",
        status="ACTIVE",
    )
    db_session.add(second_admin)
    await db_session.commit()
    auth_headers_admin2 = {"Authorization": f"Bearer {create_test_jwt(second_admin.id, role='ADMIN')}"}

    # Override get_db with independent sessions per request for genuine DB concurrency
    async def concurrent_get_db():
        async with TestingSessionLocal() as session:
            yield session

    app.dependency_overrides[get_db] = concurrent_get_db
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as c1, \
               AsyncClient(transport=transport, base_url="http://test") as c2:
        req1 = c1.patch(
            f"/api/v1/admin/posts/{post_id}/moderation",
            headers=auth_headers_admin,
            json={"action": "HIDE", "reason": "Admin 1: Vi phạm quảng cáo"},
        )
        req2 = c2.patch(
            f"/api/v1/admin/posts/{post_id}/moderation",
            headers=auth_headers_admin2,
            json={"action": "HIDE", "reason": "Admin 2: Vi phạm spam"},
        )

        res1, res2 = await asyncio.gather(req1, req2)

    app.dependency_overrides.clear()

    # Both requests must succeed (HTTP 200) with status HIDDEN
    assert res1.status_code == 200
    assert res2.status_code == 200
    assert res1.json()["status"] == "HIDDEN"
    assert res2.json()["status"] == "HIDDEN"

    # Verify in DB: Post is HIDDEN
    db_session.expunge_all()
    post_stmt = select(Post).where(Post.id == post_id)
    post_res = await db_session.execute(post_stmt)
    refreshed_post = post_res.scalars().first()
    assert refreshed_post is not None
    assert refreshed_post.status == "HIDDEN"

    # Exactly 1 audit log was recorded for the first admin who acquired the row lock
    audit_stmt = select(AuditLog).where(AuditLog.target_id == post_id)
    audit_res = await db_session.execute(audit_stmt)
    audit_logs = audit_res.scalars().all()
    assert len(audit_logs) == 1

    # Exactly 1 notification was emitted for the post owner
    notif_stmt = select(Notification).where(Notification.resource_id == post_id)
    notif_res = await db_session.execute(notif_stmt)
    notifications = notif_res.scalars().all()
    assert len(notifications) == 1


# ============================================================================
# 8. KAN-33 API Edge Cases & Parameter Validation
# ============================================================================

@pytest.mark.asyncio
async def test_admin_posts_pagination_boundary_values(
    client: AsyncClient,
    auth_headers_admin: dict[str, str],
):
    """Verifies that invalid page and limit query parameters return HTTP 422."""
    # page < 1
    res_page_zero = await client.get("/api/v1/admin/posts?page=0", headers=auth_headers_admin)
    assert res_page_zero.status_code == 422

    res_page_neg = await client.get("/api/v1/admin/posts?page=-5", headers=auth_headers_admin)
    assert res_page_neg.status_code == 422

    # limit < 1
    res_limit_zero = await client.get("/api/v1/admin/posts?limit=0", headers=auth_headers_admin)
    assert res_limit_zero.status_code == 422

    # limit > 100
    res_limit_exceed = await client.get("/api/v1/admin/posts?limit=101", headers=auth_headers_admin)
    assert res_limit_exceed.status_code == 422


@pytest.mark.asyncio
async def test_admin_posts_combined_filters_and_search(
    client: AsyncClient,
    db_session: AsyncSession,
    test_user_a: User,
    auth_headers_admin: dict[str, str],
):
    """Verifies filtering by status + type + search keyword simultaneously."""
    # Match: status=ACTIVE, type=LOST, contains "ví da"
    target_post = await create_test_post(
        db_session,
        test_user_a.id,
        title="Bị mất ví da màu đen tại Cầu Giấy",
        type_="LOST",
        status="ACTIVE",
    )
    # Different type
    await create_test_post(
        db_session,
        test_user_a.id,
        title="Tìm thấy ví da màu đen tại Cầu Giấy",
        type_="FOUND",
        status="ACTIVE",
    )
    # Different keyword
    await create_test_post(
        db_session,
        test_user_a.id,
        title="Bị rơi chìa khóa xe máy",
        type_="LOST",
        status="ACTIVE",
    )
    # Different status
    await create_test_post(
        db_session,
        test_user_a.id,
        title="Bị mất ví da tại siêu thị",
        type_="LOST",
        status="HIDDEN",
    )

    res = await client.get(
        "/api/v1/admin/posts?status=ACTIVE&type=LOST&q=ví da",
        headers=auth_headers_admin,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["pagination"]["total"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["id"] == str(target_post.id)
    assert data["items"][0]["status"] == "ACTIVE"
    assert data["items"][0]["type"] == "LOST"


@pytest.mark.asyncio
async def test_admin_posts_invalid_uuid_param_rejected(
    client: AsyncClient,
    auth_headers_admin: dict[str, str],
):
    """Verifies that non-UUID path parameter format returns HTTP 422 Unprocessable Entity."""
    res = await client.patch(
        "/api/v1/admin/posts/not-a-valid-uuid-format/moderation",
        headers=auth_headers_admin,
        json={"action": "HIDE", "reason": "Kiểm thử định dạng UUID"},
    )
    assert res.status_code == 422
