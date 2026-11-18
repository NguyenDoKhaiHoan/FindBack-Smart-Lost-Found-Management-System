from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, Text, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base, UTCDateTime, utcnow


class Report(Base):
    __tablename__ = "reports"
    __table_args__ = (
        CheckConstraint(
            "status IN ('PENDING','REVIEWING','RESOLVED','DISMISSED')", name="ck_report_status"
        ),
        Index(
            "uq_open_report_per_user_post",
            "reporter_id",
            "post_id",
            unique=True,
            postgresql_where=text("status IN ('PENDING','REVIEWING')"),
            sqlite_where=text("status IN ('PENDING','REVIEWING')"),
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    reporter_id: Mapped[UUID] = mapped_column(ForeignKey("findback_api.users.id"))
    post_id: Mapped[UUID] = mapped_column(ForeignKey("findback_api.posts.id"), index=True)
    reason: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(12), default="PENDING", index=True)
    resolution_note: Mapped[str | None] = mapped_column(Text)
    reviewed_by: Mapped[UUID | None] = mapped_column(ForeignKey("findback_api.users.id"))
    reviewed_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class ModerationAudit(Base):
    __tablename__ = "moderation_audit_logs"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    actor_id: Mapped[UUID] = mapped_column(ForeignKey("findback_api.users.id"))
    post_id: Mapped[UUID] = mapped_column(ForeignKey("findback_api.posts.id"))
    report_id: Mapped[UUID | None] = mapped_column(ForeignKey("findback_api.reports.id"))
    action: Mapped[str] = mapped_column(String(30))
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
