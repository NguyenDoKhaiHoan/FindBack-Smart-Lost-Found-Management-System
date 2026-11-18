from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query

from app.core.security import CurrentAdmin, CurrentUser, DatabaseSession
from app.modules.notifications_admin.schemas.reports import (
    AdminReport,
    AdminStatistics,
    ReportCreated,
    ReportList,
    ReportRequest,
    ReportReview,
    ReportStatus,
)
from app.modules.notifications_admin.services import moderation

router = APIRouter(prefix="/api/v1", tags=["Reports"])


@router.post("/reports", status_code=201)
def report_post(body: ReportRequest, db: DatabaseSession, user: CurrentUser) -> ReportCreated:
    return moderation.create_report(db, user.id, body)


@router.get("/admin/reports")
def admin_reports(
    db: DatabaseSession,
    admin: CurrentAdmin,
    status: ReportStatus | None = None,
    page: Annotated[int, Query(ge=1, le=10000)] = 1,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ReportList:
    return moderation.list_reports(db, status, page, limit)


@router.patch("/admin/reports/{id}")
def review_report(
    id: UUID, body: ReportReview, db: DatabaseSession, admin: CurrentAdmin
) -> AdminReport:
    return moderation.review_report(db, id, admin.id, body)


@router.get("/admin/statistics")
def admin_statistics(db: DatabaseSession, admin: CurrentAdmin) -> AdminStatistics:
    return moderation.statistics(db)
