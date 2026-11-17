from datetime import datetime
from typing import Any
import uuid
from pydantic import BaseModel, ConfigDict, Field


class NotificationItemResponse(BaseModel):
    """Notification response item matching KAN-30 API contract."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    type: str = Field(..., description="Mã sự kiện / loại thông báo, ví dụ CLAIM_CREATED, POST_HIDDEN")
    title: str = Field(..., description="Tiêu đề thông báo")
    message: str = Field(..., description="Nội dung thông báo")
    resource_type: str | None = Field(None, description="Loại tài nguyên liên kết: CLAIM, POST, RETURN, REPORT, MATCH")
    resource_id: str | None = Field(None, description="ID tài nguyên liên kết dạng chuỗi UUID")
    is_read: bool = Field(..., description="Trạng thái đã đọc hay chưa")
    read_at: datetime | None = Field(None, description="Thời điểm đánh dấu đã đọc (ISO 8601)")
    created_at: datetime = Field(..., description="Thời điểm tạo thông báo (ISO 8601)")


class NotificationPagination(BaseModel):
    """Pagination metadata matching KAN-30 API contract."""
    page: int = Field(..., ge=1, description="Trang hiện tại")
    limit: int = Field(..., ge=1, le=100, description="Số lượng phần tử mỗi trang")
    total: int = Field(..., ge=0, description="Tổng số thông báo")
    total_pages: int = Field(..., ge=0, description="Tổng số trang")


class NotificationListResponse(BaseModel):
    """Paginated list response for GET /api/v1/notifications."""
    items: list[NotificationItemResponse]
    pagination: NotificationPagination


class NotificationReadResponse(BaseModel):
    """Response for PATCH /api/v1/notifications/{id}/read."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    is_read: bool = Field(True, description="Trạng thái đã đọc")
    read_at: datetime = Field(..., description="Thời điểm đã đọc")


class NotificationCreateInternal(BaseModel):
    """
    Internal service payload used by Claims and Posts modules to create notifications.
    Not exposed via public HTTP endpoint.
    """
    recipient_id: uuid.UUID
    event_type: str = Field(..., min_length=1, max_length=50)
    title: str = Field(..., min_length=1, max_length=255)
    message: str = Field(..., min_length=1)
    resource_type: str | None = None
    resource_id: uuid.UUID | None = None
    metadata: dict[str, Any] | None = None
    event_id: uuid.UUID | None = Field(
        None,
        description="Unique event ID for deduplication / idempotency"
    )
