from datetime import datetime, timezone
import uuid
from sqlalchemy import CheckConstraint, DateTime, String, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class User(Base):
    """
    Shared User persistence model for the FindBack Modular Monolith.

    This model serves as the foundational user entity for Identity,
    Notifications, Posts, and Claims modules to prevent duplicate user tables.
    All primary keys across the system reference this UUID id.
    """
    __tablename__ = "users"

    __table_args__ = (
        CheckConstraint(
            "role IN ('USER', 'ADMIN', 'user', 'admin')",
            name="ck_users_role",
        ),
        CheckConstraint(
            "status IN ('ACTIVE', 'SUSPENDED', 'DISABLED')",
            name="ck_users_status",
        ),
        CheckConstraint(
            "length(trim(email)) > 0 AND email = lower(trim(email))",
            name="ck_users_email_normalized",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
    )
    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="USER",
        server_default=text("'USER'"),
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="ACTIVE",
        server_default=text("'ACTIVE'"),
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

    @property
    def is_active(self) -> bool:
        return self.status == "ACTIVE"

    @property
    def is_admin(self) -> bool:
        return self.role.upper() == "ADMIN"
