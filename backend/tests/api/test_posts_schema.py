from datetime import datetime, timezone
from decimal import Decimal
import uuid
from httpx import AsyncClient
import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.identity.models.user import User
from app.modules.notifications_admin.models.audit_log import AuditLog
from app.modules.notifications_admin.models.notification import Notification
from app.modules.posts.models.category import Category
from app.modules.posts.models.post import Post
from app.modules.posts.models.post_image import PostImage
from tests.conftest import create_test_jwt


async def create_user(
    session: AsyncSession,
    role: str = "USER",
    email: str | None = None,
) -> User:
    """Helper to create a user in test db."""
    uid = uuid.uuid4()
    user = User(
        id=uid,
        email=email or f"user_{uid.hex[:8]}@example.com",
        password_hash="mock_hash",
        role=role,
        status="ACTIVE",
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


# ==========================================
# 1. Categories Tests
# ==========================================

@pytest.mark.asyncio
async def test_category_creation_and_query(db_session: AsyncSession):
    """Verifies Category can be created, stored, and queried."""
    cat = Category(
        name="Điện tử",
        slug="dien-tu",
        description="Điện thoại, máy tính bảng, laptop",
    )
    db_session.add(cat)
    await db_session.commit()
    await db_session.refresh(cat)

    assert cat.id is not None
    assert cat.name == "Điện tử"
    assert cat.slug == "dien-tu"
    assert cat.description == "Điện thoại, máy tính bảng, laptop"

    # Query by slug
    stmt = select(Category).where(Category.slug == "dien-tu")
    result = await db_session.execute(stmt)
    found = result.scalars().first()
    assert found is not None
    assert found.id == cat.id


@pytest.mark.asyncio
async def test_category_slug_uniqueness(db_session: AsyncSession):
    """Verifies duplicate slug is rejected by unique constraint."""
    cat1 = Category(name="Giấy tờ", slug="giay-to")
    db_session.add(cat1)
    await db_session.commit()

    cat2 = Category(name="Giấy tờ xe", slug="giay-to")
    db_session.add(cat2)
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


# ==========================================
# 2. Post & Category Relationship Tests
# ==========================================

@pytest.mark.asyncio
async def test_post_linked_to_category(db_session: AsyncSession):
    """Verifies Post can be linked to Category and eager-loaded."""
    user = await create_user(db_session)
    cat = Category(name="Ví & Bóp", slug="vi-bop")
    db_session.add(cat)
    await db_session.commit()
    await db_session.refresh(cat)

    post = Post(
        user_id=user.id,
        type="LOST",
        title="Rơi ví Montblanc",
        description="Rơi tại sảnh tầng 1",
        category_id=cat.id,
    )
    db_session.add(post)
    await db_session.commit()
    await db_session.refresh(post)

    assert post.category_id == cat.id
    assert post.category is not None
    assert post.category.name == "Ví & Bóp"


@pytest.mark.asyncio
async def test_delete_category_sets_post_category_id_null(db_session: AsyncSession):
    """Verifies deleting Category sets post.category_id to NULL (ON DELETE SET NULL)."""
    user = await create_user(db_session)
    cat = Category(name="Chìa khóa", slug="chia-khoa")
    db_session.add(cat)
    await db_session.commit()
    await db_session.refresh(cat)

    post = Post(
        user_id=user.id,
        type="FOUND",
        title="Nhặt được chùm chìa khóa",
        description="Chùm chìa khóa có móc gấu bông",
        category_id=cat.id,
    )
    db_session.add(post)
    await db_session.commit()
    await db_session.refresh(post)

    # Delete category
    await db_session.delete(cat)
    await db_session.commit()

    # Re-fetch post
    await db_session.refresh(post)
    assert post.category_id is None


# ==========================================
# 3. Post Images Tests
# ==========================================

@pytest.mark.asyncio
async def test_post_with_multiple_images(db_session: AsyncSession):
    """Verifies a Post can have multiple public images ordered by display_order."""
    user = await create_user(db_session)
    user_id = user.id
    post = Post(
        user_id=user_id,
        type="LOST",
        title="Mất tai nghe Sony WH-1000XM5",
        description="Màu bạc, để quên tại phòng họp 302",
    )
    img1 = PostImage(image_url="https://cdn.findback.vn/p1.jpg", display_order=1)
    img0 = PostImage(image_url="https://cdn.findback.vn/p0.jpg", display_order=0)
    post.images = [img1, img0]

    db_session.add(post)
    await db_session.commit()
    post_id = post.id

    db_session.expunge_all()

    # Re-query post with images
    stmt = select(Post).where(Post.id == post_id)
    result = await db_session.execute(stmt)
    loaded_post = result.scalars().first()

    assert loaded_post is not None
    assert len(loaded_post.images) == 2
    # Ordered by display_order ASC
    assert loaded_post.images[0].display_order == 0
    assert loaded_post.images[0].image_url == "https://cdn.findback.vn/p0.jpg"
    assert loaded_post.images[1].display_order == 1
    assert loaded_post.images[1].image_url == "https://cdn.findback.vn/p1.jpg"


@pytest.mark.asyncio
async def test_delete_post_cascades_images(db_session: AsyncSession):
    """Verifies deleting a Post cascades to its PostImages."""
    user = await create_user(db_session)
    post = Post(
        user_id=user.id,
        type="FOUND",
        title="Nhặt được ô dù",
        description="Ô màu xanh lá",
    )
    db_session.add(post)
    await db_session.commit()
    await db_session.refresh(post)

    img = PostImage(post_id=post.id, image_url="https://cdn.findback.vn/umbrella.jpg", display_order=0)
    db_session.add(img)
    await db_session.commit()
    img_id = img.id

    # Delete post
    await db_session.delete(post)
    await db_session.commit()

    # Verify image is deleted
    stmt = select(PostImage).where(PostImage.id == img_id)
    res = await db_session.execute(stmt)
    assert res.scalars().first() is None


# ==========================================
# 4. GPS Coordinates & Mutual Pair Constraint Tests
# ==========================================

@pytest.mark.asyncio
async def test_gps_valid_coordinates(db_session: AsyncSession):
    """Verifies valid latitude and longitude persist and query accurately."""
    user = await create_user(db_session)
    post = Post(
        user_id=user.id,
        type="LOST",
        title="Rơi điện thoại iPhone 15",
        description="Tại khu vực cổng vòm",
        latitude=Decimal("21.028511"),
        longitude=Decimal("105.804817"),
    )
    db_session.add(post)
    await db_session.commit()
    await db_session.refresh(post)

    assert post.latitude == Decimal("21.028511")
    assert post.longitude == Decimal("105.804817")


@pytest.mark.asyncio
async def test_gps_both_null_allowed(db_session: AsyncSession):
    """Verifies both latitude and longitude can be NULL."""
    user = await create_user(db_session)
    post = Post(
        user_id=user.id,
        type="LOST",
        title="Rơi balo",
        description="Không rõ tọa độ chính xác",
        latitude=None,
        longitude=None,
    )
    db_session.add(post)
    await db_session.commit()
    await db_session.refresh(post)

    assert post.latitude is None
    assert post.longitude is None


@pytest.mark.asyncio
async def test_gps_latitude_out_of_range_rejected(db_session: AsyncSession):
    """Verifies latitude > 90 or < -90 is rejected by ck_posts_latitude."""
    user = await create_user(db_session)
    post = Post(
        user_id=user.id,
        type="LOST",
        title="Invalid Lat",
        description="Test latitude",
        latitude=Decimal("90.000001"),
        longitude=Decimal("105.000000"),
    )
    db_session.add(post)
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_gps_longitude_out_of_range_rejected(db_session: AsyncSession):
    """Verifies longitude > 180 or < -180 is rejected by ck_posts_longitude."""
    user = await create_user(db_session)
    post = Post(
        user_id=user.id,
        type="LOST",
        title="Invalid Lon",
        description="Test longitude",
        latitude=Decimal("21.000000"),
        longitude=Decimal("180.000001"),
    )
    db_session.add(post)
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_gps_coordinate_pair_constraint_rejected(db_session: AsyncSession):
    """Verifies only one coordinate being NULL violates ck_posts_coordinates."""
    user = await create_user(db_session)
    user_id = user.id

    # 1. Latitude provided, Longitude is NULL
    post1 = Post(
        user_id=user_id,
        type="LOST",
        title="Missing Lon",
        description="Latitude only",
        latitude=Decimal("21.028511"),
        longitude=None,
    )
    db_session.add(post1)
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()

    # 2. Longitude provided, Latitude is NULL
    post2 = Post(
        user_id=user_id,
        type="FOUND",
        title="Missing Lat",
        description="Longitude only",
        latitude=None,
        longitude=Decimal("105.804817"),
    )
    db_session.add(post2)
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


# ==========================================
# 5. Nullable Item Details Tests
# ==========================================

@pytest.mark.asyncio
async def test_nullable_item_details(db_session: AsyncSession):
    """Verifies brand, color, event_time can be populated or null."""
    user = await create_user(db_session)
    now = datetime.now(timezone.utc)

    # Populated
    post1 = Post(
        user_id=user.id,
        type="FOUND",
        title="Nhặt được đồng hồ",
        description="Đồng hồ kim loại",
        brand="Casio",
        color="Bạc",
        event_time=now,
    )
    db_session.add(post1)
    await db_session.commit()
    await db_session.refresh(post1)

    assert post1.brand == "Casio"
    assert post1.color == "Bạc"
    assert post1.event_time is not None

    # Nullable
    post2 = Post(
        user_id=user.id,
        type="LOST",
        title="Rơi sách",
        description="Sách giáo trình toán",
        brand=None,
        color=None,
        event_time=None,
    )
    db_session.add(post2)
    await db_session.commit()
    await db_session.refresh(post2)

    assert post2.brand is None
    assert post2.color is None
    assert post2.event_time is None


# ==========================================
# 6. KAN-32 Admin Compatibility Tests
# ==========================================

@pytest.mark.asyncio
async def test_admin_list_posts_with_new_schema(client: AsyncClient, db_session: AsyncSession):
    """Verifies GET /api/v1/admin/posts continues working with full schema posts."""
    admin = await create_user(db_session, role="ADMIN", email="admin_test@example.com")
    token = create_test_jwt(admin.id, role="ADMIN")
    headers = {"Authorization": f"Bearer {token}"}

    cat = Category(name="Thiết bị số", slug="thiet-bi-so")
    db_session.add(cat)
    await db_session.commit()
    await db_session.refresh(cat)

    post = Post(
        user_id=admin.id,
        type="LOST",
        title="Mất đồng hồ thông minh Garmin",
        description="Quên tại phòng gym",
        category_id=cat.id,
        location="Phòng gym F-Town",
        area="Quận 9",
        latitude=Decimal("10.841127"),
        longitude=Decimal("106.809883"),
        brand="Garmin",
        color="Đen",
        event_time=datetime.now(timezone.utc),
    )
    db_session.add(post)
    await db_session.commit()
    await db_session.refresh(post)

    img = PostImage(post_id=post.id, image_url="https://cdn.findback.vn/garmin.jpg")
    db_session.add(img)
    await db_session.commit()

    res = await client.get("/api/v1/admin/posts", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["pagination"]["total"] == 1
    item = data["items"][0]
    assert item["id"] == str(post.id)
    assert item["title"] == "Mất đồng hồ thông minh Garmin"
    assert item["status"] == "ACTIVE"


@pytest.mark.asyncio
async def test_admin_post_moderation_with_new_schema(client: AsyncClient, db_session: AsyncSession):
    """Verifies PATCH /api/v1/admin/posts/{id}/moderation works on posts with new schema fields."""
    admin = await create_user(db_session, role="ADMIN", email="mod_admin@example.com")
    author = await create_user(db_session, role="USER", email="post_author@example.com")
    token = create_test_jwt(admin.id, role="ADMIN")
    headers = {"Authorization": f"Bearer {token}"}

    cat = Category(name="Khác", slug="khac")
    db_session.add(cat)
    await db_session.commit()
    await db_session.refresh(cat)

    post = Post(
        user_id=author.id,
        type="LOST",
        title="Spam post cần ẩn",
        description="Nội dung vi phạm chính sách",
        category_id=cat.id,
        brand="Generic",
        latitude=Decimal("10.762622"),
        longitude=Decimal("106.660172"),
    )
    db_session.add(post)
    await db_session.commit()
    await db_session.refresh(post)

    res = await client.patch(
        f"/api/v1/admin/posts/{post.id}/moderation",
        json={"action": "HIDE", "reason": "Nội dung quảng cáo vi phạm quy định."},
        headers=headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["id"] == str(post.id)
    assert data["status"] == "HIDDEN"
    assert data["moderated_by"] == str(admin.id)
    assert data["moderation_reason"] == "Nội dung quảng cáo vi phạm quy định."

    # Verify audit log created
    stmt_audit = select(AuditLog).where(AuditLog.target_id == post.id)
    res_audit = await db_session.execute(stmt_audit)
    audit = res_audit.scalars().first()
    assert audit is not None
    assert audit.action == "HIDE"
    assert audit.actor_id == admin.id

    # Verify notification created for author
    stmt_notif = select(Notification).where(Notification.recipient_id == author.id)
    res_notif = await db_session.execute(stmt_notif)
    notif = res_notif.scalars().first()
    assert notif is not None
    assert notif.event_type == "POST_HIDDEN"


@pytest.mark.asyncio
async def test_delete_admin_who_moderated_post_is_restricted(db_session: AsyncSession):
    """Verifies that deleting an admin who moderated a post is rejected by ON DELETE RESTRICT."""
    admin = await create_user(db_session, role="ADMIN", email="admin_audit@example.com")
    author = await create_user(db_session, role="USER", email="author_audit@example.com")

    post = Post(
        user_id=author.id,
        type="LOST",
        title="Bản tin vi phạm",
        description="Nội dung đã bị admin kiểm duyệt",
        status="HIDDEN",
        moderated_by=admin.id,
        moderated_at=datetime.now(timezone.utc),
        moderation_reason="Vi phạm điều khoản cộng đồng.",
    )
    db_session.add(post)
    await db_session.commit()

    # Attempt to delete the admin user who moderated the post
    await db_session.delete(admin)
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()
