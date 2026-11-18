from datetime import datetime
from uuid import UUID

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.modules.posts.models.post import Post
from app.shared.errors import DomainError


class PostService:
    def __init__(self, session: Session):
        self.session = session

    def close_for_completed_claim(self, post: Post, claim_id: UUID, occurred_at: datetime):
        """Caller owns the Post lock and transaction; this service never commits."""
        conflict = DomainError(409, "POST_STATE_CONFLICT", "Post cannot be completed consistently")
        if post.type != "FOUND" or post.is_hidden or post.deleted_at is not None:
            raise conflict
        if post.status == "CLOSED":
            if post.completed_claim_id == claim_id and post.completed_at is not None:
                return
            raise conflict
        result = self.session.execute(
            update(Post)
            .where(
                Post.id == post.id,
                Post.status == "OPEN",
                Post.completed_claim_id.is_(None),
                Post.deleted_at.is_(None),
                Post.is_hidden.is_(False),
                Post.type == "FOUND",
            )
            .values(
                status="CLOSED",
                completed_claim_id=claim_id,
                completed_at=occurred_at,
                updated_at=occurred_at,
            )
            .execution_options(synchronize_session=False)
        )
        if result.rowcount != 1:
            raise conflict
