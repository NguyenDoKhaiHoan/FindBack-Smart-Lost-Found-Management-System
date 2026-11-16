import os
from dataclasses import dataclass
from datetime import timedelta
from uuid import UUID, uuid4

import pytest
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import text

from alembic import command
from app.core.config import BACKEND_DIR, Settings
from app.core.security import create_access_token
from app.db.session import make_engine, make_session_factory, utcnow
from app.main import create_app
from app.modules.claims_returns.models.claim import Claim
from app.modules.identity.models.user import User
from app.modules.posts.models.post import Post


def migrate(engine, *, schema=None, revision="head"):
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.attributes["schema"] = schema
    with engine.connect() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, revision)


@dataclass
class World:
    settings: Settings
    engine: object
    factory: object
    ids: dict[str, UUID]
    tokens: dict[str, str]
    client: TestClient | None = None

    def auth(self, name="claimant"):
        return {"Authorization": f"Bearer {self.tokens[name]}"}

    def body(self, post="found", **overrides):
        return {
            "found_post_id": str(self.ids[post]),
            "evidence_description": "  Fictional secret marking DEMO-123  ",
            **overrides,
        }

    def add_claim(self, *, claimant="claimant", post="found", status="PENDING", at=None):
        now = at or utcnow()
        claim_id = uuid4()
        with self.factory() as session:
            session.add(
                Claim(
                    id=claim_id,
                    found_post_id=self.ids[post],
                    claimant_id=self.ids[claimant],
                    status=status,
                    version=1,
                    created_at=now,
                    updated_at=now,
                    decided_by=self.ids["owner"] if status != "PENDING" else None,
                    decided_at=now if status != "PENDING" else None,
                    rejection_reason="Fictional reason" if status == "REJECTED" else None,
                    returned_by=self.ids[claimant] if status == "RETURNED" else None,
                    returned_at=now if status == "RETURNED" else None,
                )
            )
            session.commit()
        return claim_id


def populate(settings, engine):
    factory = make_session_factory(engine)
    ids = {
        name: uuid4()
        for name in (
            "owner",
            "claimant",
            "other",
            "admin",
            "locked",
            "found",
            "second",
            "own",
            "closed",
            "hidden",
            "deleted",
            "lost",
            "unrelated",
        )
    }
    tokens = {}
    with factory() as session:
        for name in ("owner", "claimant", "other", "admin", "locked"):
            user = User(
                id=ids[name],
                role="ADMIN" if name == "admin" else "USER",
                is_active=name != "locked",
                token_version=1,
            )
            session.add(user)
            session.flush()
            tokens[name] = create_access_token(user, settings)
        for name in ("found", "second", "own", "closed", "hidden", "deleted", "lost", "unrelated"):
            owner = "claimant" if name == "own" else "other" if name == "unrelated" else "owner"
            session.add(
                Post(
                    id=ids[name],
                    owner_id=ids[owner],
                    type="LOST" if name == "lost" else "FOUND",
                    status="CLOSED" if name == "closed" else "OPEN",
                    is_hidden=name == "hidden",
                    deleted_at=utcnow() if name == "deleted" else None,
                )
            )
        session.commit()
    return World(settings, engine, factory, ids, tokens)


def pytest_addoption(parser):
    parser.addoption("--postgres", action="store_true", help="Run against TEST_DATABASE_URL")


@pytest.fixture
def world(tmp_path, request):
    use_postgres = request.config.getoption("--postgres")
    test_url = os.environ.get("TEST_DATABASE_URL")
    if use_postgres and not test_url:
        pytest.fail(
            "--postgres requires TEST_DATABASE_URL; normal application DB is never implicit"
        )
    schema = f"claims_test_{uuid4().hex}" if use_postgres else None
    settings = Settings(
        _env_file=None,
        database_url=test_url if use_postgres else f"sqlite:///{tmp_path / 'claims.db'}",
        database_schema=schema or "findback_api",
        jwt_secret_key="test-only-" + "x" * 48,
    )
    engine = make_engine(settings)
    migrate(engine, schema=schema)
    world = populate(settings, engine)
    with TestClient(create_app(settings, engine=engine)) as client:
        world.client = client
        yield world
    if schema:
        assert schema.startswith("claims_test_") and len(schema) == 44
        with engine.begin() as connection:
            quoted = connection.dialect.identifier_preparer.quote(schema)
            connection.execute(text(f"DROP SCHEMA {quoted} CASCADE"))
    engine.dispose()


@pytest.fixture
def expired_token(world):
    with world.factory() as session:
        user = session.get(User, world.ids["claimant"])
        return create_access_token(user, world.settings, lifetime=-timedelta(seconds=1))
