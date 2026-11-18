from datetime import datetime
from typing import Any
import uuid
from pydantic import BaseModel, ConfigDict, Field


class ErrorResponse(BaseModel):
    """Mô hình phản hồi lỗi tiêu chuẩn FastAPI."""
    detail: str = Field(
        ...,
        description="Thông báo mô tả chi tiết lỗi",
        examples=["Thông báo chi tiết lỗi xảy ra trong quá trình xử lý."],
    )


class NotificationItemResponse(BaseModel):
    """Notification response item matching KAN-30 API contract."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(
        ...,
        description="Định danh duy nhất của thông báo dạng UUIDv4",
        examples=["a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11"],
    )
    type: str = Field(
        ...,
        description="Mã sự kiện / loại thông báo, ví dụ CLAIM_CREATED, POST_HIDDEN",
        examples=["CLAIM_CREATED"],
    )
    title: str = Field(
        ...,
        description="Tiêu đề thông báo",
        examples=["Bạn có yêu cầu nhận đồ mới"],
    )
    message: str = Field(
        ...,
        description="Nội dung thông báo",
        examples=["Một người dùng đã gửi yêu cầu nhận đồ trong bài đăng của bạn."],
    )
    resource_type: str | None = Field(
        None,
        description="Loại tài nguyên liên kết: CLAIM, POST, RETURN, REPORT, MATCH",
        examples=["CLAIM"],
    )
    resource_id: str | None = Field(
        None,
        description="ID tài nguyên liên kết dạng chuỗi UUID",
        examples=["b1ffcd88-8b0a-4fe7-aa5c-5aa8ac270b22"],
    )
    is_read: bool = Field(
        ...,
        description="Trạng thái đã đọc hay chưa",
        examples=[False],
    )
    read_at: datetime | None = Field(
        None,
        description="Thời điểm đánh dấu đã đọc (ISO 8601 UTC)",
        examples=[None],
    )
    created_at: datetime = Field(
        ...,
        description="Thời điểm tạo thông báo (ISO 8601 UTC)",
        examples=["2026-11-18T10:30:00Z"],
    )


class NotificationPagination(BaseModel):
    """Pagination metadata matching KAN-30 API contract."""
    page: int = Field(
        ...,
        ge=1,
        description="Trang hiện tại (bắt đầu từ 1)",
        examples=[1],
    )
    limit: int = Field(
        ...,
        ge=1,
        le=100,
        description="Số lượng phần tử mỗi trang (tối đa 100)",
        examples=[20],
    )
    total: int = Field(
        ...,
        ge=0,
        description="Tổng số thông báo thỏa mãn điều kiện lọc",
        examples=[42],
    )
    total_pages: int = Field(
        ...,
        ge=0,
        description="Tổng số trang",
        examples=[3],
    )


class NotificationListResponse(BaseModel):
    """Paginated list response for GET /api/v1/notifications."""
    items: list[NotificationItemResponse] = Field(
        ...,
        description="Danh sách các thông báo trên trang hiện tại",
    )
    pagination: NotificationPagination = Field(
        ...,
        description="Metadata phân trang",
    )


class NotificationReadResponse(BaseModel):
    """Response for PATCH /api/v1/notifications/{id}/read."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(
        ...,
        description="Định danh duy nhất của thông báo dạng UUIDv4",
        examples=["a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11"],
    )
    is_read: bool = Field(
        True,
        description="Trạng thái đã đọc sau khi cập nhật (luôn là true)",
        examples=[True],
    )
    read_at: datetime = Field(
        ...,
        description="Thời điểm đã đọc (ISO 8601 UTC)",
        examples=["2026-11-18T10:35:00Z"],
    )


class NotificationCreateInternal(BaseModel):
    """
    Internal service payload used by Claims and Posts modules to create notifications.
    Not exposed via public HTTP endpoint.
    """
    recipient_id: uuid.UUID = Field(
        ...,
        description="UUID của người nhận thông báo (phải là user ACTIVE)",
        examples=["d3b22c11-4e3f-4c79-a9f2-6293af12458b"],
    )
    event_type: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Mã sự kiện thông báo (CLAIM_CREATED, CLAIM_APPROVED, CLAIM_REJECTED, RETURN_REQUESTED, RETURN_COMPLETED, POST_HIDDEN)",
        examples=["POST_HIDDEN"],
    )
    title: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Tiêu đề thông báo",
        examples=["Bài đăng của bạn đã bị ẩn"],
    )
    message: str = Field(
        ...,
        min_length=1,
        description="Nội dung thông báo hiển thị cho người dùng",
        examples=["Bài đăng của bạn đã bị quản trị viên ẩn do vi phạm quy định."],
    )
    resource_type: str | None = Field(
        None,
        description="Loại tài nguyên liên kết: POST, CLAIM, RETURN, REPORT, MATCH",
        examples=["POST"],
    )
    resource_id: uuid.UUID | None = Field(
        None,
        description="UUID của tài nguyên liên kết",
        examples=["c2a11b00-3d2e-4b68-98e1-51829e01347a"],
    )
    metadata: dict[str, Any] | None = Field(
        None,
        description="Metadata bổ sung an toàn (đã qua allowlist kiểm duyệt)",
        examples=[{"post_id": "c2a11b00-3d2e-4b68-98e1-51829e01347a"}],
    )
    event_id: uuid.UUID | None = Field(
        None,
        description="Unique event ID for deduplication / idempotency (UUIDv5 hoặc UUID ngẫu nhiên)",
        examples=["f47ac10b-58cc-4372-a567-0e02b2c3d479"],
    )
