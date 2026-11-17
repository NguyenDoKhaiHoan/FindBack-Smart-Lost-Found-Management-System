from datetime import datetime, timezone
import uuid
from sqlalchemy import DateTime, String, Text, UniqueConstraint, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Category(Base):
    """
    Canonical Category persistence model for FindBack.

    Owned by Posts module (TV2):
    - ID uses RFC 4122 UUID.
    - name: Category display name.
    - slug: Unique slug for URL routing and indexing.
    - description: Optional text description.
    - Dynamic categories (not fixed enum) per project specifications.
    """
    __tablename__ = "categories"

    __table_args__ = (
        UniqueConstraint("slug", name="uq_categories_slug"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    slug: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(
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

    posts = relationship("Post", back_populates="category", lazy="raise")
