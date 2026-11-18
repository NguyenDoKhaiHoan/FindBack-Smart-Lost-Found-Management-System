from uuid import UUID

from app.shared.errors import DomainError

from ..repositories.snapshots import SnapshotReader, fingerprint
from ..schemas.contracts import MatchesQuery, MatchesResponse, MatchItem, Pagination
from .scoring import RULE_VERSION, eligible


def get_matches(
    reader: SnapshotReader, query: MatchesQuery, *, match_id: UUID | None = None
) -> MatchesResponse:
    snapshot = reader.read(query.post_id)
    source = snapshot.posts.get(query.post_id)
    if source is None or not source.is_public:
        raise DomainError(404, "POST_NOT_FOUND", "Không tìm thấy tin công khai.")
    if not eligible(source):
        raise DomainError(409, "POST_NOT_MATCHABLE", "Tin không đủ điều kiện nhận gợi ý.")
    generation = snapshot.generation
    current = [
        source,
        *(
            item
            for item in snapshot.posts.values()
            if eligible(item) and item.post.type != source.post.type
        ),
    ]
    if (
        generation is None
        or generation.source_id != query.post_id
        or generation.rule_version != RULE_VERSION
        or any(generation.inputs.get(item.post.id) != fingerprint(item) for item in current)
    ):
        raise DomainError(
            409,
            "MATCHES_NOT_READY",
            "Gợi ý chưa sẵn sàng. Vui lòng thử lại sau khi hệ thống tính lại.",
        )

    items = []
    for pair in generation.pairs:
        if match_id is not None and pair.id != match_id:
            continue
        candidate_id = pair.found_post_id if source.post.type == "LOST" else pair.lost_post_id
        candidate = snapshot.posts.get(candidate_id)
        if (
            candidate is None
            or not eligible(candidate)
            or candidate.post.id == source.post.id
            or candidate.post.type == source.post.type
            or pair.score < query.min_score
        ):
            continue
        items.append((pair, candidate.post))
    items.sort(
        key=lambda entry: (-entry[0].score, abs(entry[0].delta_microseconds), entry[1].id.int)
    )
    total = len(items)
    total_pages = (total + query.page_size - 1) // query.page_size
    start = (query.page - 1) * query.page_size
    return MatchesResponse(
        source_post_id=query.post_id,
        rule_version=generation.rule_version,
        calculated_at=generation.calculated_at,
        min_score=float(query.min_score),
        items=[
            MatchItem(
                id=pair.id,
                lost_post_id=pair.lost_post_id,
                found_post_id=pair.found_post_id,
                candidate=candidate,
                score=pair.score,
                level="HIGH" if pair.score >= 75 else "POSSIBLE",
                score_details=pair.details,
                explanation=pair.explanation,
            )
            for pair, candidate in items[start : start + query.page_size]
        ],
        pagination=Pagination(
            page=query.page,
            page_size=query.page_size,
            total=total,
            total_pages=total_pages,
            has_next=query.page < total_pages,
            has_previous=query.page > 1 and total > 0,
        ),
    )
