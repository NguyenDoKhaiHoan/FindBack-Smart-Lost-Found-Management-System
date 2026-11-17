"""Explicit public projection: adapters must never pass private Posts/Claims models."""
from datetime import datetime, timezone
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Schema(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Category(Schema):
    id: UUID
    name: str = Field(min_length=1)


class Location(Schema):
    code: str = Field(pattern=r"^[A-Z0-9]+(?:[_-][A-Z0-9]+)*$", max_length=50)
    name: str = Field(min_length=1)


Color = Literal["BLACK", "WHITE", "GRAY", "RED", "ORANGE", "YELLOW", "GREEN", "BLUE", "PURPLE", "PINK", "BROWN", "OTHER"]


def normalize_attribute(value: str) -> str:
    import unicodedata
    return " ".join(unicodedata.normalize("NFC", value).lower().split())


class PublicPost(Schema):
    id: UUID
    type: Literal["LOST", "FOUND"]
    title: str = Field(min_length=1)
    description: str = Field(min_length=1)
    category: Category
    location: Location
    event_time: datetime
    status: Literal["OPEN", "CLOSED"]
    color_code: Color | None = None
    public_attributes: dict[Literal["brand", "material"], str] = Field(default_factory=dict)
    created_at: datetime

    @field_validator("event_time", "created_at")
    @classmethod
    def utc_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Timezone is required")
        return value.astimezone(timezone.utc)

    @field_validator("title", "description")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Public text is required")
        return value

    @field_validator("public_attributes")
    @classmethod
    def attributes(cls, value: dict) -> dict:
        return {key: normalized for key, raw in value.items() if (normalized := normalize_attribute(raw))}


class PublicPostInput(Schema):
    """Posts asserts these policy flags, after public projection and catalog validation.

    Incomplete/invalid Posts records must be rejected by the adapter, not fabricated.
    """
    post: PublicPost
    is_public: bool = False
    matching_eligible: bool = False


class Criterion(Schema):
    points: float = Field(ge=0, le=25)
    max_points: int
    reason: Literal["matched", "different", "missing"]


class TimeCriterion(Schema):
    points: float = Field(ge=0, le=20)
    max_points: Literal[20] = 20
    reason: Literal["within_1_day", "within_3_days", "within_7_days", "out_of_window"]
    delta_seconds: float


class KeywordCriterion(Criterion):
    intersection_count: int = Field(ge=0)
    union_count: int = Field(ge=0)


class AttributeCriterion(Criterion):
    matched_count: int = Field(ge=0, le=2)
    compared_count: int = Field(ge=0, le=2)


class ScoreDetails(Schema):
    category: Criterion
    location: Criterion
    time: TimeCriterion
    color: Criterion
    keywords: KeywordCriterion
    public_attributes: AttributeCriterion


class MatchItem(Schema):
    id: UUID
    lost_post_id: UUID
    found_post_id: UUID
    candidate: PublicPost
    score: float = Field(ge=50, le=100)
    level: Literal["HIGH", "POSSIBLE"]
    score_details: ScoreDetails
    explanation: str


class Pagination(Schema):
    page: int
    page_size: int
    total: int
    total_pages: int
    has_next: bool
    has_previous: bool


class MatchesResponse(Schema):
    source_post_id: UUID
    rule_version: str
    calculated_at: datetime
    min_score: float
    sort: Literal["score_desc"] = "score_desc"
    items: list[MatchItem]
    pagination: Pagination


class MatchesQuery(Schema):
    post_id: UUID
    min_score: Annotated[Decimal, Field(ge=50, le=100, decimal_places=2, allow_inf_nan=False)] = Decimal(50)
    page: int = Field(default=1, ge=1, le=10000)
    page_size: int = Field(default=20, ge=1, le=100)
    sort: Literal["score_desc"] = "score_desc"


class ErrorDetail(Schema):
    field: str
    code: str
    message: str


class ErrorBody(Schema):
    code: str
    message: str
    details: list[ErrorDetail] = Field(default_factory=list)


class ErrorResponse(Schema):
    error: ErrorBody
