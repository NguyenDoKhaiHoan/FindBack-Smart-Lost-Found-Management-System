from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.modules.claims_returns.models.claim import AuditLog, OutboxEvent
from app.modules.notifications_admin.schemas.claim_events import ClaimNotificationEvent


def record_claim_event(
    session: Session,
    *,
    action: str,
    actor_id: UUID,
    claim_id: UUID,
    post_id: UUID,
    recipient_id: UUID,
    previous_version: int | None,
    version: int,
    occurred_at: datetime,
):
    """Stage audit + event in the caller's transaction, without delivering before commit."""
    event = ClaimNotificationEvent(
        event_id=uuid4(),
        type=action,
        claim_id=claim_id,
        found_post_id=post_id,
        recipient_id=recipient_id,
        version=version,
        occurred_at=occurred_at,
    )
    session.add(
        AuditLog(
            actor_id=actor_id,
            action=action,
            claim_id=claim_id,
            found_post_id=post_id,
            previous_version=previous_version,
            version=version,
            occurred_at=occurred_at,
        )
    )
    session.add(
        OutboxEvent(
            event_id=event.event_id,
            type=action,
            occurred_at=occurred_at,
            payload=event.model_dump(mode="json"),
        )
    )
