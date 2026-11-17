from datetime import datetime
from typing import Any, Sequence
import uuid
from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.notifications_admin.models.notification import Notification


class NotificationRepository:
    """Async repository for Notification persistence operations."""

    async def create_idempotent(
        self,
        session: AsyncSession,
        notification_values: dict[str, Any],
    ) -> Notification:
        """
        Persists a notification with PostgreSQL ON CONFLICT (event_id) DO NOTHING
        when event_id is specified.

        Guarantees that concurrent attempts to insert the same event_id:
        1. Do not raise IntegrityError or abort the caller transaction.
        2. Do not create duplicate records.
        3. Returns the existing notification if a conflict occurs.
        """
        event_id = notification_values.get("event_id")

        if event_id is not None:
            bind = session.get_bind()
            dialect_name = getattr(bind.dialect, "name", "")

            if dialect_name == "postgresql":
                stmt = (
                    pg_insert(Notification)
                    .values(notification_values)
                    .on_conflict_do_nothing(
                        index_elements=["event_id"],
                        index_where=text("event_id IS NOT NULL"),
                    )
                    .returning(Notification)
                )
                result = await session.execute(stmt)
                created = result.scalars().first()
                if created:
                    return created

                existing = await self.get_by_event_id(session, event_id)
                if existing:
                    return existing

            # Generic fallback with savepoint for other dialects / engines
            try:
                async with session.begin_nested():
                    notification = Notification(**notification_values)
                    session.add(notification)
                    await session.flush()
                    await session.refresh(notification)
                    return notification
            except IntegrityError:
                existing = await self.get_by_event_id(session, event_id)
                if existing:
                    return existing
                raise

        notification = Notification(**notification_values)
        session.add(notification)
        await session.flush()
        await session.refresh(notification)
        return notification

    async def create(self, session: AsyncSession, notification: Notification) -> Notification:
        """Persists a new notification entity."""
        session.add(notification)
        await session.flush()
        await session.refresh(notification)
        return notification

    async def get_by_id_and_recipient(
        self,
        session: AsyncSession,
        notification_id: uuid.UUID,
        recipient_id: uuid.UUID,
    ) -> Notification | None:
        """
        Retrieves a notification strictly bounded by its recipient.
        Guarantees users cannot query notifications of other users.
        """
        stmt = select(Notification).where(
            Notification.id == notification_id,
            Notification.recipient_id == recipient_id,
        )
        result = await session.execute(stmt)
        return result.scalars().first()

    async def get_by_event_id(
        self,
        session: AsyncSession,
        event_id: uuid.UUID,
    ) -> Notification | None:
        """Finds an existing notification by event_id for idempotency/deduplication."""
        stmt = select(Notification).where(Notification.event_id == event_id)
        result = await session.execute(stmt)
        return result.scalars().first()

    async def list_by_recipient(
        self,
        session: AsyncSession,
        recipient_id: uuid.UUID,
        page: int,
        limit: int,
        is_read: bool | None = None,
    ) -> tuple[Sequence[Notification], int]:
        """
        Fetches paginated notifications for the given recipient.
        Order: newest first (created_at DESC, id DESC for stable ordering).
        """
        base_query = select(Notification).where(Notification.recipient_id == recipient_id)
        if is_read is not None:
            base_query = base_query.where(Notification.is_read == is_read)

        # Count total items
        count_query = select(func.count()).select_from(base_query.subquery())
        total_result = await session.execute(count_query)
        total = total_result.scalar_one()

        # Fetch page items
        offset = (page - 1) * limit
        items_query = (
            base_query.order_by(Notification.created_at.desc(), Notification.id.desc())
            .offset(offset)
            .limit(limit)
        )
        items_result = await session.execute(items_query)
        items = items_result.scalars().all()

        return items, total

    async def mark_as_read(
        self,
        session: AsyncSession,
        notification: Notification,
        read_at: datetime,
    ) -> Notification:
        """Updates the read status and read timestamp of a notification."""
        notification.is_read = True
        notification.read_at = read_at
        await session.flush()
        await session.refresh(notification)
        return notification
