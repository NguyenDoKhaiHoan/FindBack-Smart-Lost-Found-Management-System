from typing import Sequence
import uuid
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.posts.models.post import Post


class PostRepository:
    """Async repository for Post persistence and query operations."""

    async def get_by_id(
        self,
        session: AsyncSession,
        post_id: uuid.UUID,
        for_update: bool = False,
    ) -> Post | None:
        """Retrieves a single post by its UUID with optional row-level lock."""
        stmt = select(Post).where(Post.id == post_id)
        if for_update:
            stmt = stmt.with_for_update()
        result = await session.execute(stmt)
        return result.scalars().first()

    async def create(self, session: AsyncSession, post: Post) -> Post:
        """Persists a new post."""
        session.add(post)
        await session.flush()
        await session.refresh(post)
        return post

    async def list_admin_posts(
        self,
        session: AsyncSession,
        page: int = 1,
        limit: int = 20,
        status: str | None = None,
        type_: str | None = None,
        q: str | None = None,
    ) -> tuple[Sequence[Post], int]:
        """
        Fetches paginated posts for Admin listing with optional filtering and search.
        Order: created_at DESC, id DESC.
        """
        base_query = select(Post)

        if status:
            base_query = base_query.where(Post.status == status)

        if type_:
            base_query = base_query.where(Post.type == type_)

        if q and q.strip():
            search_term = f"%{q.strip()}%"
            base_query = base_query.where(
                or_(
                    Post.title.ilike(search_term),
                    Post.description.ilike(search_term),
                    Post.location.ilike(search_term),
                )
            )

        # Count total
        count_query = select(func.count()).select_from(base_query.subquery())
        total_result = await session.execute(count_query)
        total = total_result.scalar_one()

        # Page query
        offset = (page - 1) * limit
        items_query = (
            base_query.order_by(Post.created_at.desc(), Post.id.desc())
            .offset(offset)
            .limit(limit)
        )
        items_result = await session.execute(items_query)
        items = items_result.scalars().all()

        return items, total
