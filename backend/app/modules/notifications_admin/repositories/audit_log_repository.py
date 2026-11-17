from typing import Any
import uuid
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.notifications_admin.models.audit_log import AuditLog


class AuditLogRepository:
    """Async repository for AuditLog persistence."""

    async def create(
        self,
        session: AsyncSession,
        actor_id: uuid.UUID,
        action: str,
        target_type: str,
        target_id: uuid.UUID,
        reason: str,
        old_status: str | None = None,
        new_status: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AuditLog:
        """Creates and flushes a new audit log entry."""
        audit_log = AuditLog(
            actor_id=actor_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            reason=reason,
            old_status=old_status,
            new_status=new_status,
            metadata_json=metadata,
        )
        session.add(audit_log)
        await session.flush()
        return audit_log
