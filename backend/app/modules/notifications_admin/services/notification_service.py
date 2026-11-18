from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.db.session import utcnow
from app.modules.notifications_admin.models.notification import Notification
from app.modules.notifications_admin.schemas.claim_events import ClaimNotificationEvent
from app.modules.notifications_admin.schemas.notification import (
    NotificationItemResponse,
    NotificationListResponse,
    NotificationPagination,
    NotificationReadResponse,
)
from app.shared.errors import DomainError

CLAIM_MESSAGES = {
    "claim.created": ("CLAIM_CREATED", "Yêu cầu nhận đồ mới"),
    "claim.approved": ("CLAIM_APPROVED", "Yêu cầu nhận đồ được duyệt"),
    "claim.rejected": ("CLAIM_REJECTED", "Yêu cầu nhận đồ bị từ chối"),
    "claim.completed": ("CLAIM_COMPLETED", "Trao trả đã được xác nhận"),
    "claim.evidence_added": ("CLAIM_EVIDENCE_ADDED", "Bằng chứng nhận đồ được bổ sung"),
    "return.arranged": ("RETURN_ARRANGED", "Phiên trao trả đã được lập"),
    "return.handed_over": ("RETURN_HANDED_OVER", "Chủ tin đã ghi nhận giao đồ"),
}


def stage_claim_notification(db: Session, event: ClaimNotificationEvent) -> None:
    kind, title = CLAIM_MESSAGES[event.type]
    db.add(
        Notification(
            recipient_id=event.recipient_id,
            event_id=event.event_id,
            type=kind,
            title=title,
            message=title,
            resource_type="CLAIM",
            resource_id=event.claim_id,
            created_at=event.occurred_at,
        )
    )


def list_notifications(
    db: Session, user_id: UUID, page: int, limit: int, is_read: bool | None
) -> NotificationListResponse:
    stmt = select(Notification).where(Notification.recipient_id == user_id)
    if is_read is not None:
        stmt = stmt.where(
            Notification.read_at.is_not(None) if is_read else Notification.read_at.is_(None)
        )
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db.scalars(
        stmt.order_by(Notification.created_at.desc(), Notification.id.desc())
        .offset((page - 1) * limit)
        .limit(limit)
    )
    return NotificationListResponse(
        items=[NotificationItemResponse.model_validate(row) for row in rows],
        pagination=NotificationPagination(
            page=page,
            limit=limit,
            total=total,
            total_pages=(total + limit - 1) // limit,
        ),
    )


def mark_read(db: Session, notification_id: UUID, user_id: UUID) -> NotificationReadResponse:
    db.execute(
        update(Notification)
        .where(
            Notification.id == notification_id,
            Notification.recipient_id == user_id,
            Notification.read_at.is_(None),
        )
        .values(read_at=utcnow())
    )
    row = db.scalar(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.recipient_id == user_id,
        )
    )
    if row is None:
        raise DomainError(404, "NOTIFICATION_NOT_FOUND", "Notification not found")
    response = NotificationReadResponse.model_validate(row)
    db.commit()
    return response
