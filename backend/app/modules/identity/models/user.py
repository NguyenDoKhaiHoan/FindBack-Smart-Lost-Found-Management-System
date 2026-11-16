from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, CheckConstraint, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base, UTCDateTime


class User(Base):
    """Minimal Identity persistence adapter; no public account management API."""

    __tablename__ = "users"
    __table_args__ = (CheckConstraint("token_version >= 1", name="ck_user_token_version"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    role: Mapped[str] = mapped_column(String(20), default="USER")
    token_version: Mapped[int] = mapped_column(Integer, default=1)


class RevokedToken(Base):
    __tablename__ = "revoked_tokens"

    jti: Mapped[str] = mapped_column(String(128), primary_key=True)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
