from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.modules.matching.schemas.contracts import Color
from app.modules.posts.services.catalog import HotspotZone

from .post_image import PostImageResponse


class PostType(str, Enum):
    LOST = "LOST"
    FOUND = "FOUND"


class PostStatus(str, Enum):
    OPEN = "OPEN"
    HIDDEN = "HIDDEN"
    CLOSED = "CLOSED"


Latitude = Annotated[Decimal, Field(ge=-90, le=90, max_digits=9, decimal_places=6)]
Longitude = Annotated[Decimal, Field(ge=-180, le=180, max_digits=9, decimal_places=6)]


class _PostEditable(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    item_name: str | None = Field(default=None, min_length=1, max_length=100)
    hotspot_zone: HotspotZone | None = None

    @field_validator("event_time", check_fields=False)
    @classmethod
    def require_offset(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("event_time must include an ISO 8601 timezone offset")
        return value

    @model_validator(mode="after")
    def coordinate_pair(self):
        supplied = self.model_fields_set
        if "latitude" in supplied or "longitude" in supplied:
            if "latitude" not in supplied or "longitude" not in supplied:
                raise ValueError("latitude and longitude must be provided together")
            if (self.latitude is None) != (self.longitude is None):
                raise ValueError("latitude and longitude must both be null or both non-null")
        return self


class PostCreate(_PostEditable):
    type: PostType
    category_id: UUID
    title: str = Field(min_length=1, max_length=255)
    description: str = Field(min_length=1, max_length=10000)
    location: str = Field(min_length=1, max_length=255)
    area: str | None = Field(default=None, max_length=100)
    location_code: str | None = Field(default=None, max_length=50)
    event_time: datetime
    brand: str | None = Field(default=None, max_length=100)
    color: str | None = Field(default=None, max_length=50)
    color_code: Color | None = None
    material: str | None = Field(default=None, max_length=100)
    latitude: Latitude | None = None
    longitude: Longitude | None = None


class PostUpdate(_PostEditable):
    category_id: UUID | None = None
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, min_length=1, max_length=10000)
    location: str | None = Field(default=None, min_length=1, max_length=255)
    area: str | None = Field(default=None, max_length=100)
    location_code: str | None = Field(default=None, max_length=50)
    event_time: datetime | None = None
    brand: str | None = Field(default=None, max_length=100)
    color: str | None = Field(default=None, max_length=50)
    color_code: Color | None = None
    material: str | None = Field(default=None, max_length=100)
    latitude: Latitude | None = None
    longitude: Longitude | None = None

    @model_validator(mode="after")
    def reject_empty_or_null_required(self):
        if not self.model_fields_set:
            raise ValueError("PATCH body must contain at least one field")
        for key in ("category_id", "title", "description", "location", "event_time"):
            if key in self.model_fields_set and getattr(self, key) is None:
                raise ValueError(f"{key} cannot be null")
        return self


class PostResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    type: PostType
    category_id: UUID | None
    item_name: str | None = None
    title: str | None
    description: str | None
    location: str | None
    area: str | None
    location_code: str | None
    event_time: datetime | None
    brand: str | None
    color: str | None
    material: str | None
    color_code: Color | None
    status: PostStatus = Field(validation_alias="display_status")
    created_at: datetime
    updated_at: datetime
    images: list[PostImageResponse] = Field(default_factory=list)


class PostListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    type: PostType
    category_id: UUID | None
    title: str | None
    location: str | None
    area: str | None
    event_time: datetime | None
    status: PostStatus = Field(validation_alias="display_status")
    created_at: datetime


class PostListResponse(BaseModel):
    items: list[PostListItem]
    page: int = Field(ge=1)
    page_size: int = Field(ge=1)
    total: int = Field(ge=0)
    total_pages: int = Field(ge=0)


class PostHotspotLocation(BaseModel):
    hotspot_zone: HotspotZone
    latitude: float
    longitude: float


class PostListQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
    type: PostType | None = None
    category_id: UUID | None = None
    area: str | None = Field(default=None, min_length=1, max_length=100)


class ErrorResponse(BaseModel):
    code: str
    message: str
    details: list[dict] | None = None
