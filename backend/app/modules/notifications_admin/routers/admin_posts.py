import uuid
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_admin_user, get_db
from app.modules.identity.models.user import User
from app.modules.notifications_admin.schemas.admin_post import (
    AdminPostListResponse,
    ErrorResponse,
    PostModerationRequest,
    PostModerationResponse,
)
from app.modules.notifications_admin.services.post_moderation_service import PostModerationService

router = APIRouter(prefix="/admin/posts", tags=["Admin Posts"])
post_moderation_service = PostModerationService()


@router.get(
    "",
    response_model=AdminPostListResponse,
    status_code=status.HTTP_200_OK,
    summary="Lấy danh sách bài đăng dành cho Quản trị viên (Admin)",
    description="Trả về danh sách bài đăng có hỗ trợ phân trang, lọc trạng thái, lọc loại bài và tìm kiếm theo từ khóa.",
    responses={
        status.HTTP_200_OK: {
            "model": AdminPostListResponse,
            "description": "Lấy danh sách bài đăng thành công.",
        },
        status.HTTP_401_UNAUTHORIZED: {
            "model": ErrorResponse,
            "description": "Chưa xác thực hoặc token không hợp lệ / hết hạn.",
        },
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Chức năng chỉ dành cho quản trị viên (Admin) hoặc tài khoản không ở trạng thái ACTIVE.",
        },
    },
)
async def list_admin_posts(
    page: int = Query(1, ge=1, description="Số trang, bắt đầu từ 1"),
    limit: int = Query(20, ge=1, le=100, description="Số phần tử mỗi trang, tối đa 100"),
    status: str | None = Query(None, description="Lọc theo trạng thái: DRAFT, ACTIVE, HIDDEN, CLOSED"),
    type: str | None = Query(None, description="Lọc theo loại: LOST, FOUND"),
    q: str | None = Query(None, description="Từ khóa tìm kiếm theo tiêu đề, mô tả hoặc vị trí"),
    current_admin: User = Depends(get_current_admin_user),
    session: AsyncSession = Depends(get_db),
) -> AdminPostListResponse:
    """Lấy danh sách bài đăng phân trang cho quản trị viên."""
    return await post_moderation_service.list_posts(
        session=session,
        page=page,
        limit=limit,
        status=status,
        type_=type,
        q=q,
    )


@router.patch(
    "/{id}/moderation",
    response_model=PostModerationResponse,
    status_code=status.HTTP_200_OK,
    summary="Kiểm duyệt bài đăng (Admin)",
    description="Thực hiện kiểm duyệt bài đăng (ẩn bài HIDE). Yêu cầu quyền Admin và lý do kiểm duyệt bắt buộc.",
    responses={
        status.HTTP_200_OK: {
            "model": PostModerationResponse,
            "description": "Kiểm duyệt bài đăng thành công (chuyển sang HIDDEN và tạo thông báo cho tác giả).",
        },
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Hành động kiểm duyệt không hợp lệ hoặc bài viết đã ở trạng thái CLOSED (không thể ẩn).",
        },
        status.HTTP_401_UNAUTHORIZED: {
            "model": ErrorResponse,
            "description": "Chưa xác thực hoặc token không hợp lệ / hết hạn.",
        },
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Chức năng chỉ dành cho quản trị viên (Admin) hoặc tài khoản không ở trạng thái ACTIVE.",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "Không tìm thấy bài đăng theo ID đã cung cấp.",
        },
    },
)
async def moderate_post(
    id: uuid.UUID,
    request: PostModerationRequest,
    current_admin: User = Depends(get_current_admin_user),
    session: AsyncSession = Depends(get_db),
) -> PostModerationResponse:
    """Kiểm duyệt bài đăng theo ID."""
    return await post_moderation_service.moderate_post(
        session=session,
        post_id=id,
        admin_user=current_admin,
        request=request,
    )
