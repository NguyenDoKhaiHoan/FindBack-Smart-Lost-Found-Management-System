import io
from pathlib import Path
from uuid import UUID

from fastapi import UploadFile
from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.posts.models.post import PostImage
from app.modules.posts.schemas.post_image import PostImageUploadResponse
from app.modules.posts.services.listings import lock_editable_post
from app.shared.errors import DomainError

MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_IMAGES = 5
FORMATS = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}


def image_path(root: Path, image: PostImage) -> Path:
    return root / "posts" / str(image.post_id) / str(image.id)


def clean_image(data: bytes, content_type: str | None) -> tuple[bytes, str]:
    if not data:
        raise DomainError(422, "EMPTY_IMAGE", "Image is empty")
    if len(data) > MAX_IMAGE_BYTES:
        raise DomainError(413, "IMAGE_TOO_LARGE", "Image exceeds 5 MiB")
    try:
        with Image.open(io.BytesIO(data)) as image:
            image_format = image.format
            mime = FORMATS.get(image_format)
            if mime is None or content_type != mime or image.width * image.height > 16_000_000:
                raise ValueError("Unsupported image")
            # Re-encode pixels to discard EXIF/GPS and reject corrupt data.
            pixels = ImageOps.exif_transpose(image).convert(
                "RGB" if image_format == "JPEG" else "RGBA"
            )
            pixels.info.clear()
            output = io.BytesIO()
            pixels.save(output, format=image_format)
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as exc:
        raise DomainError(415, "INVALID_IMAGE", "Upload a valid JPEG, PNG or WebP image") from exc
    if output.tell() > MAX_IMAGE_BYTES:
        raise DomainError(413, "IMAGE_TOO_LARGE", "Image exceeds 5 MiB after processing")
    return output.getvalue(), mime


def upload_image(
    db: Session, post_id: UUID, file: UploadFile, owner_id: UUID, media_root: Path
) -> PostImageUploadResponse:
    lock_editable_post(db, post_id, owner_id, check_claims=False)
    count = db.scalar(select(func.count()).where(PostImage.post_id == post_id))
    if count >= MAX_IMAGES:
        raise DomainError(409, "IMAGE_LIMIT", "A post can have at most 5 images")
    data, mime = clean_image(file.file.read(MAX_IMAGE_BYTES + 1), file.content_type)
    name = Path((file.filename or "image").replace(chr(92), "/")).name[:255] or "image"
    record = PostImage(
        post_id=post_id,
        original_name=name,
        mime_type=mime,
        size_bytes=len(data),
        sort_order=count,
    )
    db.add(record)
    db.flush()
    response = PostImageUploadResponse(image=record)
    path = image_path(media_root, record)
    created = False
    try:
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
    return response
