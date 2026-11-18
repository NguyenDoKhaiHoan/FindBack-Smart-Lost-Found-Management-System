from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import JSON, CheckConstraint, ForeignKey, Index, Integer, String, Text, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base, UTCDateTime, utcnow


class Claim(Base):
    __tablename__ = "claims"
    __table_args__ = (
        CheckConstraint(
            "status IN ('PENDING','APPROVED','REJECTED','RETURNED')", name="ck_claim_status"
        ),
        CheckConstraint("version >= 1", name="ck_claim_version"),
        CheckConstraint(
            "(status = 'PENDING' AND decided_by IS NULL AND decided_at IS NULL) OR "
            "(status <> 'PENDING' AND decided_by IS NOT NULL AND decided_at IS NOT NULL)",
            name="ck_claim_decision",
        ),
        CheckConstraint(
            "(status = 'REJECTED' AND rejection_reason IS NOT NULL "
            "AND length(trim(rejection_reason)) > 0) OR "
            "(status <> 'REJECTED' AND rejection_reason IS NULL)",
            name="ck_claim_rejection",
        ),
        CheckConstraint(
            "(status = 'RETURNED' AND returned_by IS NOT NULL "
            "AND returned_by = claimant_id AND returned_at IS NOT NULL) OR "
            "(status <> 'RETURNED' AND returned_by IS NULL AND returned_at IS NULL)",
            name="ck_claim_return",
        ),
        Index(
            "uq_claim_active_pair",
            "found_post_id",
            "claimant_id",
            unique=True,
            postgresql_where=text("status IN ('PENDING','APPROVED')"),
            sqlite_where=text("status IN ('PENDING','APPROVED')"),
        ),
        Index(
            "uq_claim_post_winner",
            "found_post_id",
            unique=True,
            postgresql_where=text("status IN ('APPROVED','RETURNED')"),
            sqlite_where=text("status IN ('APPROVED','RETURNED')"),
        ),
        Index("ix_claim_claimant_created", "claimant_id", "created_at", "id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    found_post_id: Mapped[UUID] = mapped_column(ForeignKey("findback_api.posts.id"), index=True)
    claimant_id: Mapped[UUID] = mapped_column(ForeignKey("findback_api.users.id"))
    status: Mapped[str] = mapped_column(String(12), default="PENDING")
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    decided_by: Mapped[UUID | None] = mapped_column(ForeignKey("findback_api.users.id"))
    decided_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    rejection_reason: Mapped[str | None] = mapped_column(Text)
    returned_by: Mapped[UUID | None] = mapped_column(ForeignKey("findback_api.users.id"))
    returned_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    return_summary: Mapped["ReturnRecord | None"] = relationship(lazy="raise")


class ClaimEvidence(Base):
    __tablename__ = "claim_evidence"
    __table_args__ = (
        CheckConstraint("length(trim(private_content)) > 0", name="ck_evidence_content"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    claim_id: Mapped[UUID] = mapped_column(ForeignKey("findback_api.claims.id"), index=True)
    private_content: Mapped[str] = mapped_column(Text)
    # Legacy private file paths are intentionally never exposed in response models.
    file_path: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class ReturnRecord(Base):
    __tablename__ = "returns"
    __table_args__ = (
        CheckConstraint(
            "status IN ('ARRANGED','HANDED_OVER','CONFIRMED')", name="ck_return_status"
        ),
        CheckConstraint(
            "confirmed_by IS NULL OR (status = 'CONFIRMED' AND confirmed_at IS NOT NULL)",
            name="ck_return_confirmation_actor",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    claim_id: Mapped[UUID] = mapped_column(ForeignKey("findback_api.claims.id"), unique=True)
    status: Mapped[str] = mapped_column(String(12))
    arranged_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    scheduled_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    meeting_note: Mapped[str | None] = mapped_column(Text)
    handed_over_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    confirmed_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    confirmed_by: Mapped[UUID | None] = mapped_column(ForeignKey("findback_api.users.id"))


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    actor_id: Mapped[UUID] = mapped_column(ForeignKey("findback_api.users.id"))
    action: Mapped[str] = mapped_column(String(32))
    claim_id: Mapped[UUID] = mapped_column(ForeignKey("findback_api.claims.id"))
    found_post_id: Mapped[UUID] = mapped_column(ForeignKey("findback_api.posts.id"))
    previous_version: Mapped[int | None] = mapped_column(Integer)
    version: Mapped[int] = mapped_column(Integer)
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class OutboxEvent(Base):
    __tablename__ = "outbox_events"

    event_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    type: Mapped[str] = mapped_column(String(32))
    payload: Mapped[dict] = mapped_column(JSON)
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
