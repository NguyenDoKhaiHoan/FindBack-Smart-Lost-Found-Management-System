from uuid import UUID

from sqlalchemy import or_, select, update
from sqlalchemy.orm import Session, joinedload

from app.modules.claims_returns.models.claim import Claim, ClaimEvidence
from app.modules.claims_returns.schemas.claims import ClaimQuery
from app.modules.posts.models.post import Post


class ClaimRepository:
    def __init__(self, session: Session):
        self.session = session

    def has_active(self, post_id: UUID, claimant_id: UUID) -> bool:
        return (
            self.session.scalar(
                select(Claim.id)
                .where(
                    Claim.found_post_id == post_id,
                    Claim.claimant_id == claimant_id,
                    Claim.status.in_(("PENDING", "APPROVED")),
                )
                .limit(1)
            )
            is not None
        )

    def has_winner(self, post_id: UUID, *, exclude_claim_id: UUID | None = None) -> bool:
        return (
            self.session.scalar(
                select(Claim.id)
                .where(
                    Claim.found_post_id == post_id,
                    Claim.status.in_(("APPROVED", "RETURNED")),
                    or_(exclude_claim_id is None, Claim.id != exclude_claim_id),
                )
                .limit(1)
            )
            is not None
        )

    def related_post_id(self, claim_id: UUID, actor_id: UUID) -> UUID | None:
        # Discover only the parent ID; do not lock Claim before Post or load evidence.
        return self.session.scalar(
            select(Claim.found_post_id)
            .join(Post, Post.id == Claim.found_post_id)
            .where(Claim.id == claim_id, self.related(actor_id))
        )

    def get_for_update(self, claim_id: UUID) -> Claim | None:
        return self.session.scalar(
            select(Claim)
            .where(Claim.id == claim_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )

    def transition(
        self, claim: Claim, expected_status: str, expected_version: int, **values
    ) -> bool:
        result = self.session.execute(
            update(Claim)
            .where(
                Claim.id == claim.id,
                Claim.status == expected_status,
                Claim.version == expected_version,
            )
            .values(**values, version=expected_version + 1)
            .execution_options(synchronize_session=False)
        )
        return result.rowcount == 1

    def has_valid_evidence(self, claim_id: UUID) -> bool:
        contents = self.session.scalars(
            select(ClaimEvidence.private_content).where(ClaimEvidence.claim_id == claim_id)
        )
        return any(content and content.strip() for content in contents)

    @staticmethod
    def related(actor_id: UUID):
        return or_(Claim.claimant_id == actor_id, Post.owner_id == actor_id)

    def list_related(self, actor_id: UUID, query: ClaimQuery) -> list[Claim]:
        relation = {
            "claimant": Claim.claimant_id == actor_id,
            "reviewer": Post.owner_id == actor_id,
            "all": self.related(actor_id),
        }[query.relation]
        statement = select(Claim).join(Post, Post.id == Claim.found_post_id).where(relation)
        if query.status is not None:
            statement = statement.where(Claim.status == query.status.value)
        return list(
            self.session.scalars(
                statement.options(joinedload(Claim.return_summary))
                .order_by(Claim.created_at.desc(), Claim.id.desc())
                .offset((query.page - 1) * query.page_size)
                .limit(query.page_size + 1)
            )
        )

    def get_related(self, claim_id: UUID, actor_id: UUID) -> Claim | None:
        return self.session.scalar(
            select(Claim)
            .join(Post, Post.id == Claim.found_post_id)
            .where(Claim.id == claim_id, self.related(actor_id))
            .options(joinedload(Claim.return_summary))
            .execution_options(populate_existing=True)
        )

    def evidence_for_authorized_claim(self, claim: Claim) -> list[ClaimEvidence]:
        # Called only after get_related has established access to this exact claim.
        return list(
            self.session.scalars(
                select(ClaimEvidence)
                .where(ClaimEvidence.claim_id == claim.id)
                .order_by(ClaimEvidence.created_at, ClaimEvidence.id)
            )
        )
