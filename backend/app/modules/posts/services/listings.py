from datetime import timezone
from uuid import UUID

from sqlalchemy import exists, func, select
from sqlalchemy.orm import Session, selectinload

from app.db.session import utcnow
from app.modules.claims_returns.models.claim import Claim
from app.modules.matching.schemas.contracts import normalize_attribute
from app.modules.matching.services.scoring import tokens
from app.modules.posts.models.post import Category, Post
from app.modules.posts.repositories.posts import PostRepository, public_post_query
from app.modules.posts.schemas.post import (
    PostCreate,
    PostListQuery,
    PostListResponse,
    PostResponse,
    PostUpdate,
)
from app.modules.posts.services.catalog import LOCATIONS
from app.shared.errors import DomainError


def list_posts(
    db: Session, query: PostListQuery, *, owner_id: UUID | None = None
) -> PostListResponse:
    stmt = (
        public_post_query()
        if owner_id is None
        else select(Post).where(Post.owner_id == owner_id, Post.deleted_at.is_(None))
    )
    if query.type is not None:
        stmt = stmt.where(Post.type == query.type.value)
    if query.category_id is not None:
        stmt = stmt.where(Post.category_id == query.category_id)
    if query.area is not None:
        stmt = stmt.where(func.lower(Post.area) == query.area.strip().lower())
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    items = db.scalars(
        stmt.order_by(Post.created_at.desc(), Post.id.desc())
        .offset((query.page - 1) * query.page_size)
        .limit(query.page_size)
    ).all()
    return PostListResponse(
        items=items,
        page=query.page,
        page_size=query.page_size,
        total=total,
        total_pages=(total + query.page_size - 1) // query.page_size,
    )


def create_post(db: Session, payload: PostCreate, owner_id: UUID) -> PostResponse:
    values = payload.model_dump()
    values["type"] = payload.type.value
    check_values(db, values)
    normalize_hotspot_location(values)
    values["location_code"] = values["location_code"] or "OTHER"
    post = Post(owner_id=owner_id, images=[], **values)
    update_search_text(post)
    db.add(post)
    db.flush()
    result = PostResponse.model_validate(post)
    db.commit()
    return result


def check_values(db: Session, values: dict) -> None:
    if "category_id" in values:
        category = db.get(Category, values["category_id"])
        if category is None or not category.is_active:
            raise DomainError(422, "INVALID_CATEGORY", "An active category is required")
    code = values.get("location_code")
    if code is not None and code not in LOCATIONS:
        raise DomainError(422, "INVALID_LOCATION_CODE", "Unknown location code")
    for key in ("brand", "material"):
        if values.get(key):
            values[key] = normalize_attribute(values[key]) or None
    if event_time := values.get("event_time"):
        values["event_time"] = event_time.astimezone(timezone.utc)


def update_search_text(post: Post) -> None:
    words = sorted(
        tokens(" ".join(value for value in (post.item_name, post.title, post.description) if value))
    )
    post.search_text = f" {' '.join(words)} "


def normalize_hotspot_location(values: dict, post: Post | None = None) -> None:
    zone = values.get("hotspot_zone", post.hotspot_zone if post else None)
    if zone is None:
        return
    lat = values.get("latitude", post.latitude if post else None)
    lon = values.get("longitude", post.longitude if post else None)
    if (post.type if post else values["type"]) != "LOST" or lat is None or lon is None:
        raise DomainError(422, "INVALID_HOTSPOT_LOCATION", "Choose a map pin for a lost-item post")
    if {"hotspot_zone", "latitude", "longitude"} & values.keys():
        lat, lon = round(lat, 3), round(lon, 3)
        if (lat, lon) == (0, 0):
            raise DomainError(422, "INVALID_HOTSPOT_LOCATION", "Choose a valid map pin")
        values.update(latitude=lat, longitude=lon)


def lock_editable_post(
    db: Session, post_id: UUID, owner_id: UUID, *, check_claims: bool = True
) -> Post:
    post = PostRepository(db).get_for_update(post_id)
    if post is None or post.deleted_at is not None:
        raise DomainError(404, "POST_NOT_FOUND", "Post not found")
    if post.owner_id != owner_id:
        raise DomainError(403, "POST_OWNER_REQUIRED", "Only the owner may change the post")
    if post.status != "OPEN" or post.is_hidden:
        raise DomainError(409, "POST_STATE_CONFLICT", "Post is not editable")
    if check_claims and db.scalar(
        select(
            exists().where(
                Claim.found_post_id == post.id, Claim.status.in_(("PENDING", "APPROVED"))
            )
        )
    ):
        raise DomainError(409, "POST_HAS_ACTIVE_CLAIM", "Post has an active claim")
    return post


def edit_post(db: Session, post_id: UUID, owner_id: UUID, payload: PostUpdate) -> PostResponse:
    post = lock_editable_post(db, post_id, owner_id)
    values = payload.model_dump(exclude_unset=True)
    check_values(db, values)
    normalize_hotspot_location(values, post)
    if "location_code" in values and values["location_code"] is None:
        values["location_code"] = "OTHER"
    for name, value in values.items():
        setattr(post, name, value)
    post.updated_at = utcnow()
    update_search_text(post)
    db.flush()
    db.scalar(select(Post).where(Post.id == post.id).options(selectinload(Post.images)))
    result = PostResponse.model_validate(post)
    db.commit()
    return result


def delete_post(db: Session, post_id: UUID, owner_id: UUID) -> None:
    post = lock_editable_post(db, post_id, owner_id)
    post.updated_at = post.deleted_at = utcnow()
    db.commit()
