from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.posts.models.post import Post


class PostRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_visible_for_update(self, post_id: UUID) -> Post | None:
        # All future Posts writers must follow the same Post -> Claim lock order.
        return self.session.scalar(
            select(Post)
            .where(Post.id == post_id, Post.deleted_at.is_(None), Post.is_hidden.is_(False))
            .with_for_update()
            .execution_options(populate_existing=True)
        )

    def get_for_update(self, post_id: UUID) -> Post | None:
        return self.session.scalar(
            select(Post)
            .where(Post.id == post_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
