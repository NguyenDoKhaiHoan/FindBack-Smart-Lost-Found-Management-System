from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.identity.models.user import User
from app.modules.identity.repositories import user_repository
from app.modules.identity.schemas import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserRead,
)
from app.modules.identity.security import (
    create_access_token,
    hash_password,
    verify_password_and_update,
)


def register_user(db: Session, payload: RegisterRequest) -> UserRead:
    email = str(payload.email)
    if user_repository.get_by_email(db, email) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        )

    user = User(
        email=email,
        full_name=payload.full_name,
        password_hash=hash_password(payload.password),
    )
    try:
        created_user = user_repository.create(db, user)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        ) from exc

    return UserRead.model_validate(created_user)


def authenticate_user(db: Session, payload: LoginRequest) -> TokenResponse:
    user = user_repository.get_by_email(db, str(payload.email))
    if user is None:
        raise _invalid_credentials()

    password_is_valid, replacement_hash = verify_password_and_update(
        payload.password,
        user.password_hash,
    )
    if not password_is_valid:
        raise _invalid_credentials()

    if replacement_hash is not None:
        user.password_hash = replacement_hash
        user_repository.save(db, user)

    return TokenResponse(access_token=create_access_token(user.id))


def _invalid_credentials() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid email or password",
        headers={"WWW-Authenticate": "Bearer"},
    )
