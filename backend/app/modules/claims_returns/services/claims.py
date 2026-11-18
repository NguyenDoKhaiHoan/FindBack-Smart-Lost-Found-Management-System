from uuid import UUID, uuid4

from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session

from app.db.session import utcnow
from app.modules.claims_returns.models.claim import Claim, ClaimEvidence
from app.modules.claims_returns.repositories.claims import ClaimRepository
from app.modules.claims_returns.repositories.returns import ReturnRepository
from app.modules.claims_returns.schemas.claims import (
    ApproveClaimRequest,
    ClaimDetail,
    ClaimPage,
    ClaimQuery,
    ClaimSummary,
    CompleteClaimRequest,
    CreateClaimRequest,
    Evidence,
    RejectClaimRequest,
)
from app.modules.claims_returns.services.events import record_claim_event
from app.modules.posts.models.post import can_accept_claims
from app.modules.posts.repositories.posts import PostRepository
from app.modules.posts.services.posts import PostService
from app.shared.errors import DomainError


class ClaimService:
    def __init__(self, session: Session):
        self.session = session
        self.claims = ClaimRepository(session)
        self.posts = PostRepository(session)
        self.returns = ReturnRepository(session)
        self.post_service = PostService(session)

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

    def approve(self, actor_id: UUID, claim_id: UUID, body: ApproveClaimRequest) -> ClaimSummary:
        return self._mutate(actor_id, claim_id, body, "approved")

    def reject(self, actor_id: UUID, claim_id: UUID, body: RejectClaimRequest) -> ClaimSummary:
        return self._mutate(actor_id, claim_id, body, "rejected")

    def complete(self, actor_id: UUID, claim_id: UUID, body: CompleteClaimRequest) -> ClaimSummary:
        return self._mutate(actor_id, claim_id, body, "completed")

    def _mutate(self, actor_id, claim_id, body, action) -> ClaimSummary:
        for attempt in range(3):
            try:
                result = self._mutate_once(actor_id, claim_id, body, action)
                self.session.commit()
                return result
            except IntegrityError as exc:
                self.session.rollback()
                constraint = getattr(getattr(exc.orig, "diag", None), "constraint_name", None)
                if constraint == "uq_claim_post_winner":
                    raise DomainError(
                        409, "POST_ALREADY_ASSIGNED", "Post already assigned"
                    ) from None
                raise
            except DBAPIError as exc:
                self.session.rollback()
                if getattr(exc.orig, "sqlstate", None) not in {"40001", "40P01"} or attempt == 2:
                    raise
                # Retry the entire aborted transaction, before any external delivery.
            except Exception:
                self.session.rollback()
                raise
        raise AssertionError("Unreachable transaction retry state")

    def _mutate_once(self, actor_id, claim_id, body, action) -> ClaimSummary:
        post, claim = self.lock_related(actor_id, claim_id)
        if action in {"approved", "rejected"}:
            allowed = actor_id == post.owner_id and actor_id != claim.claimant_id
        else:
            allowed = actor_id == claim.claimant_id
        if not allowed:
            raise DomainError(403, "CLAIM_ACTION_FORBIDDEN", "This action is not permitted")
        expected_status = "APPROVED" if action == "completed" else "PENDING"
        self.check_state(claim, expected_status, body.expected_version)
        return self._apply_decision(actor_id, post, claim, body, action, expected_status)

    def lock_related(self, actor_id: UUID, claim_id: UUID):
        not_found = DomainError(404, "CLAIM_NOT_FOUND", "Claim not found")
        post_id = self.claims.related_post_id(claim_id, actor_id)
        if post_id is None:
            raise not_found
        post = self.posts.get_for_update(post_id)
        claim = self.claims.get_for_update(claim_id)
        if post is None or claim is None or claim.found_post_id != post.id:
            raise not_found
        # Recheck current ownership and claimant after acquiring locks.
        if actor_id not in {post.owner_id, claim.claimant_id}:
            raise not_found
        return post, claim

    @staticmethod
    def check_state(claim, expected_status, expected_version):
        if claim.status != expected_status:
            raise DomainError(409, "CLAIM_STATE_CONFLICT", "Claim is not in the required state")
        if claim.version != expected_version:
            raise DomainError(
                409, "CLAIM_VERSION_CONFLICT", "Claim has changed; reload before acting"
            )

    def _apply_decision(self, actor_id, post, claim, body, action, expected_status) -> ClaimSummary:
        now = utcnow()
        if action == "approved":
            if self.claims.has_winner(post.id, exclude_claim_id=claim.id):
                raise DomainError(409, "POST_ALREADY_ASSIGNED", "Post already assigned")
            if post.type != "FOUND" or not can_accept_claims(post):
                raise DomainError(409, "POST_NOT_CLAIMABLE", "Post is not accepting claims")
            if not self.claims.has_valid_evidence(claim.id):
                raise DomainError(422, "EVIDENCE_REQUIRED", "Valid claim evidence is required")
            changes = dict(status="APPROVED", decided_by=actor_id, decided_at=now)
        elif action == "rejected":
            changes = dict(
                status="REJECTED",
                decided_by=actor_id,
                decided_at=now,
                rejection_reason=body.reason,
            )
        else:
            record = self.returns.get_for_update(claim.id)
            if (
                record is None
                or record.status != "HANDED_OVER"
                or record.handed_over_at is None
                or record.handed_over_at < claim.decided_at
                or record.handed_over_at > now
                or record.confirmed_at is not None
                or record.confirmed_by is not None
            ):
                raise DomainError(409, "RETURN_NOT_READY", "A handed-over Return is required")
            if not self.returns.confirm(record, actor_id, now):
                raise DomainError(
                    409, "RETURN_NOT_READY", "Return has changed; reload before acting"
                )
            changes = dict(status="RETURNED", returned_by=actor_id, returned_at=now)
            self.post_service.close_for_completed_claim(post, claim.id, now)
        if not self.claims.transition(
            claim,
            expected_status,
            body.expected_version,
            updated_at=now,
            **changes,
        ):
            raise DomainError(
                409, "CLAIM_VERSION_CONFLICT", "Claim has changed; reload before acting"
            )
        record_claim_event(
            self.session,
            action=f"claim.{action}",
            actor_id=actor_id,
            claim_id=claim.id,
            post_id=post.id,
            recipient_id=post.owner_id if action == "completed" else claim.claimant_id,
            previous_version=body.expected_version,
            version=body.expected_version + 1,
            occurred_at=now,
        )
        self.session.flush()
        return ClaimSummary.model_validate(self.claims.get_related(claim.id, actor_id))

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
