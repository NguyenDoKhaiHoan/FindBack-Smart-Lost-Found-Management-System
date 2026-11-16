from datetime import datetime
from enum import Enum
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints


class Schema(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)


class ClaimStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    RETURNED = "RETURNED"


class CreateClaimRequest(Schema):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "found_post_id": "55b40512-fcb0-5c7a-b84a-8ec95e3c058f",
                    "evidence_description": "Du lieu gia lap: mat trong co ky hieu DEMO-123.",
                }
            ]
        },
    )

    found_post_id: UUID
    evidence_description: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=10, max_length=5000)
    ]


class ClaimQuery(Schema):
    relation: Literal["claimant", "reviewer", "all"] = "claimant"
    status: ClaimStatus | None = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class NoQuery(Schema):
    pass


class ReturnSummary(Schema):
    id: UUID
    status: Literal["ARRANGED", "HANDED_OVER", "CONFIRMED"]
    handed_over_at: datetime | None
    confirmed_at: datetime | None


class ClaimSummary(Schema):
    id: UUID
    found_post_id: UUID
    claimant_id: UUID
    status: ClaimStatus
    version: int = Field(ge=1)
    created_at: datetime
    updated_at: datetime
    decided_by: UUID | None
    decided_at: datetime | None
    rejection_reason: str | None
    returned_by: UUID | None
    returned_at: datetime | None
    return_summary: ReturnSummary | None


class Evidence(Schema):
    id: UUID
    private_content: str
    created_at: datetime


class ClaimDetail(ClaimSummary):
    evidence: list[Evidence]


class ClaimPage(Schema):
    items: list[ClaimSummary] = Field(max_length=100)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)
    has_next: bool
