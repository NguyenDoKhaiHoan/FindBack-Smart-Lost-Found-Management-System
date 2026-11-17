from datetime import datetime, timezone
from typing import Any
import uuid
from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class AuditLog(Base):
    """
    Audit log persistence model for sensitive administrative and moderation actions.

    Records:
    - actor_id: admin who performed the action.
    - action: operation identifier (e.g. HIDE).
    - target_type: entity category (e.g. POST).
    - target_id: UUID of the affected entity.
    - reason: administrative justification.
    - old_status / new_status: state transition tracking.
    """
    __tablename__ = "audit_logs"

    __table_args__ = (
        Index("ix_audit_logs_actor", "actor_id", text("created_at DESC")),
        Index("ix_audit_logs_target", "target_type", "target_id", text("created_at DESC")),
        Index("ix_audit_logs_created", text("created_at DESC")),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    actor_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", name="fk_audit_logs_actor", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    action: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    target_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    target_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        nullable=False,
        index=True,
    )
    reason: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    old_status: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )
    new_status: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(
        "metadata",
        JSON().with_variant(JSONB, "postgresql"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=text("CURRENT_TIMESTAMP"),
    )

    actor = relationship("User", foreign_keys=[actor_id], lazy="raise")
