from datetime import datetime, timezone
from typing import Any
import uuid
from sqlalchemy import (
    Boolean, CheckConstraint, DateTime, ForeignKey, Index, String, Text, Uuid, text
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Notification(Base):
    """
    Notification model for the FindBack application.

    Adheres strictly to KAN-30 API Contract and NOTIFICATION_EVENT_CONTRACT.md:
    - ID and recipient_id use UUID.
    - event_id is recorded for deduplication/idempotency.
    - resource_type & resource_id provide safe polymorphic referencing to Claims, Posts, etc.
    """
    __tablename__ = "notifications"

    __table_args__ = (
        CheckConstraint(
            "resource_type IS NULL OR resource_type IN ('CLAIM', 'POST', 'RETURN', 'REPORT', 'MATCH')",
            name="ck_notifications_resource_type",
        ),
        CheckConstraint(
            "(resource_type IS NULL AND resource_id IS NULL) OR "
            "(resource_type IS NOT NULL AND resource_id IS NOT NULL)",
            name="ck_notifications_resource_pair",
        ),
        CheckConstraint(
            "(is_read = FALSE AND read_at IS NULL) OR "
            "(is_read = TRUE AND read_at IS NOT NULL)",
            name="ck_notifications_read_state",
        ),
        CheckConstraint(
            "length(trim(event_type)) > 0",
            name="ck_notifications_event_type_not_empty",
        ),
        CheckConstraint(
            "length(trim(title)) > 0",
            name="ck_notifications_title_not_empty",
        ),
        Index(
            "ix_notifications_recipient_created",
            "recipient_id",
            text("created_at DESC"),
        ),
        Index(
            "ix_notifications_unread",
            "recipient_id",
            text("created_at DESC"),
            postgresql_where=text("is_read = FALSE"),
            sqlite_where=text("is_read = 0"),
        ),
        Index(
            "ix_notifications_event_id_unique",
            "event_id",
            unique=True,
            postgresql_where=text("event_id IS NOT NULL"),
            sqlite_where=text("event_id IS NOT NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    recipient_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", name="fk_notifications_recipient", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        nullable=True,
        doc="Unique identifier from producer for idempotency and deduplication",
    )
    event_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    message: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    resource_type: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
    )
    resource_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        nullable=True,
    )
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(
        "metadata",
        JSON().with_variant(JSONB, "postgresql"),
        nullable=True,
    )
    is_read: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("FALSE"),
    )
    read_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=text("CURRENT_TIMESTAMP"),
    )

    # Optional relationship to shared User
    recipient = relationship("User", foreign_keys=[recipient_id], lazy="raise")
