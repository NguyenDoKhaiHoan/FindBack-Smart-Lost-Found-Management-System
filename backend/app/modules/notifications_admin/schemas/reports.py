from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

ReportStatus = Literal["PENDING", "REVIEWING", "RESOLVED", "DISMISSED"]


class ReportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    post_id: UUID
    reason: str = Field(min_length=3, max_length=2000)


class ReportReview(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    status: Literal["REVIEWING", "RESOLVED", "DISMISSED"]
    resolution_note: str = Field(min_length=1, max_length=2000)


class ReportCreated(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    post_id: UUID
    status: ReportStatus
    created_at: datetime


class AdminReport(ReportCreated):
    reporter_id: UUID
    reason: str
    reviewed_by: UUID | None
    reviewed_at: datetime | None
    resolution_note: str | None


class ReportList(BaseModel):
    items: list[AdminReport]
    page: int
    limit: int
    total: int
    total_pages: int


class AdminStatistics(BaseModel):
    users: int
    posts: int
    public_posts: int
    hidden_posts: int
    claims: int
    completed_returns: int
    pending_reports: int
    resolved_reports: int
