from uuid import UUID, uuid4

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.session import utcnow
from app.modules.claims_returns.models.claim import Claim, ClaimEvidence
from app.modules.claims_returns.repositories.claims import ClaimRepository
from app.modules.claims_returns.schemas.claims import (
    ClaimDetail,
    ClaimPage,
    ClaimQuery,
    ClaimSummary,
    CreateClaimRequest,
    Evidence,
)
from app.modules.claims_returns.services.events import record_claim_event
from app.modules.posts.models.post import can_accept_claims
from app.modules.posts.repositories.posts import PostRepository
from app.shared.errors import DomainError


class ClaimService:
    def __init__(self, session: Session):
        self.session = session
        self.claims = ClaimRepository(session)
        self.posts = PostRepository(session)

    def create(self, actor_id: UUID, body: CreateClaimRequest) -> ClaimSummary:
        try:
            post = self.posts.get_visible_for_update(body.found_post_id)
            if post is None:
                raise DomainError(404, "POST_NOT_FOUND", "Post not found")
            if post.type != "FOUND":
                raise DomainError(422, "POST_TYPE_NOT_FOUND", "Claims require a FOUND post")
            if post.owner_id == actor_id:
                raise DomainError(403, "SELF_CLAIM_FORBIDDEN", "You cannot claim your own post")
            if self.claims.has_active(post.id, actor_id):
                raise DomainError(409, "DUPLICATE_ACTIVE_CLAIM", "An open claim already exists")
            if self.claims.has_winner(post.id):
                raise DomainError(409, "POST_ALREADY_ASSIGNED", "Post already assigned")
            if not can_accept_claims(post):
                raise DomainError(409, "POST_NOT_CLAIMABLE", "Post is not accepting claims")
            now = utcnow()
            claim = Claim(
                id=uuid4(),
                found_post_id=post.id,
                claimant_id=actor_id,
                status="PENDING",
                version=1,
                created_at=now,
                updated_at=now,
            )
            self.session.add(claim)
            self.session.flush()
            self.session.add(
                ClaimEvidence(
                    claim_id=claim.id,
                    private_content=body.evidence_description,
                    created_at=now,
                )
            )
            record_claim_event(
                self.session,
                action="claim.created",
                actor_id=actor_id,
                claim_id=claim.id,
                post_id=post.id,
                recipient_id=post.owner_id,
                previous_version=None,
                version=1,
                occurred_at=now,
            )
            self.session.flush()
            # Explicit DTO prevents accidental loading/serialization of private fields.
            claim.return_summary = None
            result = ClaimSummary.model_validate(claim)
            self.session.commit()
            return result
        except IntegrityError as exc:
            self.session.rollback()
            # Only named PostgreSQL unique violations are translated to business errors.
            constraint = getattr(getattr(exc.orig, "diag", None), "constraint_name", None)
            if constraint == "uq_claim_active_pair":
                raise DomainError(409, "DUPLICATE_ACTIVE_CLAIM", "An open claim already exists")
            if constraint == "uq_claim_post_winner":
                raise DomainError(409, "POST_ALREADY_ASSIGNED", "Post already assigned")
            raise
        except Exception:
            self.session.rollback()
            raise

    def list_me(self, actor_id: UUID, query: ClaimQuery) -> ClaimPage:
        rows = self.claims.list_related(actor_id, query)
        return ClaimPage(
            items=[ClaimSummary.model_validate(row) for row in rows[: query.page_size]],
            page=query.page,
            page_size=query.page_size,
            has_next=len(rows) > query.page_size,
        )

    def detail(self, actor_id: UUID, claim_id: UUID) -> ClaimDetail:
        claim = self.claims.get_related(claim_id, actor_id)
        if claim is None:
            raise DomainError(404, "CLAIM_NOT_FOUND", "Claim not found")
        evidence = self.claims.evidence_for_authorized_claim(claim)
        return ClaimDetail(
            **ClaimSummary.model_validate(claim).model_dump(),
            evidence=[Evidence.model_validate(item) for item in evidence],
        )
