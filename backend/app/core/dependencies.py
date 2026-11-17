import uuid
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import jwt
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_db
from app.modules.identity.models.user import User

# Bearer scheme (auto_error=False to provide custom 401 details matching error contract)
security_bearer = HTTPBearer(auto_error=False)


async def get_current_active_user(
    auth: HTTPAuthorizationCredentials | None = Depends(security_bearer),
    session: AsyncSession = Depends(get_db),
) -> User:
    """
    JWT Authentication & Active Status Authorization Dependency.

    Security Controls (SEC-01 & SEC-02):
    - Enforces cryptographic signature verification with fixed server algorithm.
    - Strictly rejects alg=none, raw UUID strings, and missing/expired tokens.
    - Requires 'sub' (subject) to be a valid UUID representing the user ID.
    - Queries database to verify the user exists and is ACTIVE.
    - Completely eliminates X-User-Id header bypass.
    """
    if not auth or not auth.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Chưa xác thực hoặc thiếu token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = auth.credentials.strip()

    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
            options={
                "require": ["exp", "sub"],
                "verify_exp": True,
                "verify_signature": True,
            },
        )
    except ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token đã hết hạn",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Chưa xác thực hoặc token không hợp lệ",
            headers={"WWW-Authenticate": "Bearer"},
        )

    sub = payload.get("sub")
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token không chứa subject (sub)",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        user_uuid = uuid.UUID(str(sub))
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Subject trong token không phải UUID hợp lệ",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Verify user in database
    stmt = select(User).where(User.id == user_uuid)
    result = await session.execute(stmt)
    user = result.scalars().first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Người dùng không tồn tại hoặc phiên đăng nhập đã hết hạn",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check active status
    if user.status != "ACTIVE":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Tài khoản không ở trạng thái hoạt động: {user.status}",
        )

    return user


async def get_current_admin_user(
    current_user: User = Depends(get_current_active_user),
) -> User:
    """Ensures the authenticated user possesses the ADMIN role."""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Chức năng chỉ dành cho quản trị viên (Admin)",
        )
    return current_user
