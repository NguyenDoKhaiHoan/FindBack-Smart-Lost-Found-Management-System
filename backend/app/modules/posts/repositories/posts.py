from collections.abc import Iterable
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.modules.posts.models.post import Post


def public_post_query():
    return select(Post).where(Post.deleted_at.is_(None), Post.is_hidden.is_(False))


def post_keyword_filters(words: Iterable[str]):
    return (Post.search_text.contains(f" {word} ", autoescape=True) for word in words)


class PostRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_visible(self, post_id: UUID) -> Post | None:
        return self.session.scalar(
            public_post_query().where(Post.id == post_id).options(selectinload(Post.images))
        )

    def get_visible_for_update(self, post_id: UUID) -> Post | None:
        # All future Posts writers must follow the same Post -> Claim lock order.
        return self.session.scalar(
            public_post_query()
            .where(Post.id == post_id)
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
