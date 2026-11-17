from datetime import datetime, timezone
import math
from typing import Any
import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.identity.models.user import User
from app.modules.notifications_admin.models.notification import Notification
from app.modules.notifications_admin.repositories.notification_repository import NotificationRepository
from app.modules.notifications_admin.schemas.notification import (
    NotificationCreateInternal,
    NotificationItemResponse,
    NotificationListResponse,
    NotificationPagination,
    NotificationReadResponse,
)
from app.shared.errors import NotFoundError, ValidationError

# Global allowlist of approved metadata keys based on NOTIFICATION_EVENT_CONTRACT.md Section 6
ALLOWED_METADATA_KEYS = {
    "resource_type",
    "resource_id",
    "post_id",
    "claim_id",
    "return_id",
    "category_id",
    "action",
    "public_reference",
    "reference_code",
    "item_name",
}

# Forbidden keywords checked across all keys and string values at any depth
FORBIDDEN_KEYWORDS = (
    "password",
    "password_hash",
    "token",
    "access_token",
    "refresh_token",
    "jwt",
    "authorization",
    "secret",
    "api_key",
    "evidence",
    "private_evidence",
    "private_content",
    "id_card",
    "credit_card",
    "ssn",
)


class NotificationService:
    """Business logic and inter-module event service for Notifications."""

    def __init__(self, repository: NotificationRepository | None = None):
        self.repository = repository or NotificationRepository()

    @classmethod
    def sanitize_metadata(cls, data: dict[str, Any] | None) -> dict[str, Any] | None:
        """
        Deep recursive metadata sanitization (PRIV-01).

        Security Rules:
        - Only retains root keys explicitly present in ALLOWED_METADATA_KEYS.
        - Recursively inspects nested dictionaries and arrays at any depth.
        - Drops any key containing forbidden keywords (case-insensitive substring check).
        - Strips string values with token / credentials patterns.
        - Returns None if the resulting dictionary is empty or input is None.
        """
        if not data or not isinstance(data, dict):
            return None

        def _is_forbidden_key(key: str) -> bool:
            k = key.strip().lower()
            return any(forbidden in k for forbidden in FORBIDDEN_KEYWORDS)

        def _clean_value(val: Any) -> Any:
            if isinstance(val, dict):
                cleaned_dict: dict[str, Any] = {}
                for k, v in val.items():
                    k_clean = str(k).strip().lower()
                    if _is_forbidden_key(k_clean):
                        continue
                    cleaned_sub = _clean_value(v)
                    if cleaned_sub is not None:
                        cleaned_dict[k_clean] = cleaned_sub
                return cleaned_dict if cleaned_dict else None
            elif isinstance(val, (list, tuple, set)):
                cleaned_list: list[Any] = []
                for item in val:
                    cleaned_item = _clean_value(item)
                    if cleaned_item is not None:
                        cleaned_list.append(cleaned_item)
                return cleaned_list if cleaned_list else None
            elif isinstance(val, str):
                v_lower = val.lower()
                if any(forbidden in v_lower for forbidden in ("bearer ", "jwt ", "argon2", "$2b$", "$2a$")):
                    return None
                return val
            elif isinstance(val, (int, float, bool)):
                return val
            elif isinstance(val, uuid.UUID):
                return str(val)
            return None

        sanitized: dict[str, Any] = {}
        for key, value in data.items():
            key_str = str(key).strip().lower()
            # 1. Root keys MUST be present in allowlist
            if key_str not in ALLOWED_METADATA_KEYS:
                continue
            # 2. Must not contain forbidden keywords
            if _is_forbidden_key(key_str):
                continue
            # 3. Recursively clean value
            cleaned = _clean_value(value)
            if cleaned is not None:
                sanitized[key_str] = cleaned

        return sanitized if sanitized else None

    async def get_user_notifications(
        self,
        session: AsyncSession,
        current_user_id: uuid.UUID,
        page: int = 1,
        limit: int = 20,
        is_read: bool | None = None,
    ) -> NotificationListResponse:
        """
        Retrieves paginated notifications for the authenticated user only.
        Never leaks notifications belonging to other users.
        """
        notifications, total = await self.repository.list_by_recipient(
            session=session,
            recipient_id=current_user_id,
            page=page,
            limit=limit,
            is_read=is_read,
        )

        items = [
            NotificationItemResponse(
                id=n.id,
                type=n.event_type,
                title=n.title,
                message=n.message,
                resource_type=n.resource_type,
                resource_id=str(n.resource_id) if n.resource_id else None,
                is_read=n.is_read,
                read_at=n.read_at,
                created_at=n.created_at,
            )
            for n in notifications
        ]

        total_pages = math.ceil(total / limit) if total > 0 else 0

        return NotificationListResponse(
            items=items,
            pagination=NotificationPagination(
                page=page,
                limit=limit,
                total=total,
                total_pages=total_pages,
            ),
        )

    async def mark_as_read(
        self,
        session: AsyncSession,
        notification_id: uuid.UUID,
        current_user_id: uuid.UUID,
    ) -> NotificationReadResponse:
        """
        Marks a notification as read with ownership validation and idempotency.

        - If the notification does not exist or does not belong to the caller,
          returns 404 (NotFoundError) to prevent resource ID enumeration.
        - If already read, returns the existing read timestamp without modifying data.
        """
        notification = await self.repository.get_by_id_and_recipient(
            session=session,
            notification_id=notification_id,
            recipient_id=current_user_id,
        )
        if not notification:
            # Consistent 404 error per KAN-30 contract
            raise NotFoundError("Thông báo không tồn tại hoặc không thuộc quyền sở hữu.")

        # Idempotent: already read
        if notification.is_read and notification.read_at:
            return NotificationReadResponse(
                id=notification.id,
                is_read=True,
                read_at=notification.read_at,
            )

        now = datetime.now(timezone.utc)
        updated_notification = await self.repository.mark_as_read(
            session=session,
            notification=notification,
            read_at=now,
        )
        await session.commit()

        return NotificationReadResponse(
            id=updated_notification.id,
            is_read=True,
            read_at=updated_notification.read_at or now,
        )

    async def create_notification(
        self,
        session: AsyncSession,
        data: NotificationCreateInternal,
        auto_commit: bool = True,
    ) -> Notification:
        """
        Internal event contract entrypoint.

        Called by Posts or Claims modules (or background workers) to emit notifications:
        - Validates recipient exists and is active.
        - Enforces deduplication / idempotency using PostgreSQL ON CONFLICT (CONC-01).
        - Deep sanitizes metadata against allowlist and forbidden terms (PRIV-01).
        - Supports auto_commit flag to participate in caller transaction without breaking it.
        """
        # Validate recipient exists and is active
        user_stmt = select(User).where(User.id == data.recipient_id)
        user_res = await session.execute(user_stmt)
        recipient = user_res.scalars().first()
        if not recipient:
            raise NotFoundError(f"Người nhận không tồn tại: {data.recipient_id}")
        if recipient.status != "ACTIVE":
            raise ValidationError(f"Người nhận không ở trạng thái ACTIVE: {recipient.status}")

        # Sanitize metadata (deep recursive allowlist)
        sanitized_metadata = self.sanitize_metadata(data.metadata)

        notification_values: dict[str, Any] = {
            "recipient_id": data.recipient_id,
            "event_id": data.event_id,
            "event_type": data.event_type,
            "title": data.title,
            "message": data.message,
            "resource_type": data.resource_type,
            "resource_id": data.resource_id,
            "metadata_json": sanitized_metadata,
            "is_read": False,
            "read_at": None,
        }

        notification = await self.repository.create_idempotent(session, notification_values)
        if auto_commit:
            await session.commit()

        return notification
