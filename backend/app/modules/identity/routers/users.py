from uuid import UUID

from fastapi import APIRouter

from app.core.security import CurrentUser, DatabaseSession
from app.modules.identity.models.user import User
from app.modules.identity.schemas import UserRead, UserUpdate
from app.modules.identity.schemas.user import PublicUser
from app.modules.identity.services.user_service import get_user_profile, update_user_profile
from app.shared.errors import DomainError

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me")
def read_me(user: CurrentUser) -> UserRead:
    return get_user_profile(user)


@router.patch("/me")
def update_me(payload: UserUpdate, db: DatabaseSession, user: CurrentUser) -> UserRead:
    return update_user_profile(db, user, payload)


@router.get("/{id}")
def public_profile(id: UUID, db: DatabaseSession) -> PublicUser:
    user = db.get(User, id)
    if user is None or not user.is_active or user.full_name is None:
        raise DomainError(404, "USER_NOT_FOUND", "Public profile not found")
    return PublicUser.model_validate(user)
