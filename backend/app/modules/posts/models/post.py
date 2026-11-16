from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base, UTCDateTime


class Post(Base):
    """Minimal Posts integration adapter, kept separate from draft SQL schemas."""

    __tablename__ = "posts"
    __table_args__ = (
        CheckConstraint("type IN ('FOUND', 'LOST')", name="ck_post_type"),
        CheckConstraint("status IN ('OPEN', 'CLOSED')", name="ck_post_status"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    owner_id: Mapped[UUID] = mapped_column(ForeignKey("findback_api.users.id"), index=True)
    type: Mapped[str] = mapped_column(String(10), default="FOUND")
    status: Mapped[str] = mapped_column(String(10), default="OPEN")
    is_hidden: Mapped[bool] = mapped_column(Boolean, default=False)
    deleted_at: Mapped[datetime | None] = mapped_column(UTCDateTime)


def can_accept_claims(post: Post) -> bool:
    return post.status == "OPEN" and not post.is_hidden and post.deleted_at is None
