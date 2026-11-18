from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import AwareDatetime, Field, StringConstraints, model_validator

from app.modules.claims_returns.schemas.claims import ApproveClaimRequest, ReturnSummary


class ArrangeReturnRequest(ApproveClaimRequest):
    claim_id: UUID
    scheduled_at: AwareDatetime | None = None
    meeting_note: (
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]
        | None
    ) = None


class ReturnView(ReturnSummary):
    claim_id: UUID
    arranged_at: datetime | None
    scheduled_at: datetime | None
    meeting_note: str | None


class AddEvidenceRequest(ApproveClaimRequest):
    evidence_description: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=10, max_length=5000)
    ]
    image_base64: str | None = Field(default=None, max_length=6990508)
    image_content_type: str | None = Field(default=None, max_length=100)

    @model_validator(mode="after")
    def require_image_type(self):
        if (self.image_base64 is None) != (self.image_content_type is None):
            raise ValueError("Provide both image_base64 and image_content_type")
        return self
