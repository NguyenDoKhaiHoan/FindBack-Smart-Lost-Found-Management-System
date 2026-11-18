from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ClaimNotificationEvent(BaseModel):
    """Claim and return events carry only IDs, version and timestamp."""

    model_config = ConfigDict(extra="forbid")
    event_id: UUID
    type: Literal[
        "claim.created",
        "claim.approved",
        "claim.rejected",
        "claim.completed",
        "claim.evidence_added",
        "return.arranged",
        "return.handed_over",
    ]
    claim_id: UUID
    found_post_id: UUID
    recipient_id: UUID
    version: int = Field(ge=1)
    occurred_at: datetime
