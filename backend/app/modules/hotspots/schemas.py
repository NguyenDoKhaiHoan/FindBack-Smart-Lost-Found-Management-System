from datetime import date, timedelta
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.posts.services.catalog import HotspotZone, LocationCode

Density = Literal["low", "medium", "high", "very_high"]
Scope = Literal["public", "admin"]
GroupBy = Literal["day", "week", "month"]


class HotspotQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    period: Literal["7", "30", "90"] | None = None
    start_date: date | None = Field(default=None, ge=date(2000, 1, 1))
    end_date: date | None = Field(default=None, le=date(2199, 12, 31))
    category_id: UUID | None = None
    location_id: LocationCode | None = None
    zone: HotspotZone | None = None
    group_by: GroupBy = "day"

    @model_validator(mode="after")
    def dates(self):
        if self.start_date is None and self.end_date is None:
            return self
        if (
            self.period
            or self.start_date is None
            or self.end_date is None
            or not timedelta(0) <= self.end_date - self.start_date < timedelta(days=180)
        ):
            raise ValueError("Use a period or both dates spanning at most 180 days")
        return self


class AlgorithmConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    eps_meters: int = Field(default=200, ge=50, le=1000)
    min_samples: int = Field(default=5, ge=3, le=50)
    period_days: int = Field(default=30, ge=7, le=90)
    medium_count: int = Field(default=10, ge=4, le=500)
    high_count: int = Field(default=20, ge=5, le=750)
    very_high_count: int = Field(default=35, ge=6, le=1000)

    @model_validator(mode="after")
    def density_order(self):
        if not self.min_samples <= self.medium_count < self.high_count < self.very_high_count:
            raise ValueError("Use increasing thresholds at or above min_samples")
        return self


class ConfigPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    eps_meters: int | None = None
    min_samples: int | None = None
    period_days: int | None = None
    medium_count: int | None = None
    high_count: int | None = None
    very_high_count: int | None = None


class Count(BaseModel):
    label: str
    count: int


class Trend(BaseModel):
    previous_count: int
    change_percent: float


class Window(BaseModel):
    start_date: date
    end_date: date


class HeatPoint(BaseModel):
    latitude: float
    longitude: float
    event_count: int
    density_level: Density


class Cluster(HeatPoint):
    cluster_id: str
    location_name: str
    top_categories: list[Count]
    peak_time: Count | None
    timeline: list[Count]
    trend: Trend | None


class Statistics(BaseModel):
    total_events: int
    total_hotspots: int
    high_density_areas: int
    noise_events: int | None
    top_areas: list[Count]
    categories: list[Count]
    hours: list[Count]
    regions: list[Count]
    timeline: list[Count]
    trend: Trend | None


class Analysis(BaseModel):
    period: Window
    previous_period: Window
    is_demo: bool
    truncated: bool
    statistics: Statistics
    clusters: list[Cluster]
    heatmap: list[HeatPoint]
    insights: list[str]


class RelatedPost(BaseModel):
    id: UUID
    title: str
    event_day: date


class ClusterDetail(Cluster):
    related_posts: list[RelatedPost]


class HeatmapResponse(BaseModel):
    is_demo: bool
    heatmap: list[HeatPoint]
