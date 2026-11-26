from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from sqlalchemy import select

from app.core.security import CurrentUser, DatabaseSession
from app.modules.ai.chat import chat, chat_image
from app.modules.ai.drafts import generate_draft
from app.modules.ai.images import search_images, upload_bytes
from app.modules.ai.matching import match_posts, open_posts
from app.modules.ai.runtime import AIRuntime
from app.modules.ai.schemas import (
    ChatInput,
    ChatResponse,
    ImageSearchResponse,
    MatchesResponse,
    PostSuggestion,
)
from app.modules.posts.models.post import Post, PostImage
from app.modules.posts.schemas.post import PostType
from app.modules.posts.services.image_service import MAX_IMAGE_BYTES, clean_image, image_path
from app.shared.errors import DomainError

router = APIRouter(prefix="/api/ai", tags=["AI"])


def get_runtime(request: Request) -> AIRuntime:
    return request.app.state.ai


Runtime = Annotated[AIRuntime, Depends(get_runtime)]
FormImage = Annotated[UploadFile, File()]


def client_id(request: Request) -> str:
    return request.client.host if request.client else "local"


@router.get("/matches/{item_id}")
def matches(
    item_id: UUID, db: DatabaseSession, request: Request, runtime: Runtime
) -> MatchesResponse:
    runtime.throttle("matching", client_id(request))
    return match_posts(db, runtime, item_id)


@router.post("/image-search")
def images(
    db: DatabaseSession,
    request: Request,
    runtime: Runtime,
    file: Annotated[UploadFile | None, File()] = None,
    image_id: Annotated[UUID | None, Form()] = None,
    type: Annotated[PostType | None, Form()] = None,
    category_id: Annotated[UUID | None, Form()] = None,
    item_kind: Annotated[str | None, Form(max_length=24)] = None,
) -> ImageSearchResponse:
    runtime.require_enabled("image_search")
    runtime.throttle("image_search", client_id(request))
    if (file is None) == (image_id is None):
        raise DomainError(422, "AI_IMAGE_REQUIRED", "Provide a file or a public post image ID")
    if file is not None:
        return search_images(
            db, runtime, upload_bytes(file), type, category_id, item_kind=item_kind
        )

    image = db.scalar(
        select(PostImage).where(
            PostImage.id == image_id, PostImage.post_id.in_(open_posts().with_only_columns(Post.id))
        )
    )
    if image is None:
        raise DomainError(404, "IMAGE_NOT_FOUND", "Post image not found")
    data = image.image_data
    if data is None:
        try:
            with image_path(runtime.settings.media_root, image).open("rb") as stream:
                data = stream.read(MAX_IMAGE_BYTES + 1)
        except OSError:
            raise DomainError(404, "IMAGE_NOT_FOUND", "Post image not found") from None
    clean, _ = clean_image(data, image.mime_type)
    return search_images(
        db, runtime, clean, type, category_id, exclude_id=image.post_id, item_kind=item_kind
    )


@router.post("/generate-post")
def drafts(
    file: FormImage, db: DatabaseSession, user: CurrentUser, runtime: Runtime
) -> PostSuggestion:
    runtime.require_enabled("auto_post")
    runtime.openai_model("vision")
    runtime.throttle("auto_post", str(user.id))
    return generate_draft(db, runtime, upload_bytes(file))


@router.post("/chat")
def assistant(
    body: ChatInput, db: DatabaseSession, user: CurrentUser, runtime: Runtime
) -> ChatResponse:
    runtime.require_enabled("chatbot")
    runtime.throttle("chatbot", str(user.id))
    return chat(db, runtime, user.id, body)


@router.post("/chat/image-search")
def assistant_image(
    file: FormImage,
    db: DatabaseSession,
    user: CurrentUser,
    runtime: Runtime,
    conversation_id: Annotated[UUID | None, Form()] = None,
) -> ChatResponse:
    runtime.require_enabled("chatbot")
    runtime.require_enabled("image_search")
    runtime.throttle("chatbot", str(user.id))
    return chat_image(db, runtime, user.id, conversation_id, upload_bytes(file))
