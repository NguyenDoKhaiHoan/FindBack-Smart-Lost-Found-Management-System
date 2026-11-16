from datetime import timedelta
from typing import Annotated
from uuid import UUID, uuid4

import jwt
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.session import get_session, utcnow
from app.modules.identity.models.user import RevokedToken, User
from app.shared.errors import DomainError

bearer = HTTPBearer(auto_error=False, scheme_name="BearerAuth")


def create_access_token(user: User, settings: Settings, *, lifetime=timedelta(hours=1)) -> str:
    """For the Identity adapter and local demo CLI; never a public token-issuing route."""
    now = utcnow()
    return jwt.encode(
        {
            "sub": str(user.id),
            "iat": now,
            "exp": now + lifetime,
            "jti": str(uuid4()),
            "iss": settings.jwt_issuer,
            "aud": settings.jwt_audience,
            "token_version": user.token_version,
        },
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def get_current_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    session: Annotated[Session, Depends(get_session)],
) -> User:
    unauthenticated = DomainError(401, "UNAUTHENTICATED", "A valid access token is required")
    if credentials is None:
        raise unauthenticated
    settings = request.app.state.settings
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
            issuer=settings.jwt_issuer,
            audience=settings.jwt_audience,
            options={"require": ["sub", "exp", "iat", "jti", "token_version"]},
        )
        user_id = UUID(payload["sub"])
        jti = payload["jti"]
        version = payload["token_version"]
        if not isinstance(jti, str) or not 1 <= len(jti) <= 128 or type(version) is not int:
            raise ValueError("Invalid access token")
    except (jwt.InvalidTokenError, ValueError, TypeError, KeyError, AttributeError):
        raise unauthenticated from None
    user = session.get(User, user_id)
    if user is None or user.token_version != version or session.get(RevokedToken, jti):
        raise unauthenticated
    if not user.is_active:
        raise DomainError(403, "ACCOUNT_FORBIDDEN", "This account cannot access claims")
    return user
