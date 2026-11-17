from datetime import datetime
from typing import Literal
import uuid
from pydantic import BaseModel, ConfigDict, Field, field_validator


class AdminPostItemResponse(BaseModel):
    """Admin post item matching KAN-32 specifications."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str = Field(..., description="Tiêu đề bài đăng")
    description: str = Field(..., description="Nội dung mô tả bài đăng")
    type: str = Field(..., description="Loại tin: LOST hoặc FOUND")
    status: str = Field(..., description="Trạng thái bài đăng: DRAFT, ACTIVE, HIDDEN, CLOSED")
    user_id: uuid.UUID = Field(..., description="ID tác giả bài đăng")
    location: str | None = Field(None, description="Địa điểm")
    area: str | None = Field(None, description="Khu vực")
    moderated_by: uuid.UUID | None = Field(None, description="Admin thực hiện kiểm duyệt")
    moderated_at: datetime | None = Field(None, description="Thời điểm kiểm duyệt")
    moderation_reason: str | None = Field(None, description="Lý do kiểm duyệt")
    created_at: datetime = Field(..., description="Thời điểm tạo (ISO 8601)")
    updated_at: datetime = Field(..., description="Thời điểm cập nhật (ISO 8601)")


class AdminPostPagination(BaseModel):
    """Pagination metadata for admin post listings."""
    page: int = Field(..., ge=1, description="Trang hiện tại")
    limit: int = Field(..., ge=1, le=100, description="Số lượng phần tử mỗi trang")
    total: int = Field(..., ge=0, description="Tổng số bài đăng")
    total_pages: int = Field(..., ge=0, description="Tổng số trang")


class AdminPostListResponse(BaseModel):
    """Paginated list response for GET /api/v1/admin/posts."""
    items: list[AdminPostItemResponse]
    pagination: AdminPostPagination


class PostModerationRequest(BaseModel):
    """Request payload for PATCH /api/v1/admin/posts/{id}/moderation."""
    action: str = Field(..., description="Hành động kiểm duyệt (chỉ hỗ trợ HIDE)")
    reason: str = Field(..., min_length=1, description="Lý do kiểm duyệt bắt buộc")

    @field_validator("reason")
    @classmethod
    def validate_non_empty_reason(cls, v: str) -> str:
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("Lý do kiểm duyệt không được để trống.")
        return trimmed


class PostModerationResponse(BaseModel):
    """Response payload for PATCH /api/v1/admin/posts/{id}/moderation."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: str = Field("HIDDEN", description="Trạng thái sau kiểm duyệt")
    moderated_by: uuid.UUID = Field(..., description="ID quản trị viên kiểm duyệt")
    moderation_reason: str = Field(..., description="Lý do kiểm duyệt đã ghi nhận")
    moderated_at: datetime = Field(..., description="Thời điểm kiểm duyệt (ISO 8601)")
