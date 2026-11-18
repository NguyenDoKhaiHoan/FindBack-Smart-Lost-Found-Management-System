from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Query

from app.core.security import CurrentAdmin, DatabaseSession
from app.modules.notifications_admin.schemas.admin_post import (
    AdminPostListResponse,
    PostModerationRequest,
    PostModerationResponse,
)
from app.modules.notifications_admin.services import moderation

router = APIRouter(prefix="/api/v1/admin/posts", tags=["Admin Posts"])


@router.get("")
def list_admin_posts(
    db: DatabaseSession,
    admin: CurrentAdmin,
    page: Annotated[int, Query(ge=1, le=10000)] = 1,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    status: Literal["OPEN", "ACTIVE", "HIDDEN", "CLOSED"] | None = None,
    type: Literal["LOST", "FOUND"] | None = None,
    q: Annotated[str | None, Query(max_length=200)] = None,
) -> AdminPostListResponse:
    return moderation.list_admin_posts(db, page, limit, status, type, q)


@router.patch("/{id}/moderation")
def moderate_post(
    id: UUID, body: PostModerationRequest, db: DatabaseSession, admin: CurrentAdmin
) -> PostModerationResponse:
    return moderation.moderate_post(db, id, admin.id, body)
