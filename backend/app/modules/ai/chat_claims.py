from datetime import timedelta, timezone
from typing import Literal
from uuid import UUID

from sqlalchemy.orm import Session

from app.modules.ai.schemas import AIInput, ChatResult
from app.modules.claims_returns.repositories.claims import ClaimRepository
from app.modules.claims_returns.schemas.claims import ClaimQuery, ClaimStatus
from app.modules.posts.models.post import Post
from app.modules.posts.repositories.posts import public_post_query

LOCAL_TZ = timezone(timedelta(hours=7))
STATUS_LABELS = {
    ClaimStatus.PENDING: "Chờ duyệt",
    ClaimStatus.APPROVED: "Đã duyệt",
    ClaimStatus.REJECTED: "Đã từ chối",
    ClaimStatus.RETURNED: "Đã trao trả",
}
RELATION_LABELS = {
    "claimant": "bạn đã gửi",
    "reviewer": "gửi đến tin của bạn",
    "all": "liên quan tới tài khoản của bạn",
}


class ClaimStatusArgs(AIInput):
    relation: Literal["claimant", "reviewer", "all"]
    status: ClaimStatus | None
    handover: bool


def claim_status(db: Session, actor: UUID, args: ClaimStatusArgs) -> ChatResult:
    status = args.status or (ClaimStatus.APPROVED if args.handover else None)
    page_size = 5
    query = ClaimQuery(relation=args.relation, status=status, page_size=page_size)
    claims = ClaimRepository(db).list_related(actor, query)
    relation = RELATION_LABELS[args.relation]
    status_label = f" ở trạng thái {STATUS_LABELS[status]}" if status is not None else ""
    if not claims:
        return ChatResult(reply=f"Mình chưa thấy yêu cầu nhận đồ {relation}{status_label}.")

    titles = dict(
        db.execute(
            public_post_query()
            .where(Post.id.in_([claim.found_post_id for claim in claims[:page_size]]))
            .with_only_columns(Post.id, Post.title)
        ).all()
    )
    lines = [f"Yêu cầu nhận đồ {relation}{status_label} gần nhất."]
    for index, claim in enumerate(claims[:page_size], 1):
        title = titles.get(claim.found_post_id) or "Tin nhận đồ"
        detail = STATUS_LABELS[claim.status]
        if claim.status == ClaimStatus.APPROVED:
            handover = claim.return_summary
            if handover and handover.status == "HANDED_OVER":
                detail += ", đã ghi nhận bàn giao"
            elif handover and handover.scheduled_at:
                scheduled = handover.scheduled_at.astimezone(LOCAL_TZ)
                detail += f", lịch hẹn {scheduled:%H:%M ngày %d/%m/%Y}"
            else:
                detail += ", chưa có giờ hẹn"
        lines.append(f"{index}. {title} · {detail}")
    lines.append("Mở Yêu cầu nhận đồ để xem chi tiết và các thao tác hiện có.")
    return ChatResult(reply="\n".join(lines))
