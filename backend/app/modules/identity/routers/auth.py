from fastapi import APIRouter, Request

from app.core.security import DatabaseSession
from app.modules.identity.schemas import LoginRequest, RegisterRequest, TokenResponse, UserRead
from app.modules.identity.schemas.auth import RefreshRequest
from app.modules.identity.services.auth_service import (
    authenticate_user,
    register_user,
    rotate_refresh_token,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", status_code=201)
def register(payload: RegisterRequest, db: DatabaseSession) -> UserRead:
    return register_user(db, payload)


@router.post("/login")
def login(payload: LoginRequest, request: Request, db: DatabaseSession) -> TokenResponse:
    return authenticate_user(db, payload, request.app.state.settings)


@router.post("/refresh")
def refresh(payload: RefreshRequest, request: Request, db: DatabaseSession) -> TokenResponse:
    return rotate_refresh_token(db, payload.refresh_token, request.app.state.settings)
