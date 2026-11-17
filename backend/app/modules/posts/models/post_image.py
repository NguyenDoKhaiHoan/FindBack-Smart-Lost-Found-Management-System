from datetime import datetime, timezone
import uuid
from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class PostImage(Base):
    """
    Public images associated with a Post.

    Owned by Posts module (TV2):
    - ID uses RFC 4122 UUID.
    - post_id references posts.id ON DELETE CASCADE.
    - image_url stores public storage URL/key.
    - Must NOT store private claim evidence.
    """
    __tablename__ = "post_images"

    __table_args__ = (
        Index("ix_post_images_post_id", "post_id"),
        Index("ix_post_images_post_order", "post_id", "display_order"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    post_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("posts.id", name="fk_post_images_post", ondelete="CASCADE"),
        nullable=False,
    )
    image_url: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )
    display_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=text("CURRENT_TIMESTAMP"),
    )

    post = relationship("Post", back_populates="images")
