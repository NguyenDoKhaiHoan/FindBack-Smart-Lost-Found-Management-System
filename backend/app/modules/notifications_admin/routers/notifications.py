import uuid
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_active_user, get_db
from app.modules.identity.models.user import User
from app.modules.notifications_admin.schemas.notification import (
    ErrorResponse,
    NotificationListResponse,
    NotificationReadResponse,
)
from app.modules.notifications_admin.services.notification_service import NotificationService

router = APIRouter(prefix="/notifications", tags=["Notifications"])
notification_service = NotificationService()


@router.get(
    "",
    response_model=NotificationListResponse,
    status_code=status.HTTP_200_OK,
    summary="Lấy danh sách thông báo của người dùng",
    description="Trả về danh sách thông báo của tài khoản đang đăng nhập, hỗ trợ phân trang và lọc trạng thái đọc.",
    responses={
        status.HTTP_200_OK: {
            "model": NotificationListResponse,
            "description": "Lấy danh sách thông báo thành công.",
        },
        status.HTTP_401_UNAUTHORIZED: {
            "model": ErrorResponse,
            "description": "Chưa xác thực hoặc token không hợp lệ / hết hạn.",
        },
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Tài khoản người dùng bị vô hiệu hóa hoặc không ở trạng thái ACTIVE.",
        },
    },
)
async def get_my_notifications(
    page: int = Query(1, ge=1, description="Số trang, bắt đầu từ 1"),
    limit: int = Query(20, ge=1, le=100, description="Số phần tử mỗi trang, tối đa 100"),
    is_read: bool | None = Query(None, description="Lọc theo trạng thái đã đọc (true) hoặc chưa đọc (false)"),
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db),
) -> NotificationListResponse:
    """Lấy danh sách thông báo theo phân trang của current user."""
    return await notification_service.get_user_notifications(
        session=session,
        current_user_id=current_user.id,
        page=page,
        limit=limit,
        is_read=is_read,
    )


@router.patch(
    "/{id}/read",
    response_model=NotificationReadResponse,
    status_code=status.HTTP_200_OK,
    summary="Đánh dấu thông báo đã đọc",
    description="Đánh dấu thông báo thuộc sở hữu của người dùng hiện tại là đã đọc. Có tính chất idempotent.",
    responses={
        status.HTTP_200_OK: {
            "model": NotificationReadResponse,
            "description": "Đánh dấu thông báo đã đọc thành công hoặc đã đọc trước đó (idempotent).",
        },
        status.HTTP_401_UNAUTHORIZED: {
            "model": ErrorResponse,
            "description": "Chưa xác thực hoặc token không hợp lệ / hết hạn.",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "Thông báo không tồn tại hoặc không thuộc quyền sở hữu của người dùng hiện tại.",
        },
    },
)
async def mark_notification_as_read(
    id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db),
) -> NotificationReadResponse:
    """Đánh dấu thông báo đã đọc theo ID."""
    return await notification_service.mark_as_read(
        session=session,
        notification_id=id,
        current_user_id=current_user.id,
    )
