from datetime import datetime
import uuid
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.modules.notifications_admin.schemas.notification import ErrorResponse


class AdminPostItemResponse(BaseModel):
    """Admin post item matching KAN-32 specifications."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(
        ...,
        description="Định danh duy nhất của bài đăng dạng UUIDv4",
        examples=["c2a11b00-3d2e-4b68-98e1-51829e01347a"],
    )
    title: str = Field(
        ...,
        description="Tiêu đề bài đăng",
        examples=["Nhặt được ví da màu đen tại Tòa FPT"],
    )
    description: str = Field(
        ...,
        description="Nội dung mô tả bài đăng",
        examples=["Nhặt được chiếc ví tại phòng Lab 204 lúc 15h ngày 18/11/2026."],
    )
    type: str = Field(
        ...,
        description="Loại tin: LOST (mất đồ) hoặc FOUND (nhặt được đồ)",
        examples=["FOUND"],
    )
    status: str = Field(
        ...,
        description="Trạng thái bài đăng: DRAFT, ACTIVE, HIDDEN, CLOSED",
        examples=["ACTIVE"],
    )
    user_id: uuid.UUID = Field(
        ...,
        description="ID tác giả bài đăng dạng UUIDv4",
        examples=["d3b22c11-4e3f-4c79-a9f2-6293af12458b"],
    )
    location: str | None = Field(
        None,
        description="Địa điểm chi tiết",
        examples=["Tòa nhà FPT, Khu Công nghệ cao"],
    )
    area: str | None = Field(
        None,
        description="Khu vực / Quận huyện",
        examples=["Quận 9, TP. Thủ Đức"],
    )
    moderated_by: uuid.UUID | None = Field(
        None,
        description="Admin thực hiện kiểm duyệt dạng UUIDv4 (nếu có)",
        examples=[None],
    )
    moderated_at: datetime | None = Field(
        None,
        description="Thời điểm kiểm duyệt (ISO 8601 UTC)",
        examples=[None],
    )
    moderation_reason: str | None = Field(
        None,
        description="Lý do kiểm duyệt (nếu có)",
        examples=[None],
    )
    created_at: datetime = Field(
        ...,
        description="Thời điểm tạo bài đăng (ISO 8601 UTC)",
        examples=["2026-11-18T08:00:00Z"],
    )
    updated_at: datetime = Field(
        ...,
        description="Thời điểm cập nhật bài đăng gần nhất (ISO 8601 UTC)",
        examples=["2026-11-18T08:30:00Z"],
    )


class AdminPostPagination(BaseModel):
    """Pagination metadata for admin post listings."""
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
        description="Tổng số bài đăng thỏa mãn điều kiện lọc",
        examples=[15],
    )
    total_pages: int = Field(
        ...,
        ge=0,
        description="Tổng số trang",
        examples=[1],
    )


class AdminPostListResponse(BaseModel):
    """Paginated list response for GET /api/v1/admin/posts."""
    items: list[AdminPostItemResponse] = Field(
        ...,
        description="Danh sách các bài đăng dành cho quản trị viên",
    )
    pagination: AdminPostPagination = Field(
        ...,
        description="Metadata phân trang",
    )


class PostModerationRequest(BaseModel):
    """Request payload for PATCH /api/v1/admin/posts/{id}/moderation."""
    action: str = Field(
        ...,
        description="Hành động kiểm duyệt (chỉ hỗ trợ HIDE)",
        examples=["HIDE"],
    )
    reason: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Lý do kiểm duyệt bắt buộc (tối thiểu 1 ký tự, tối đa 500 ký tự sau khi trim)",
        examples=["Tin đăng có nội dung không phù hợp hoặc vi phạm điều khoản cộng đồng."],
    )

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

    id: uuid.UUID = Field(
        ...,
        description="Định danh duy nhất của bài đăng dạng UUIDv4",
        examples=["c2a11b00-3d2e-4b68-98e1-51829e01347a"],
    )
    status: str = Field(
        "HIDDEN",
        description="Trạng thái bài đăng sau khi kiểm duyệt (luôn là HIDDEN)",
        examples=["HIDDEN"],
    )
    moderated_by: uuid.UUID = Field(
        ...,
        description="UUID của quản trị viên thực hiện kiểm duyệt",
        examples=["e4c33d22-5f4a-4d8a-ba03-73a4b023569c"],
    )
    moderation_reason: str = Field(
        ...,
        description="Lý do kiểm duyệt đã ghi nhận",
        examples=["Tin đăng có nội dung không phù hợp hoặc vi phạm điều khoản cộng đồng."],
    )
    moderated_at: datetime = Field(
        ...,
        description="Thời điểm kiểm duyệt (ISO 8601 UTC)",
        examples=["2026-11-18T10:15:00Z"],
    )
