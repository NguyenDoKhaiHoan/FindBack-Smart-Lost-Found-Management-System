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
    completed_claim_id: Mapped[UUID | None] = mapped_column(
        ForeignKey(
            "findback_api.claims.id",
            name="fk_post_completed_claim",
            use_alter=True,
        )
    )
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime)


def can_accept_claims(post: Post) -> bool:
    return (
        post.status == "OPEN"
        and post.completed_claim_id is None
        and not post.is_hidden
        and post.deleted_at is None
    )
