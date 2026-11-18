from sqlalchemy.orm import Session

from app.modules.identity.models.user import User
from app.modules.identity.repositories import user_repository
from app.modules.identity.schemas import UserRead, UserUpdate


def get_user_profile(user: User) -> UserRead:
    return UserRead.model_validate(user)


def update_user_profile(
    db: Session,
    user: User,
    payload: UserUpdate,
) -> UserRead:
    changes = payload.model_dump(exclude_unset=True)
    if changes.get("avatar_url") is not None:
        changes["avatar_url"] = str(changes["avatar_url"])

    updated_user = user_repository.update_profile(db, user, changes)
    return UserRead.model_validate(updated_user)
