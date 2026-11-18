from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query

from app.core.security import CurrentUser, DatabaseSession
from app.modules.notifications_admin.schemas.notification import (
    NotificationListResponse,
    NotificationReadResponse,
)
from app.modules.notifications_admin.services.notification_service import (
    list_notifications,
    mark_read,
)

router = APIRouter(prefix="/api/v1/notifications", tags=["Notifications"])


@router.get("")
def get_my_notifications(
    db: DatabaseSession,
    user: CurrentUser,
    page: Annotated[int, Query(ge=1, le=10000)] = 1,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    is_read: bool | None = None,
) -> NotificationListResponse:
    return list_notifications(db, user.id, page, limit, is_read)


@router.patch("/{id}/read")
def mark_notification_as_read(
    id: UUID, db: DatabaseSession, user: CurrentUser
) -> NotificationReadResponse:
    return mark_read(db, id, user.id)
