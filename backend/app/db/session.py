from collections.abc import Iterator
from datetime import datetime, timezone

from fastapi import Request
from sqlalchemy import DateTime, MetaData, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.types import TypeDecorator

from app.core.config import Settings


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class UTCDateTime(TypeDecorator):
    impl = DateTime(timezone=True)
    cache_ok = True

    def process_result_value(self, value, dialect):
        if value is not None and value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value


class Base(DeclarativeBase):
    metadata = MetaData(schema="findback_api")


def make_engine(settings: Settings):
    is_sqlite = settings.database_url.startswith("sqlite")
    engine = create_engine(
        settings.database_url,
        echo=False,
        hide_parameters=True,
        pool_pre_ping=True,
        connect_args={"check_same_thread": False, "timeout": 30} if is_sqlite else {},
        execution_options={
            "schema_translate_map": {
                "findback_api": None if is_sqlite else settings.database_schema
            }
        },
    )
    if is_sqlite:

        @event.listens_for(engine, "connect")
        def sqlite_foreign_keys(connection, _):
            connection.execute("PRAGMA foreign_keys=ON")

    return engine


def make_session_factory(engine):
    return sessionmaker(engine, expire_on_commit=False)


def get_session(request: Request) -> Iterator[Session]:
    with request.app.state.session_factory() as session:
        yield session
