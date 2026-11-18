from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, joinedload

from app.db.session import utcnow
from app.modules.matching.models.generation import MatchGeneration, MatchResult
from app.modules.matching.repositories.snapshots import Generation, MatchSnapshot, fingerprint
from app.modules.matching.schemas.contracts import (
    Category,
    Location,
    PublicPost,
    PublicPostInput,
    ScoreDetails,
)
from app.modules.matching.services.scoring import (
    RULE_VERSION,
    ScoredPair,
    eligible,
    rank_candidates,
)
from app.modules.posts.models.post import Post, can_accept_claims
from app.modules.posts.repositories.posts import PostRepository, public_post_query
from app.modules.posts.services.catalog import LOCATIONS
from app.shared.errors import DomainError


def project_post(post: Post) -> PublicPost | None:
    if not all((post.title, post.description, post.category, post.location_code, post.event_time)):
        return None
    return PublicPost(
        id=post.id,
        type=post.type,
        title=post.title,
        description=post.description,
        category=Category(id=post.category.id, name=post.category.name),
        location=Location(code=post.location_code, name=LOCATIONS[post.location_code]),
        event_time=post.event_time,
        status=post.status,
        color_code=post.color_code,
        public_attributes={
            key: value for key in ("brand", "material") if (value := getattr(post, key))
        },
        created_at=post.created_at,
    )


def decode_pair(row: MatchResult) -> ScoredPair:
    data = row.score_data
    return ScoredPair(
        row.id,
        UUID(data["lost"]),
        UUID(data["found"]),
        data["score"],
        ScoreDetails.model_validate(data["details"]),
        data["explanation"],
        data["delta"],
    )


class DatabaseMatchingStore:
    def __init__(self, db: Session):
        self.db = db

    def public_inputs(self, source_id: UUID) -> dict[UUID, PublicPostInput]:
        source = self.db.get(Post, source_id)
        if source is None or source.deleted_at is not None or source.is_hidden:
            return {}
        statement = (
            public_post_query()
            .where((Post.id == source_id) | ((Post.type != source.type) & (Post.status == "OPEN")))
            .options(joinedload(Post.category))
        )
        inputs = {}
        for row in self.db.scalars(statement):
            public = project_post(row)
            if public is None and row.id == source_id:
                raise DomainError(
                    409, "POST_NOT_MATCHABLE", "The post lacks public matching fields"
                )
            if public is not None:
                inputs[row.id] = PublicPostInput(
                    post=public, is_public=True, matching_eligible=can_accept_claims(row)
                )
        return inputs

    def read(self, source_id: UUID) -> MatchSnapshot:
        posts = self.public_inputs(source_id)
        if source_id not in posts:
            return MatchSnapshot(posts, None)
        # Serialize readers with recalculate to keep metadata and match rows consistent.
        row = self.db.scalar(
            select(MatchGeneration)
            .where(MatchGeneration.source_id == source_id)
            .with_for_update(read=True)
            .execution_options(populate_existing=True)
        )
        if row is None:
            return MatchSnapshot(posts, None)
        pairs = self.db.scalars(select(MatchResult).where(MatchResult.source_id == source_id))
        return MatchSnapshot(
            posts,
            Generation(
                source_id,
                row.rule_version,
                row.calculated_at,
                {UUID(post_id): digest for post_id, digest in row.fingerprints.items()},
                tuple(decode_pair(pair) for pair in pairs),
            ),
        )

    def recalculate(self, source_id: UUID, actor_id: UUID, *, admin: bool) -> None:
        post = PostRepository(self.db).get_visible_for_update(source_id)
        if post is None:
            raise DomainError(404, "POST_NOT_FOUND", "Public post not found")
        if not admin and post.owner_id != actor_id:
            raise DomainError(403, "POST_OWNER_REQUIRED", "Only the owner may recalculate matches")
        posts = self.public_inputs(source_id)
        source = posts.get(source_id)
        if source is None or not eligible(source):
            raise DomainError(409, "POST_NOT_MATCHABLE", "The post is not eligible for matching")
        candidates = [
            item for item in posts.values() if eligible(item) and item.post.type != source.post.type
        ]
        generation = self.db.get(MatchGeneration, source_id)
        if generation is None:
            generation = MatchGeneration(source_id=source_id)
            self.db.add(generation)
        generation.rule_version = RULE_VERSION
        generation.calculated_at = utcnow()
        generation.fingerprints = {
            str(item.post.id): fingerprint(item) for item in [source, *candidates]
        }
        self.db.flush()
        self.db.execute(delete(MatchResult).where(MatchResult.source_id == source_id))
        self.db.add_all(
            MatchResult(
                source_id=source_id,
                id=pair.id,
                score_data={
                    "lost": str(pair.lost_post_id),
                    "found": str(pair.found_post_id),
                    "score": pair.score,
                    "details": pair.details.model_dump(mode="json"),
                    "explanation": pair.explanation,
                    "delta": pair.delta_microseconds,
                },
            )
            for pair in rank_candidates(source, candidates)
        )
        self.db.commit()
