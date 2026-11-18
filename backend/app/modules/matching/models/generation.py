from datetime import datetime
from uuid import UUID

from sqlalchemy import JSON, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base, UTCDateTime


class MatchGeneration(Base):
    __tablename__ = "match_generations"

    source_id: Mapped[UUID] = mapped_column(ForeignKey("findback_api.posts.id"), primary_key=True)
    rule_version: Mapped[str] = mapped_column(String(50))
    calculated_at: Mapped[datetime] = mapped_column(UTCDateTime)
    fingerprints: Mapped[dict] = mapped_column(JSON)


class MatchResult(Base):
    __tablename__ = "match_results"

    source_id: Mapped[UUID] = mapped_column(
        ForeignKey("findback_api.match_generations.source_id", ondelete="CASCADE"), primary_key=True
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, index=True)
    score_data: Mapped[dict] = mapped_column(JSON)
