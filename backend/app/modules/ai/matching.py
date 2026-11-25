from uuid import UUID

from sqlalchemy import update
from sqlalchemy.orm import Session, selectinload, undefer

from app.modules.ai.inference import TEXT_KEY, cosine_similarity, embedding_key, text_vectors
from app.modules.ai.runtime import AIRuntime
from app.modules.ai.schemas import ItemCard, MatchCard, MatchesResponse
from app.modules.matching.services.scoring import tokens
from app.modules.posts.models.post import Post, can_accept_claims
from app.modules.posts.repositories.posts import public_post_query
from app.shared.errors import DomainError


def open_posts():
    return public_post_query().where(Post.status == "OPEN", Post.completed_claim_id.is_(None))


def text_embeddings(db: Session, runtime: AIRuntime, posts: list[Post]):
    vectors = {}
    missing = []
    for post in posts:
        text = "\n".join(value.strip() for value in (post.title, post.description) if value)
        if not text.strip():
            continue
        key = embedding_key(TEXT_KEY, text)
        if post.ai_embedding_key == key and post.ai_embedding:
            vectors[post.id] = post.ai_embedding
        else:
            missing.append((post, key, text))

    limit = runtime.settings.ai_text_index_batch
    batch = missing[:limit]
    if batch:
        db.commit()
        texts = [text for _, _, text in batch]
        for (post, key, _), vector in zip(batch, text_vectors(runtime, texts), strict=True):
            db.execute(
                update(Post)
                .where(
                    Post.id == post.id,
                    Post.title == post.title,
                    Post.description == post.description,
                )
                .values(ai_embedding_key=key, ai_embedding=vector)
                .execution_options(synchronize_session=False)
            )
            vectors[post.id] = vector
        db.commit()
    return vectors, len(missing) > limit


def time_gap_hours(first: Post, second: Post) -> float | None:
    lost, found = (first, second) if first.type == "LOST" else (second, first)
    if lost.event_time is None or found.event_time is None:
        return None
    return (found.event_time - lost.event_time).total_seconds() / 3600


def score_pair(first: Post, second: Post, text: float | None):
    if first.id == second.id or {first.type, second.type} != {"LOST", "FOUND"}:
        return None
    if not can_accept_claims(first) or not can_accept_claims(second):
        return None
    hours = time_gap_hours(first, second)
    if hours is not None and hours < 0:
        return None

    parts: list[tuple[float, float]] = []
    reasons = []
    if text is not None:
        parts.append((0.50, text))
        if text >= 0.55:
            reasons.append("Tiêu đề hoặc mô tả tương tự")

    same_category = False
    same_color = False
    if first.category_id and second.category_id:
        same_category = first.category_id == second.category_id
        parts.append((0.12, float(same_category)))
        if same_category:
            reasons.append("Cùng danh mục")

    first_color = tokens(first.color_code or first.color or "")
    second_color = tokens(second.color_code or second.color or "")
    if first_color and second_color:
        same_color = first_color == second_color
        parts.append((0.08, float(same_color)))
        if same_color:
            reasons.append("Cùng màu sắc")

    first_location = tokens(first.location or first.area or "")
    second_location = tokens(second.location or second.area or "")
    location = 0.0
    same_region = (
        first.location_code not in (None, "OTHER") and first.location_code == second.location_code
    )
    both_regions = all(
        code not in (None, "OTHER") for code in (first.location_code, second.location_code)
    )
    if first_location and second_location or both_regions:
        if first_location and second_location:
            location = len(first_location & second_location) / len(first_location | second_location)
        if both_regions:
            location = max(location, 0.25) if same_region else 0.0
        parts.append((0.20, location))
        if location >= 0.5:
            reasons.append("Thông tin địa điểm tương tự")
        elif same_region:
            reasons.append("Cùng khu vực")

    if hours is not None:
        parts.append((0.10, 1 / (1 + hours / 72)))
        if hours <= 72:
            reasons.append("Thời điểm mất và nhặt cách nhau tối đa 3 ngày")

    if not (
        (text is not None and text >= 0.55) or (same_category and (same_color or location >= 0.5))
    ):
        return None
    score = sum(weight * value for weight, value in parts) / sum(weight for weight, _ in parts)
    return (round(score, 4), reasons) if score >= 0.40 else None


def with_text_cache(statement):
    return statement.options(undefer(Post.ai_embedding_key), undefer(Post.ai_embedding))


def match_posts(db: Session, runtime: AIRuntime, item_id: UUID) -> MatchesResponse:
    runtime.require_enabled("matching")
    with runtime.inference():
        source = db.scalar(with_text_cache(public_post_query().where(Post.id == item_id)))
        if source is None:
            raise DomainError(404, "POST_NOT_FOUND", "Post not found")
        if not can_accept_claims(source):
            return MatchesResponse(item_id=item_id, matches=[])

        opposite = "FOUND" if source.type == "LOST" else "LOST"
        candidates = list(
            db.scalars(
                with_text_cache(
                    open_posts()
                    .where(Post.type == opposite)
                    .order_by(Post.created_at.desc(), Post.id)
                )
            )
        )
        candidates = [
            candidate
            for candidate in candidates
            if (hours := time_gap_hours(source, candidate)) is None or hours >= 0
        ]
        if not candidates:
            return MatchesResponse(item_id=item_id, matches=[])

        vectors, pending = text_embeddings(db, runtime, [source, *candidates])
        scored = []
        for candidate in candidates:
            text = (
                cosine_similarity(vectors[source.id], vectors[candidate.id])
                if source.id in vectors and candidate.id in vectors
                else None
            )
            result = score_pair(source, candidate, text)
            if result:
                score, reasons = result
                scored.append((score, candidate.id, reasons))
        scored.sort(key=lambda entry: (-entry[0], entry[1]))
        chosen = scored[:5]
        visible = {
            post.id: post
            for post in db.scalars(
                open_posts()
                .where(Post.id.in_([item_id, *(key for _, key, _ in chosen)]))
                .options(selectinload(Post.images))
            )
        }
        matches = [
            MatchCard(
                **ItemCard.from_post(visible[key]).model_dump(),
                matched_item_id=key,
                similarity_score=score,
                matching_reasons=reasons,
            )
            for score, key, reasons in chosen
            if key in visible and item_id in visible
        ]
        return MatchesResponse(item_id=item_id, matches=matches, indexing_pending=pending)
