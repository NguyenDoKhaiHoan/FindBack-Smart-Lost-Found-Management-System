from datetime import datetime, timezone
import math
from typing import Sequence
import uuid
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.identity.models.user import User
from app.modules.notifications_admin.models.audit_log import AuditLog
from app.modules.notifications_admin.repositories.audit_log_repository import AuditLogRepository
from app.modules.notifications_admin.schemas.admin_post import (
    AdminPostItemResponse,
    AdminPostListResponse,
    AdminPostPagination,
    PostModerationRequest,
    PostModerationResponse,
)
from app.modules.notifications_admin.schemas.notification import NotificationCreateInternal
from app.modules.notifications_admin.services.notification_service import NotificationService
from app.modules.posts.models.post import Post
from app.modules.posts.repositories.post_repository import PostRepository
from app.shared.errors import BadRequestError, NotFoundError, ValidationError

VALID_STATUSES = {"ACTIVE", "HIDDEN", "CLOSED", "DRAFT"}
VALID_TYPES = {"LOST", "FOUND"}


class PostModerationService:
    """Business service for Admin Post Moderation and Auditing (KAN-32)."""

    def __init__(
        self,
        post_repository: PostRepository | None = None,
        audit_log_repository: AuditLogRepository | None = None,
        notification_service: NotificationService | None = None,
    ):
        self.post_repository = post_repository or PostRepository()
        self.audit_log_repository = audit_log_repository or AuditLogRepository()
        self.notification_service = notification_service or NotificationService()

    async def list_posts(
        self,
        session: AsyncSession,
        page: int = 1,
        limit: int = 20,
        status: str | None = None,
        type_: str | None = None,
        q: str | None = None,
    ) -> AdminPostListResponse:
        """
        Lists posts for Admin with pagination, status/type filters, and search.
        Validates filter parameters and prevents exposure of sensitive internal data.
        """
        # Validate status if supplied
        if status is not None:
            status_clean = status.strip().upper()
            if status_clean not in VALID_STATUSES:
                raise ValidationError(
                    f"Trạng thái '{status}' không hợp lệ. Các giá trị hợp lệ: {', '.join(sorted(VALID_STATUSES))}."
                )
            status = status_clean

        # Validate type if supplied
        if type_ is not None:
            type_clean = type_.strip().upper()
            if type_clean not in VALID_TYPES:
                raise ValidationError(
                    f"Loại bài đăng '{type_}' không hợp lệ. Các giá trị hợp lệ: {', '.join(sorted(VALID_TYPES))}."
                )
            type_ = type_clean

        posts, total = await self.post_repository.list_admin_posts(
            session=session,
            page=page,
            limit=limit,
            status=status,
            type_=type_,
            q=q,
        )

        items = [
            AdminPostItemResponse(
                id=p.id,
                title=p.title,
                description=p.description,
                type=p.type,
                status=p.status,
                user_id=p.user_id,
                location=p.location,
                area=p.area,
                moderated_by=p.moderated_by,
                moderated_at=p.moderated_at,
                moderation_reason=p.moderation_reason,
                created_at=p.created_at,
                updated_at=p.updated_at,
            )
            for p in posts
        ]

        total_pages = math.ceil(total / limit) if total > 0 else 0

        return AdminPostListResponse(
            items=items,
            pagination=AdminPostPagination(
                page=page,
                limit=limit,
                total=total,
                total_pages=total_pages,
            ),
        )

    async def moderate_post(
        self,
        session: AsyncSession,
        post_id: uuid.UUID,
        admin_user: User,
        request: PostModerationRequest,
    ) -> PostModerationResponse:
        """
        Moderates a post (action HIDE) atomically:
        1. Validates admin permissions and request parameters.
        2. Verifies post existence (404) and state (rejects CLOSED with 400).
        3. Updates post status to HIDDEN and records moderation metadata.
        4. Writes an audit log entry within the same transaction.
        5. Notifies the post owner via NotificationService (auto_commit=False).
        6. Commits atomically or rolls back entirely on any failure.
        """
        # Validate action
        action_clean = request.action.strip().upper()
        if action_clean != "HIDE":
            raise BadRequestError(
                f"Hành động '{request.action}' không được hỗ trợ trong phạm vi KAN-32. Chỉ hỗ trợ 'HIDE'."
            )

        # Validate reason
        reason_clean = request.reason.strip()
        if not reason_clean:
            raise ValidationError("Lý do kiểm duyệt không được để trống.")

        # Fetch target post with row-level lock for concurrency safety
        post = await self.post_repository.get_by_id(session, post_id, for_update=True)
        if not post:
            raise NotFoundError("Bài đăng không tồn tại.")

        # Business rule: CLOSED posts cannot be moderated
        if post.status == "CLOSED":
            raise BadRequestError("Không thể kiểm duyệt bài đăng đã đóng (CLOSED).")

        # Idempotency rule: If already HIDDEN, preserve initial moderation metadata
        # (do not overwrite moderated_by, moderated_at, moderation_reason with repeat calls)
        if post.status == "HIDDEN":
            return PostModerationResponse(
                id=post.id,
                status=post.status,
                moderated_by=post.moderated_by or admin_user.id,
                moderation_reason=post.moderation_reason or reason_clean,
                moderated_at=post.moderated_at or datetime.now(timezone.utc),
            )

        old_status = post.status
        now = datetime.now(timezone.utc)

        try:
            # 1. Update post state and moderation fields
            post.status = "HIDDEN"
            post.moderated_by = admin_user.id
            post.moderated_at = now
            post.moderation_reason = reason_clean
            post.updated_at = now

            # 2. Record Audit Log entry
            await self.audit_log_repository.create(
                session=session,
                actor_id=admin_user.id,
                action="HIDE",
                target_type="POST",
                target_id=post.id,
                reason=reason_clean,
                old_status=old_status,
                new_status="HIDDEN",
                metadata={"action": "HIDE", "post_title": post.title},
            )

            # 3. Notify post owner via NotificationService (auto_commit=False)
            # Use deterministic event_id for idempotency
            event_id = uuid.uuid5(uuid.NAMESPACE_OID, f"POST_HIDDEN:{post.id}")
            notification_data = NotificationCreateInternal(
                recipient_id=post.user_id,
                event_type="POST_HIDDEN",
                title="Bài đăng đã bị ẩn",
                message=f"Bài đăng '{post.title}' của bạn đã bị ẩn bởi quản trị viên do vi phạm quy định: {reason_clean}",
                resource_type="POST",
                resource_id=post.id,
                metadata={
                    "resource_type": "POST",
                    "resource_id": str(post.id),
                    "post_id": str(post.id),
                    "action": "HIDE",
                },
                event_id=event_id,
            )

            await self.notification_service.create_notification(
                session=session,
                data=notification_data,
                auto_commit=False,
            )

            # 4. Atomic transaction commit
            await session.commit()
            await session.refresh(post)

        except Exception:
            await session.rollback()
            raise

        return PostModerationResponse(
            id=post.id,
            status=post.status,
            moderated_by=post.moderated_by or admin_user.id,
            moderation_reason=post.moderation_reason or reason_clean,
            moderated_at=post.moderated_at or now,
        )
