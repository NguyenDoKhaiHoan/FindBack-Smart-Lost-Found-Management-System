from datetime import datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.modules.claims_returns.models.claim import ReturnRecord


class ReturnRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_for_update(self, claim_id: UUID) -> ReturnRecord | None:
        return self.session.scalar(
            select(ReturnRecord)
            .where(ReturnRecord.claim_id == claim_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )

    def confirm(self, record: ReturnRecord, actor_id: UUID, occurred_at: datetime) -> bool:
        result = self.session.execute(
            update(ReturnRecord)
            .where(
                ReturnRecord.id == record.id,
                ReturnRecord.status == "HANDED_OVER",
                ReturnRecord.confirmed_at.is_(None),
                ReturnRecord.confirmed_by.is_(None),
                ReturnRecord.handed_over_at.is_not(None),
            )
            .values(status="CONFIRMED", confirmed_by=actor_id, confirmed_at=occurred_at)
            .execution_options(synchronize_session=False)
        )
        return result.rowcount == 1
