from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.matching.schemas.contracts import Color
from app.modules.posts.models.post import Post
from app.modules.posts.schemas.post import PostType


class AIInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ItemCard(BaseModel):
    item_id: UUID
    type: PostType
    title: str | None
    location: str | None
    event_time: datetime | None
    image_url: str | None

    @classmethod
    def from_post(cls, post: Post):
        return cls(
            item_id=post.id,
            type=post.type,
            title=post.title,
            location=post.location,
            event_time=post.event_time,
            image_url=post.images[0].file_path if post.images else None,
        )


class MatchCard(ItemCard):
    matched_item_id: UUID
    similarity_score: float
    matching_reasons: list[str]


class MatchesResponse(BaseModel):
    item_id: UUID
    matches: list[MatchCard]
    indexing_pending: bool = False
    matching_mode: Literal["semantic", "details"] = "semantic"


class ImageCard(ItemCard):
    image_similarity: float
    same_item_type: bool = False


class ImageSearchResponse(BaseModel):
    results: list[ImageCard]
    indexing_pending: bool = False
    detected_item_type: str | None = None


class PostDraft(AIInput):
    title: str = Field(min_length=1, max_length=255)
    category: str | None = Field(max_length=100)
    color: Color | None
    description: str = Field(min_length=1, max_length=1200)


class PostSuggestion(PostDraft):
    category_id: UUID | None
    confidence_note: str


class ChatReview(AIInput):
    topic: Literal["why", "location", "time", "description"]
    number: int | None = Field(ge=1, le=20)


class ChatCompare(AIInput):
    first: int = Field(ge=1, le=20)
    second: int = Field(ge=1, le=20)


class ChatInput(AIInput):
    message: str = Field(min_length=1, max_length=500)
    conversation_id: UUID | None = None
    selected_item_id: UUID | None = None
    review: ChatReview | None = None
    compare: ChatCompare | None = None

    @model_validator(mode="after")
    def allow_one_quick_action(self):
        if (
            sum(action is not None for action in (self.review, self.compare, self.selected_item_id))
            > 1
        ):
            raise ValueError("Choose one chat action")
        return self


class ChatItem(ItemCard):
    reasons: list[str] = Field(default_factory=list)
    result_number: int | None = None


class ChatMap(BaseModel):
    destination: str
    origin: str | None = None


class ChatResult(BaseModel):
    reply: str
    related_items: list[ChatItem] = Field(default_factory=list)
    action: Literal["create_lost", "create_found", "explore", "guide"] | None = None
    can_select_item: bool = False
    can_review_items: bool = False
    map_place: ChatMap | None = None


class ChatResponse(ChatResult):
    conversation_id: UUID
