from datetime import timezone
from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, Field, field_validator, model_validator
from sqlalchemy import func, select, true
from sqlalchemy.orm import Session, aliased, contains_eager

from app.modules.matching.repositories.database import project_post
from app.modules.matching.schemas.contracts import (
    Color,
    Pagination,
    PublicPost,
    Schema,
    normalize_attribute,
)
from app.modules.matching.services.scoring import tokens
from app.modules.posts.models.post import Category, Post
from app.modules.posts.repositories.posts import public_post_query
from app.modules.posts.services.catalog import LOCATIONS
from app.shared.errors import DomainError

SearchSort = Literal["newest", "oldest", "event_desc", "event_asc"]


class SearchQuery(Schema):
    q: str | None = Field(default=None, max_length=200)
    type: Literal["LOST", "FOUND"] | None = None
    category_id: UUID | None = None
    location_code: str | None = Field(
        default=None, pattern=r"^[A-Z0-9]+(?:[_-][A-Z0-9]+)*$", max_length=50
    )
    event_from: AwareDatetime | None = None
    event_to: AwareDatetime | None = None
    status: Literal["OPEN", "CLOSED"] | None = None
    color_code: Color | None = None
    brand: str | None = Field(default=None, min_length=1, max_length=100)
    material: str | None = Field(default=None, min_length=1, max_length=100)
    page: int = Field(default=1, ge=1, le=10000)
    page_size: int = Field(default=20, ge=1, le=100)
    sort: SearchSort = "newest"

    @field_validator("event_from", "event_to", mode="before")
    @classmethod
    def require_rfc3339(cls, value):
        if value is not None and (not isinstance(value, str) or "T" not in value):
            raise ValueError("Use an RFC 3339 timestamp with a timezone")
        return value

    @model_validator(mode="after")
    def check_filters(self):
        if self.event_from and self.event_to and self.event_from >= self.event_to:
            raise ValueError("event_from must be earlier than event_to")
        for attr in (self.brand, self.material):
            if attr is not None and not normalize_attribute(attr):
                raise ValueError("Brand and material must not be blank")
        return self


class SearchResponse(Schema):
    items: list[PublicPost]
    pagination: Pagination
    sort: SearchSort


def ordering(model, sort: SearchSort):
    if sort == "newest":
        return model.created_at.desc(), model.id.asc()
    if sort == "oldest":
        return model.created_at.asc(), model.id.asc()
    if sort == "event_desc":
        return model.event_time.desc(), model.id.asc()
    return model.event_time.asc(), model.id.asc()


def search_posts(db: Session, query: SearchQuery) -> SearchResponse:
    if query.category_id is not None and db.get(Category, query.category_id) is None:
        raise DomainError(
            422,
            "UNKNOWN_FILTER_VALUE",
            "Unknown category",
            [{"field": "category_id", "issue": "Unknown category"}],
        )
    if query.location_code is not None and query.location_code not in LOCATIONS:
        raise DomainError(
            422,
            "UNKNOWN_FILTER_VALUE",
            "Unknown location",
            [{"field": "location_code", "issue": "Unknown location"}],
        )
    filtered = public_post_query().where(
        Post.category_id.is_not(None),
        Post.event_time.is_not(None),
        Post.location_code.is_not(None),
        Post.title.is_not(None),
        Post.description.is_not(None),
    )
    for key in (
        "type",
        "category_id",
        "location_code",
        "status",
        "color_code",
        "brand",
        "material",
    ):
        value = getattr(query, key)
        if value is not None:
            if key in ("brand", "material"):
                value = normalize_attribute(value)
            filtered = filtered.where(getattr(Post, key) == value)
    if query.event_from is not None:
        filtered = filtered.where(Post.event_time >= query.event_from.astimezone(timezone.utc))
    if query.event_to is not None:
        filtered = filtered.where(Post.event_time < query.event_to.astimezone(timezone.utc))
    for word in tokens(query.q or ""):
        filtered = filtered.where(Post.search_text.contains(f" {word} ", autoescape=True))

    total_query = select(func.count().label("total")).select_from(filtered.subquery()).subquery()
    page_query = (
        filtered.order_by(*ordering(Post, query.sort))
        .offset((query.page - 1) * query.page_size)
        .limit(query.page_size)
        .subquery()
    )
    page_post = aliased(Post, page_query)
    rows = db.execute(
        select(page_post, total_query.c.total)
        .select_from(total_query)
        .outerjoin(page_post, true())
        .outerjoin(Category, Category.id == page_post.category_id)
        .options(contains_eager(page_post.category))
        .order_by(*ordering(page_post, query.sort))
    ).all()
    total = rows[0].total
    pages = (total + query.page_size - 1) // query.page_size
    return SearchResponse(
        items=[item for post, _ in rows if post is not None and (item := project_post(post))],
        pagination=Pagination(
            page=query.page,
            page_size=query.page_size,
            total=total,
            total_pages=pages,
            has_next=query.page < pages,
            has_previous=query.page > 1 and total > 0,
        ),
        sort=query.sort,
    )
