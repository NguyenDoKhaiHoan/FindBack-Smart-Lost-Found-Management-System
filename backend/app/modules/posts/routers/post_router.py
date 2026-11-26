from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, File, Query, Request, Response, UploadFile
from fastapi.responses import FileResponse

from app.core.security import CurrentUser, DatabaseSession
from app.modules.posts.models.post import Post, PostImage
from app.modules.posts.repositories.posts import PostRepository
from app.modules.posts.schemas.post import (
    PostCreate,
    PostHotspotLocation,
    PostListQuery,
    PostListResponse,
    PostResponse,
    PostUpdate,
)
from app.modules.posts.schemas.post_image import PostImageUploadResponse
from app.modules.posts.services import listings
from app.modules.posts.services.image_service import image_path, upload_image
from app.shared.errors import DomainError

router = APIRouter(prefix="/api/v1", tags=["Posts"])


@router.post("/posts", status_code=201)
def create_post(payload: PostCreate, db: DatabaseSession, user: CurrentUser) -> PostResponse:
    return listings.create_post(db, payload, user.id)


@router.get("/posts")
def public_posts(query: Annotated[PostListQuery, Query()], db: DatabaseSession) -> PostListResponse:
    return listings.list_posts(db, query)


@router.get("/users/me/posts")
def my_posts(
    query: Annotated[PostListQuery, Query()], db: DatabaseSession, user: CurrentUser
) -> PostListResponse:
    return listings.list_posts(db, query, owner_id=user.id)


@router.get("/posts/{id}")
def post_detail(id: UUID, db: DatabaseSession) -> PostResponse:
    post = PostRepository(db).get_visible(id)
    if post is None:
        raise DomainError(404, "POST_NOT_FOUND", "Post not found")
    return PostResponse.model_validate(post)


@router.patch("/posts/{id}")
def patch_post(
    id: UUID, payload: PostUpdate, db: DatabaseSession, user: CurrentUser
) -> PostResponse:
    return listings.edit_post(db, id, user.id, payload)


@router.get("/posts/{id}/hotspot-location")
def post_hotspot_location(
    id: UUID, db: DatabaseSession, user: CurrentUser
) -> PostHotspotLocation | None:
    post = db.get(Post, id)
    if post is None or post.deleted_at is not None or post.owner_id != user.id:
        raise DomainError(404, "POST_NOT_FOUND", "Post not found")
    if post.hotspot_zone is None or post.latitude is None or post.longitude is None:
        return None
    return PostHotspotLocation(
        hotspot_zone=post.hotspot_zone,
        latitude=float(post.latitude),
        longitude=float(post.longitude),
    )


@router.delete("/posts/{id}", status_code=204)
def delete_post(id: UUID, db: DatabaseSession, user: CurrentUser) -> Response:
    listings.delete_post(db, id, user.id)
    return Response(status_code=204)


@router.post("/posts/{id}/images", status_code=201)
def upload_post_image(
    id: UUID,
    request: Request,
    db: DatabaseSession,
    user: CurrentUser,
    file: Annotated[UploadFile, File()],
    restore_image_id: Annotated[
        UUID | None, Query(description="Restore an unavailable image at its existing URL")
    ] = None,
) -> PostImageUploadResponse:
    return upload_image(
        db, id, file, user.id, request.app.state.settings.media_root, restore_image_id
    )


@router.get("/posts/{id}/images/{image_id}", response_class=FileResponse)
def download_post_image(
    id: UUID, image_id: UUID, request: Request, db: DatabaseSession
) -> Response:
    post = PostRepository(db).get_visible(id)
    image = db.get(PostImage, image_id) if post is not None else None
    if image is None or image.post_id != id:
        raise DomainError(404, "IMAGE_NOT_FOUND", "Post image not found")
    headers = {"X-Content-Type-Options": "nosniff"}
    data = image.image_data
    if data is not None:
        return Response(data, media_type=image.mime_type, headers=headers)
    path = image_path(request.app.state.settings.media_root, image)
    if not path.is_file():
        raise DomainError(404, "IMAGE_NOT_FOUND", "Post image not found")
    return FileResponse(path, media_type=image.mime_type, headers=headers)
