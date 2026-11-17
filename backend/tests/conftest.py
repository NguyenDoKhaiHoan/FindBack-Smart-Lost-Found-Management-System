from datetime import datetime, timedelta, timezone
from typing import AsyncGenerator
import uuid
from httpx import ASGITransport, AsyncClient
import jwt
import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.modules.identity.models.user import User

# TEST-01: Explicit database safety verification
test_db_url = settings.async_test_database_url
test_engine = create_async_engine(
    test_db_url,
    echo=False,
    poolclass=NullPool,
)

# Safety guard: Prevent accidental execution against production / dev database
db_name = test_engine.url.database
if not db_name or "test" not in db_name.lower() or db_name.lower() == "findback":
    raise RuntimeError(
        f"CRITICAL TEST CONFIG ERROR: Expected dedicated test database containing 'test', got '{db_name}'. "
        "Refusing to execute tests against development database!"
    )

TestingSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


def create_test_jwt(
    user_id: uuid.UUID,
    role: str = "USER",
    expires_delta: timedelta | None = None,
    secret_key: str = settings.JWT_SECRET_KEY,
    algorithm: str = settings.JWT_ALGORITHM,
) -> str:
    """Helper to generate cryptographically signed JWT tokens for testing."""
    now = datetime.now(timezone.utc)
    expire = now + (expires_delta if expires_delta is not None else timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    payload = {
        "sub": str(user_id),
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    return jwt.encode(payload, secret_key, algorithm=algorithm)


@pytest_asyncio.fixture(autouse=True)
async def prepare_and_clean_database():
    """
    Ensures tables exist on test database before test,
    and cleanly truncates all rows after test so data never accumulates (TEST-01).
    """
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    # Cleanup after each test: Truncate test tables
    async with test_engine.begin() as conn:
        await conn.execute(text("TRUNCATE TABLE notifications CASCADE;"))
        await conn.execute(text("TRUNCATE TABLE users CASCADE;"))


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provides an isolated test database session per test."""
    async with TestingSessionLocal() as session:
        yield session


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """TestClient wired with isolated test database session."""
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def test_user_a(db_session: AsyncSession) -> User:
    """Creates a standard active user A in test DB."""
    user = User(
        id=uuid.uuid4(),
        email=f"user_a_{uuid.uuid4().hex[:8]}@example.com",
        password_hash="hashed_secret_a",
        role="USER",
        status="ACTIVE",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def test_user_b(db_session: AsyncSession) -> User:
    """Creates a standard active user B in test DB."""
    user = User(
        id=uuid.uuid4(),
        email=f"user_b_{uuid.uuid4().hex[:8]}@example.com",
        password_hash="hashed_secret_b",
        role="USER",
        status="ACTIVE",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def test_inactive_user(db_session: AsyncSession) -> User:
    """Creates a suspended user in test DB."""
    user = User(
        id=uuid.uuid4(),
        email=f"inactive_{uuid.uuid4().hex[:8]}@example.com",
        password_hash="hashed_secret_inactive",
        role="USER",
        status="SUSPENDED",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def test_disabled_user(db_session: AsyncSession) -> User:
    """Creates a disabled user in test DB."""
    user = User(
        id=uuid.uuid4(),
        email=f"disabled_{uuid.uuid4().hex[:8]}@example.com",
        password_hash="hashed_secret_disabled",
        role="USER",
        status="DISABLED",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def test_admin_user(db_session: AsyncSession) -> User:
    """Creates an active admin user in test DB."""
    user = User(
        id=uuid.uuid4(),
        email=f"admin_{uuid.uuid4().hex[:8]}@example.com",
        password_hash="hashed_secret_admin",
        role="ADMIN",
        status="ACTIVE",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
def auth_headers_user_a(test_user_a: User) -> dict[str, str]:
    """Generates valid JWT Authorization headers for user A."""
    token = create_test_jwt(test_user_a.id, role=test_user_a.role)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def auth_headers_user_b(test_user_b: User) -> dict[str, str]:
    """Generates valid JWT Authorization headers for user B."""
    token = create_test_jwt(test_user_b.id, role=test_user_b.role)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def auth_headers_admin(test_admin_user: User) -> dict[str, str]:
    """Generates valid JWT Authorization headers for admin."""
    token = create_test_jwt(test_admin_user.id, role=test_admin_user.role)
    return {"Authorization": f"Bearer {token}"}
