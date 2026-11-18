from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.db.session import utcnow
from app.modules.claims_returns.models.claim import Claim, ReturnRecord
from app.modules.identity.models.user import User
from app.modules.notifications_admin.models.notification import Notification
from app.modules.notifications_admin.models.report import ModerationAudit, Report
from app.modules.notifications_admin.schemas.admin_post import (
    AdminPostItemResponse,
    AdminPostListResponse,
    AdminPostPagination,
    PostModerationRequest,
    PostModerationResponse,
)
from app.modules.notifications_admin.schemas.reports import (
    AdminReport,
    AdminStatistics,
    ReportCreated,
    ReportList,
    ReportRequest,
    ReportReview,
    ReportStatus,
)
from app.modules.posts.models.post import Post
from app.modules.posts.repositories.posts import PostRepository, public_post_query
from app.shared.errors import DomainError


def list_admin_posts(
    db: Session, page: int, limit: int, status: str | None, type_: str | None, q: str | None
) -> AdminPostListResponse:
    visible = (Post.is_hidden.is_(False), Post.deleted_at.is_(None))
    stmt = select(Post)
    if status == "HIDDEN":
        stmt = stmt.where(or_(Post.is_hidden.is_(True), Post.deleted_at.is_not(None)))
    elif status is not None:
        stmt = stmt.where(*visible, Post.status == ("OPEN" if status == "ACTIVE" else status))
    if type_ is not None:
        stmt = stmt.where(Post.type == type_)
    if q:
        stmt = stmt.where(
            or_(
                *(
                    field.icontains(q, autoescape=True)
                    for field in (
                        Post.title,
                        Post.description,
                        Post.location,
                    )
                )
            )
        )
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db.scalars(
        stmt.order_by(Post.created_at.desc(), Post.id.desc())
        .offset((page - 1) * limit)
        .limit(limit)
    )
    return AdminPostListResponse(
        items=[AdminPostItemResponse.model_validate(row) for row in rows],
        pagination=AdminPostPagination(
            page=page, limit=limit, total=total, total_pages=(total + limit - 1) // limit
        ),
    )


def moderate_post(
    db: Session, post_id: UUID, admin_id: UUID, body: PostModerationRequest
) -> PostModerationResponse:
    post = PostRepository(db).get_for_update(post_id)
    if post is None or post.deleted_at is not None:
        raise DomainError(404, "POST_NOT_FOUND", "Post not found")
    if post.status == "CLOSED":
        raise DomainError(409, "POST_STATE_CONFLICT", "A closed post cannot be hidden")
    if post.is_hidden and post.moderated_by is not None:
        return PostModerationResponse.model_validate(post)
    if db.scalar(
        select(Claim.id).where(Claim.found_post_id == post_id, Claim.status == "APPROVED").limit(1)
    ):
        raise DomainError(409, "POST_HAS_ACTIVE_RETURN", "An approved claim is waiting for return")
    now = utcnow()
    post.is_hidden = True
    post.moderated_by = admin_id
    post.moderated_at = post.updated_at = now
    post.moderation_reason = body.reason
    db.add(ModerationAudit(actor_id=admin_id, post_id=post_id, action="POST_HIDDEN"))
    db.add(
        Notification(
            recipient_id=post.owner_id,
            type="POST_HIDDEN",
            title="Bài đăng đã bị ẩn",
            message="Bài đăng của bạn đã bị ẩn sau khi kiểm duyệt.",
            resource_type="POST",
            resource_id=post.id,
        )
    )
    result = PostModerationResponse(
        id=post.id,
        status="HIDDEN",
        moderated_by=admin_id,
        moderated_at=now,
        moderation_reason=body.reason,
    )
    db.commit()
    return result


def create_report(db: Session, actor_id: UUID, body: ReportRequest) -> ReportCreated:
    post = PostRepository(db).get_visible_for_update(body.post_id)
    if post is None:
        raise DomainError(404, "POST_NOT_FOUND", "Post not found")
    if db.scalar(
        select(Report.id).where(
            Report.post_id == post.id,
            Report.reporter_id == actor_id,
            Report.status.in_(("PENDING", "REVIEWING")),
        )
    ):
        raise DomainError(
            409, "DUPLICATE_OPEN_REPORT", "You already have an open report for this post"
        )
    report = Report(post_id=post.id, reporter_id=actor_id, reason=body.reason)
    db.add(report)
    db.flush()
    result = ReportCreated.model_validate(report)
    db.commit()
    return result


def review_report(db: Session, report_id: UUID, admin_id: UUID, body: ReportReview) -> AdminReport:
    report = db.scalar(select(Report).where(Report.id == report_id).with_for_update())
    if report is None:
        raise DomainError(404, "REPORT_NOT_FOUND", "Report not found")
    if report.status not in ("PENDING", "REVIEWING") or report.status == body.status:
        raise DomainError(409, "REPORT_STATE_CONFLICT", "Report cannot transition to that status")
    report.status = body.status
    report.reviewed_at = utcnow()
    report.reviewed_by = admin_id
    report.resolution_note = body.resolution_note
    db.add(
        ModerationAudit(
            actor_id=admin_id,
            post_id=report.post_id,
            report_id=report.id,
            action=f"REPORT_{body.status}",
        )
    )
    result = AdminReport.model_validate(report)
    db.commit()
    return result


def list_reports(db: Session, status: ReportStatus | None, page: int, limit: int) -> ReportList:
    stmt = select(Report)
    if status is not None:
        stmt = stmt.where(Report.status == status)
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db.scalars(
        stmt.order_by(Report.created_at.desc(), Report.id.desc())
        .offset((page - 1) * limit)
        .limit(limit)
    )
    return ReportList(
        items=[AdminReport.model_validate(row) for row in rows],
        page=page,
        limit=limit,
        total=total,
        total_pages=(total + limit - 1) // limit,
    )


def statistics(db: Session) -> AdminStatistics:
    def count(statement):
        return select(func.count()).select_from(statement.subquery()).scalar_subquery()

    row = (
        db.execute(
            select(
                count(select(User)).label("users"),
                count(select(Post).where(Post.deleted_at.is_(None))).label("posts"),
                count(public_post_query()).label("public_posts"),
                count(
                    select(Post).where(Post.is_hidden.is_(True), Post.deleted_at.is_(None))
                ).label("hidden_posts"),
                count(select(Claim)).label("claims"),
                count(select(ReturnRecord).where(ReturnRecord.status == "CONFIRMED")).label(
                    "completed_returns"
                ),
                count(select(Report).where(Report.status.in_(("PENDING", "REVIEWING")))).label(
                    "pending_reports"
                ),
                count(select(Report).where(Report.status == "RESOLVED")).label("resolved_reports"),
            )
        )
        .mappings()
        .one()
    )
    return AdminStatistics.model_validate(row)
