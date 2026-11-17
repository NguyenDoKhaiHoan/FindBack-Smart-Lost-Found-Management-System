from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.identity.models.user import User
from app.modules.identity.routers.dependencies import get_current_user
from app.modules.identity.schemas import UserRead, UserUpdate
from app.modules.identity.services.user_service import (
    get_user_profile,
    update_user_profile,
)

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserRead, summary="Get the current user")
def read_current_user(
    current_user: User = Depends(get_current_user),
) -> UserRead:
    return get_user_profile(current_user)


@router.patch("/me", response_model=UserRead, summary="Update the current user")
def update_current_user(
    payload: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserRead:
    return update_user_profile(db, current_user, payload)
