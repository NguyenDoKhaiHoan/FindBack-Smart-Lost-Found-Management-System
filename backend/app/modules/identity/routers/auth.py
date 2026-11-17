from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.identity.schemas import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserRead,
)
from app.modules.identity.services.auth_service import (
    authenticate_user,
    register_user,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    summary="Register a user",
)
def register(
    payload: RegisterRequest,
    db: Session = Depends(get_db),
) -> UserRead:
    return register_user(db, payload)


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Authenticate and receive a bearer token",
)
def login(
    payload: LoginRequest,
    db: Session = Depends(get_db),
) -> TokenResponse:
    return authenticate_user(db, payload)
