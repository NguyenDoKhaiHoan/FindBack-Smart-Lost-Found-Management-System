import os
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import HTTPException, status
from passlib.context import CryptContext
from passlib.exc import InvalidHashError, UnknownHashError

from app.core.config import load_environment

load_environment()

password_context = CryptContext(
    schemes=["bcrypt", "argon2"],
    deprecated=["argon2"],
)

JWT_ALGORITHM = "HS256"
DEFAULT_ACCESS_TOKEN_EXPIRE_MINUTES = 30


def hash_password(password: str) -> str:
    return password_context.hash(password)


def verify_password_and_update(
    password: str, hashed_password: str
) -> tuple[bool, str | None]:
    try:
        return password_context.verify_and_update(password, hashed_password)
    except (InvalidHashError, UnknownHashError):
        return False, None


def _jwt_settings() -> tuple[str, str, int]:
    secret = os.getenv("JWT_SECRET_KEY")
    if (
        not secret
        or len(secret) < 32
        or secret.startswith(("REPLACE_WITH_", "CHANGE_ME"))
    ):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="JWT_SECRET_KEY must be configured with at least 32 characters",
        )

    algorithm = os.getenv("JWT_ALGORITHM", JWT_ALGORITHM)
    if algorithm != JWT_ALGORITHM:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"JWT_ALGORITHM must be {JWT_ALGORITHM}",
        )

    try:
        expires_minutes = int(
            os.getenv(
                "JWT_ACCESS_TOKEN_EXPIRE_MINUTES",
                str(DEFAULT_ACCESS_TOKEN_EXPIRE_MINUTES),
            )
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="JWT_ACCESS_TOKEN_EXPIRE_MINUTES must be a positive integer",
        ) from exc

    if expires_minutes <= 0:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="JWT_ACCESS_TOKEN_EXPIRE_MINUTES must be a positive integer",
        )

    return secret, algorithm, expires_minutes


def create_access_token(user_id: int) -> str:
    secret, algorithm, expires_minutes = _jwt_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(minutes=expires_minutes),
    }
    return jwt.encode(payload, secret, algorithm=algorithm)


def get_user_id_from_token(token: str) -> int:
    secret, algorithm, _ = _jwt_settings()
    try:
        payload = jwt.decode(token, secret, algorithms=[algorithm])
        subject = payload["sub"]
        if not isinstance(subject, str) or not subject.isdigit():
            raise ValueError("Invalid user ID")
        user_id = int(subject)
        if user_id < 1:
            raise ValueError("Invalid user ID")
        return user_id
    except (jwt.InvalidTokenError, KeyError, TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
