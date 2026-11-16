from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ClaimNotificationEvent(BaseModel):
    """Private-data-free contract consumed by Notifications after the outbox commit."""

    model_config = ConfigDict(extra="forbid")
    event_id: UUID
    type: Literal["claim.created", "claim.approved", "claim.rejected", "claim.completed"]
    claim_id: UUID
    found_post_id: UUID
    recipient_id: UUID
    version: int = Field(ge=1)
    occurred_at: datetime
