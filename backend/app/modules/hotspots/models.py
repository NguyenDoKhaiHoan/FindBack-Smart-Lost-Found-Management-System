from sqlalchemy import Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class HotspotSettings(Base):
    __tablename__ = "hotspot_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    eps_meters: Mapped[int]
    min_samples: Mapped[int]
    period_days: Mapped[int]
    medium_count: Mapped[int]
    high_count: Mapped[int]
    very_high_count: Mapped[int]
