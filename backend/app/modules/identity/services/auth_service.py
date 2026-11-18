from datetime import timedelta
from hashlib import sha256
from secrets import token_urlsafe

from pwdlib import PasswordHash
from pwdlib.exceptions import UnknownHashError
from pwdlib.hashers.argon2 import Argon2Hasher
from pwdlib.hashers.bcrypt import BcryptHasher
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.security import create_access_token
from app.db.session import utcnow
from app.modules.identity.models.user import RefreshToken, User
from app.modules.identity.repositories import user_repository
from app.modules.identity.schemas import LoginRequest, RegisterRequest, TokenResponse, UserRead
from app.shared.errors import DomainError

passwords = PasswordHash((Argon2Hasher(), BcryptHasher()))
dummy_hash = passwords.hash(token_urlsafe(32))


def register_user(db: Session, payload: RegisterRequest) -> UserRead:
    email = str(payload.email).casefold()
    conflict = DomainError(409, "EMAIL_ALREADY_REGISTERED", "Email is already registered")
    if user_repository.get_by_email(db, email) is not None:
        raise conflict
    user = User(
        email=email, full_name=payload.full_name, password_hash=passwords.hash(payload.password)
    )
    try:
        return UserRead.model_validate(user_repository.create(db, user))
    except IntegrityError as exc:
        db.rollback()
        raise conflict from exc


def issue_tokens(db: Session, user: User, settings: Settings) -> TokenResponse:
    secret = token_urlsafe(48)
    db.add(
        RefreshToken(
            digest=sha256(secret.encode()).hexdigest(),
            user_id=user.id,
            token_version=user.token_version,
            expires_at=utcnow() + timedelta(days=30),
        )
    )
    response = TokenResponse(access_token=create_access_token(user, settings), refresh_token=secret)
    db.commit()
    return response


def authenticate_user(db: Session, payload: LoginRequest, settings: Settings) -> TokenResponse:
    user = user_repository.get_by_email(db, str(payload.email).casefold())
    stored = user.password_hash if user else None
    try:
        valid, upgraded = passwords.verify_and_update(payload.password, stored or dummy_hash)
    except (UnknownHashError, ValueError):
        valid, upgraded = False, None
    if not valid or not stored or not user or not user.is_active:
        raise DomainError(401, "INVALID_CREDENTIALS", "Invalid email or password")
    if upgraded is not None:
        user.password_hash = upgraded
    return issue_tokens(db, user, settings)


def rotate_refresh_token(db: Session, secret: str, settings: Settings) -> TokenResponse:
    now = utcnow()
    digest = sha256(secret.encode()).hexdigest()
    invalid = DomainError(401, "INVALID_REFRESH_TOKEN", "Refresh token is invalid or expired")
    token = db.get(RefreshToken, digest)
    user = db.get(User, token.user_id) if token else None
    if (
        token is None
        or user is None
        or not user.is_active
        or user.token_version != token.token_version
    ):
        raise invalid
    consumed = db.execute(
        update(RefreshToken)
        .where(
            RefreshToken.digest == digest,
            RefreshToken.used_at.is_(None),
            RefreshToken.expires_at > now,
        )
        .values(used_at=now)
    )
    if consumed.rowcount != 1:
        raise invalid
    return issue_tokens(db, user, settings)
