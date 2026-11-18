import base64
import binascii
from datetime import timezone
from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import utcnow
from app.modules.claims_returns.models.claim import Claim, ClaimEvidence, ReturnRecord
from app.modules.claims_returns.repositories.claims import ClaimRepository
from app.modules.claims_returns.schemas.claims import ClaimDetail
from app.modules.claims_returns.schemas.returns import (
    AddEvidenceRequest,
    ArrangeReturnRequest,
    ReturnView,
)
from app.modules.claims_returns.services.claims import ClaimService
from app.modules.claims_returns.services.events import record_claim_event
from app.modules.posts.models.post import Post, can_accept_claims
from app.modules.posts.services.image_service import FORMATS, clean_image
from app.shared.errors import DomainError


def get_return(db: Session, return_id: UUID, actor_id: UUID) -> ReturnRecord:
    row = db.scalar(
        select(ReturnRecord)
        .join(Claim, Claim.id == ReturnRecord.claim_id)
        .join(Post, Post.id == Claim.found_post_id)
        .where(ReturnRecord.id == return_id, ClaimRepository.related(actor_id))
    )
    if row is None:
        raise DomainError(404, "RETURN_NOT_FOUND", "Return not found")
    return row


def bump_claim_version(
    service: ClaimService, claim: Claim, actor_id: UUID, recipient_id: UUID, action: str
) -> None:
    now = utcnow()
    if not service.claims.transition(claim, claim.status, claim.version, updated_at=now):
        raise DomainError(409, "CLAIM_VERSION_CONFLICT", "Claim has changed; reload before acting")
    record_claim_event(
        service.session,
        action=action,
        actor_id=actor_id,
        claim_id=claim.id,
        post_id=claim.found_post_id,
        recipient_id=recipient_id,
        previous_version=claim.version,
        version=claim.version + 1,
        occurred_at=now,
    )


def arrange_return(db: Session, body: ArrangeReturnRequest, actor_id: UUID) -> ReturnView:
    service = ClaimService(db)
    post, claim = service.lock_related(actor_id, body.claim_id)
    if post.owner_id != actor_id:
        raise DomainError(403, "RETURN_OWNER_REQUIRED", "Only the post owner may arrange a return")
    service.check_state(claim, "APPROVED", body.expected_version)
    if not can_accept_claims(post) or service.returns.get_for_update(claim.id) is not None:
        raise DomainError(409, "RETURN_STATE_CONFLICT", "Return cannot be arranged for this claim")
    now = utcnow()
    scheduled = body.scheduled_at.astimezone(timezone.utc) if body.scheduled_at else None
    if scheduled is not None and scheduled < now:
        raise DomainError(422, "INVALID_SCHEDULE", "Scheduled time must not be in the past")
    bump_claim_version(service, claim, actor_id, claim.claimant_id, "return.arranged")
    row = ReturnRecord(
        claim_id=claim.id,
        status="ARRANGED",
        arranged_at=now,
        scheduled_at=scheduled,
        meeting_note=body.meeting_note,
    )
    db.add(row)
    db.flush()
    result = ReturnView.model_validate(row)
    db.commit()
    return result


def mark_handover(db: Session, return_id: UUID, actor_id: UUID, version: int) -> ReturnView:
    found = get_return(db, return_id, actor_id)
    service = ClaimService(db)
    post, claim = service.lock_related(actor_id, found.claim_id)
    if post.owner_id != actor_id:
        raise DomainError(403, "RETURN_OWNER_REQUIRED", "Only the post owner may record handover")
    service.check_state(claim, "APPROVED", version)
    record = service.returns.get_for_update(claim.id)
    if (
        record is None
        or record.id != return_id
        or record.status != "ARRANGED"
        or not can_accept_claims(post)
    ):
        raise DomainError(409, "RETURN_STATE_CONFLICT", "Return is not ready for handover")
    bump_claim_version(service, claim, actor_id, claim.claimant_id, "return.handed_over")
    record.status = "HANDED_OVER"
    record.handed_over_at = utcnow()
    result = ReturnView.model_validate(record)
    db.commit()
    return result


def evidence_path(root: Path, claim_id: UUID, evidence_id: UUID) -> Path:
    return root / "claims" / str(claim_id) / str(evidence_id)


def add_evidence(
    db: Session, claim_id: UUID, actor_id: UUID, body: AddEvidenceRequest, root: Path
) -> ClaimDetail:
    service = ClaimService(db)
    post, claim = service.lock_related(actor_id, claim_id)
    if claim.claimant_id != actor_id:
        raise DomainError(403, "CLAIMANT_REQUIRED", "Only the claimant may submit evidence")
    service.check_state(claim, "PENDING", body.expected_version)
    if len(service.claims.evidence_for_authorized_claim(claim)) >= 10:
        raise DomainError(409, "EVIDENCE_LIMIT", "A claim may have at most 10 pieces of evidence")
    evidence = ClaimEvidence(
        id=uuid4(), claim_id=claim_id, private_content=body.evidence_description
    )
    data = None
    if body.image_base64 is not None:
        try:
            raw = base64.b64decode(body.image_base64, validate=True)
        except (ValueError, binascii.Error) as exc:
            raise DomainError(422, "INVALID_BASE64", "Image data must be valid base64") from exc
        data, mime = clean_image(raw, body.image_content_type)
        evidence.file_path = f"private-image:{mime}"
    bump_claim_version(service, claim, actor_id, post.owner_id, "claim.evidence_added")
    db.add(evidence)
    db.flush()
    result = service.detail(actor_id, claim_id)
    path = evidence_path(root, claim_id, evidence.id)
    created = False
    try:
        if data is not None:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("xb") as stream:
                created = True
                stream.write(data)
        db.commit()
    except Exception:
        db.rollback()
        if created:
            path.unlink(missing_ok=True)
        raise
    return result


def evidence_file(
    db: Session, claim_id: UUID, evidence_id: UUID, actor_id: UUID, root: Path
) -> tuple[Path, str]:
    missing = DomainError(404, "EVIDENCE_FILE_NOT_FOUND", "Evidence file not found")
    if ClaimRepository(db).related_post_id(claim_id, actor_id) is None:
        raise missing
    evidence = db.get(ClaimEvidence, evidence_id)
    if evidence is None or evidence.claim_id != claim_id or not evidence.file_path:
        raise missing
    marker, _, mime = evidence.file_path.partition(":")
    path = evidence_path(root, claim_id, evidence_id)
    if marker != "private-image" or mime not in FORMATS.values() or not path.is_file():
        raise missing
    return path, mime
