from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PostImageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    post_id: UUID
    file_path: str = Field(description="Public image URL subject to post visibility")
    original_name: str | None = Field(default=None, max_length=255)
    mime_type: str | None = Field(default=None, max_length=100)
    size_bytes: int | None = Field(default=None, gt=0)
    sort_order: int = Field(ge=0)
    created_at: datetime


class PostImageUploadResponse(BaseModel):
    image: PostImageResponse
