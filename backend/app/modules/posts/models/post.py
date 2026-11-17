from datetime import datetime, timezone
from decimal import Decimal
from typing import TYPE_CHECKING
import uuid
from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.modules.identity.models.user import User
    from app.modules.posts.models.category import Category
    from app.modules.posts.models.post_image import PostImage


class Post(Base):
    """
    Canonical Post persistence model for the FindBack Modular Monolith.

    Owned by Posts module (TV2) and consumed by Notifications & Admin (TV5) for moderation:
    - ID uses RFC 4122 UUID.
    - user_id references shared users table.
    - category_id references dynamic categories table.
    - Type is strictly LOST or FOUND.
    - Status is DRAFT, ACTIVE, HIDDEN, or CLOSED.
    - Optional geographic coordinates (latitude, longitude) with mutual pair constraints.
    - Optional item details (brand, color, event_time).
    - Public images relation (cascading delete on post deletion).
    - Moderation fields record admin moderation details.
    """
    __tablename__ = "posts"

    __table_args__ = (
        CheckConstraint(
            "type IN ('LOST', 'FOUND')",
            name="ck_posts_type",
        ),
        CheckConstraint(
            "status IN ('DRAFT', 'ACTIVE', 'HIDDEN', 'CLOSED')",
            name="ck_posts_status",
        ),
        CheckConstraint(
            "length(trim(title)) > 0",
            name="ck_posts_title_not_empty",
        ),
        CheckConstraint(
            "length(trim(description)) > 0",
            name="ck_posts_description_not_empty",
        ),
        CheckConstraint(
            "(moderated_by IS NULL AND moderated_at IS NULL AND moderation_reason IS NULL) OR "
            "(moderated_by IS NOT NULL AND moderated_at IS NOT NULL AND length(trim(moderation_reason)) > 0)",
            name="ck_posts_moderation",
        ),
        CheckConstraint(
            "latitude IS NULL OR (latitude BETWEEN -90.0 AND 90.0)",
            name="ck_posts_latitude",
        ),
        CheckConstraint(
            "longitude IS NULL OR (longitude BETWEEN -180.0 AND 180.0)",
            name="ck_posts_longitude",
        ),
        CheckConstraint(
            "(latitude IS NULL) = (longitude IS NULL)",
            name="ck_posts_coordinates",
        ),
        Index("ix_posts_status", "status"),
        Index("ix_posts_type", "type"),
        Index("ix_posts_category_id", "category_id"),
        Index("ix_posts_created_at", text("created_at DESC")),
        Index("ix_posts_admin_list", "status", "type", text("created_at DESC")),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", name="fk_posts_user", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    type: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("categories.id", name="fk_posts_category", ondelete="SET NULL"),
        nullable=True,
    )
    location: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    area: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    latitude: Mapped[Decimal | None] = mapped_column(
        Numeric(9, 6),
        nullable=True,
    )
    longitude: Mapped[Decimal | None] = mapped_column(
        Numeric(9, 6),
        nullable=True,
    )
    brand: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    color: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    event_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="ACTIVE",
        server_default=text("'ACTIVE'"),
    )
    moderated_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", name="fk_posts_moderated_by", ondelete="RESTRICT"),
        nullable=True,
    )
    moderated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    moderation_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=text("CURRENT_TIMESTAMP"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        server_default=text("CURRENT_TIMESTAMP"),
    )

    user: Mapped["User"] = relationship("User", foreign_keys=[user_id], lazy="raise")
    moderator: Mapped["User | None"] = relationship("User", foreign_keys=[moderated_by], lazy="raise")
    category: Mapped["Category | None"] = relationship("Category", back_populates="posts", lazy="selectin")
    images: Mapped[list["PostImage"]] = relationship(
        "PostImage",
        back_populates="post",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="PostImage.display_order",
    )
