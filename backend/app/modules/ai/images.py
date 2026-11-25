from io import BytesIO
from uuid import UUID

from fastapi import UploadFile
from PIL import Image
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.modules.ai.image_types import ITEM_TYPES, title_item_type
from app.modules.ai.inference import (
    IMAGE_KEY,
    cosine_similarity,
    embedding_key,
    image_vectors,
    predict_image_type,
)
from app.modules.ai.matching import open_posts
from app.modules.ai.runtime import AIRuntime
from app.modules.ai.schemas import ImageCard, ImageSearchResponse
from app.modules.posts.models.post import Post, PostImage
from app.modules.posts.schemas.post import PostType
from app.modules.posts.services.image_service import MAX_IMAGE_BYTES, clean_image, image_path
from app.shared.errors import DomainError

NEAR_DUPLICATE = 0.92


def upload_bytes(file: UploadFile) -> bytes:
    return clean_image(file.file.read(MAX_IMAGE_BYTES + 1), file.content_type)[0]


def compact_jpeg(data: bytes, edge: int) -> bytes:
    with Image.open(BytesIO(data)) as image:
        pixels = image.convert("RGB")
        pixels.thumbnail((edge, edge))
        output = BytesIO()
        pixels.save(output, format="JPEG", quality=88)
        return output.getvalue()


def image_embeddings(
    db: Session, runtime: AIRuntime, posts_query, query_image: bytes | None = None
):
    rows = db.execute(
        select(
            PostImage,
            PostImage.ai_embedding_key,
            PostImage.ai_embedding,
            PostImage.image_data.is_not(None).label("in_db"),
        )
        .where(PostImage.post_id.in_(posts_query.with_only_columns(Post.id)))
        .order_by(PostImage.created_at.desc(), PostImage.id)
    )
    vectors = []
    missing = []
    for image, old_key, vector, in_db in rows:
        path = None if in_db else image_path(runtime.settings.media_root, image)
        version = f"db:{image.id}"
        if path is not None:
            try:
                stat = path.stat()
            except OSError:
                continue
            version = f"file:{stat.st_size}:{stat.st_mtime_ns}"
        key = embedding_key(IMAGE_KEY, version)
        if old_key == key and vector is not None:
            if vector:
                vectors.append((image, vector))
        else:
            missing.append((image, key, path))

    batch_limit = runtime.settings.ai_image_index_batch
    batch = missing[:batch_limit]
    if batch or (query_image and vectors):
        db.commit()

    inputs = [] if query_image is None else [compact_jpeg(query_image, 1024)]
    valid = []
    invalid = []
    for image, key, path in batch:
        try:
            if path is None:
                data = db.scalar(select(PostImage.image_data).where(PostImage.id == image.id))
            else:
                with path.open("rb") as stream:
                    data = stream.read(MAX_IMAGE_BYTES + 1)
            clean, _ = clean_image(data or b"", image.mime_type)
            inputs.append(compact_jpeg(clean, 1024))
            valid.append((image, key))
        except (OSError, DomainError):
            invalid.append((image, key))
    if batch:
        db.commit()

    query_vector = None
    if valid or (query_image is not None and vectors):
        embeddings = []
        for start in range(0, len(inputs), 8):
            embeddings.extend(image_vectors(runtime, inputs[start : start + 8]))
        if query_image is not None:
            query_vector = embeddings.pop(0)
        vectors.extend(
            (image, vector) for (image, _), vector in zip(valid, embeddings, strict=True)
        )
    else:
        embeddings = []

    values = [(image, key, vector) for (image, key), vector in zip(valid, embeddings, strict=True)]
    values.extend((image, key, []) for image, key in invalid)
    for image, key, vector in values:
        db.execute(
            update(PostImage)
            .where(PostImage.id == image.id)
            .values(ai_embedding_key=key, ai_embedding=vector)
            .execution_options(synchronize_session=False)
        )
    if values:
        db.commit()
    return query_vector, vectors, len(missing) > batch_limit


def search_images(
    db: Session,
    runtime: AIRuntime,
    data: bytes,
    post_type: PostType | None,
    category_id: UUID | None,
    *,
    exclude_id: UUID | None = None,
) -> ImageSearchResponse:
    query = open_posts()
    if post_type is not None:
        query = query.where(Post.type == post_type.value)
    if category_id is not None:
        query = query.where(Post.category_id == category_id)
    if exclude_id is not None:
        query = query.where(Post.id != exclude_id)
    with runtime.inference():
        reference, vectors, pending = image_embeddings(db, runtime, query, data)
        prototypes = runtime.image_prototypes
    kind = predict_image_type(reference, prototypes) if reference else None
    scored = (
        [
            (image, vector, round(cosine_similarity(reference, vector), 4))
            for image, vector in vectors
        ]
        if reference
        else []
    )
    titles = (
        dict(db.execute(query.with_only_columns(Post.id, Post.title)).tuples().all())
        if scored
        else {}
    )
    if kind is None and prototypes:
        near_duplicate_types = {
            label
            for image, _, score in scored
            if score >= NEAR_DUPLICATE and (label := title_item_type(titles.get(image.post_id)))
        }
        if len(near_duplicate_types) == 1:
            kind = next(iter(near_duplicate_types))
    best = {}
    for image, vector, score in scored:
        same_type = False
        if kind in ITEM_TYPES:
            from_title = title_item_type(titles.get(image.post_id))
            from_photo = predict_image_type(vector, prototypes, margin=0.025)
            conflicts = any(label not in (None, kind) for label in (from_title, from_photo))
            same_type = kind in (from_title, from_photo) and not conflicts
            if conflicts and score < NEAR_DUPLICATE:
                continue
        minimum = 0.38 if same_type else 0.70
        if kind == "background":
            minimum = NEAR_DUPLICATE
        if score < minimum:
            continue
        rank = 1 + score if score >= NEAR_DUPLICATE else score + (0.22 if same_type else 0)
        current = best.get(image.post_id)
        if current is None or rank > current[0]:
            best[image.post_id] = (rank, score, same_type, image)
    ranked = sorted(best.values(), key=lambda entry: (-entry[0], entry[3].post_id))[:5]
    visible = {
        post.id: post
        for post in db.scalars(
            query.where(Post.id.in_([image.post_id for _, _, _, image in ranked]))
        )
    }
    results = [
        ImageCard(
            item_id=post.id,
            type=post.type,
            title=post.title,
            location=post.location,
            event_time=post.event_time,
            image_url=image.file_path,
            image_similarity=score,
            same_item_type=same_type,
        )
        for _, score, same_type, image in ranked
        if (post := visible.get(image.post_id)) is not None
    ]
    return ImageSearchResponse(
        results=results,
        indexing_pending=pending,
        detected_item_type=ITEM_TYPES[kind][0] if kind in ITEM_TYPES else None,
    )
