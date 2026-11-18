from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer, Numeric, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base, UTCDateTime, utcnow


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Post(Base):
    __tablename__ = "posts"
    __table_args__ = (
        CheckConstraint("type IN ('FOUND', 'LOST')", name="ck_post_type"),
        CheckConstraint("status IN ('OPEN', 'CLOSED')", name="ck_post_status"),
        CheckConstraint(
            "(completed_claim_id IS NULL AND completed_at IS NULL) OR "
            "(status = 'CLOSED' AND completed_claim_id IS NOT NULL AND completed_at IS NOT NULL)",
            name="ck_post_completion",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    owner_id: Mapped[UUID] = mapped_column(ForeignKey("findback_api.users.id"), index=True)
    type: Mapped[str] = mapped_column(String(10), default="FOUND")
    status: Mapped[str] = mapped_column(String(10), default="OPEN")
    is_hidden: Mapped[bool] = mapped_column(Boolean, default=False)
    deleted_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    category_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("findback_api.categories.id"), index=True
    )
    category: Mapped[Category | None] = relationship(lazy="raise")
    title: Mapped[str | None] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    location: Mapped[str | None] = mapped_column(String(255))
    area: Mapped[str | None] = mapped_column(String(100))
    location_code: Mapped[str | None] = mapped_column(String(50))
    event_time: Mapped[datetime | None] = mapped_column(UTCDateTime)
    brand: Mapped[str | None] = mapped_column(String(100))
    material: Mapped[str | None] = mapped_column(String(100))
    color: Mapped[str | None] = mapped_column(String(50))
    color_code: Mapped[str | None] = mapped_column(String(20))
    latitude: Mapped[float | None] = mapped_column(Numeric(9, 6))
    longitude: Mapped[float | None] = mapped_column(Numeric(9, 6))
    search_text: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    moderated_by: Mapped[UUID | None] = mapped_column(ForeignKey("findback_api.users.id"))
    moderated_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    moderation_reason: Mapped[str | None] = mapped_column(Text)
    images: Mapped[list["PostImage"]] = relationship(lazy="raise", order_by="PostImage.sort_order")
    completed_claim_id: Mapped[UUID | None] = mapped_column(
        ForeignKey(
            "findback_api.claims.id",
            name="fk_post_completed_claim",
            use_alter=True,
        )
    )
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime)

    @property
    def user_id(self) -> UUID:
        return self.owner_id

    @property
    def display_status(self) -> str:
        return "HIDDEN" if self.is_hidden or self.deleted_at else self.status


class PostImage(Base):
    __tablename__ = "post_images"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    post_id: Mapped[UUID] = mapped_column(ForeignKey("findback_api.posts.id"), index=True)
    original_name: Mapped[str] = mapped_column(String(255))
    mime_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(Integer)
    sort_order: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    @property
    def file_path(self) -> str:
        return f"/api/v1/posts/{self.post_id}/images/{self.id}"


def can_accept_claims(post: Post) -> bool:
    return (
        post.status == "OPEN"
        and post.completed_claim_id is None
        and not post.is_hidden
        and post.deleted_at is None
    )
