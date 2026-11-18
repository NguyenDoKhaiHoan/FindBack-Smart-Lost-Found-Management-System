from fastapi import APIRouter

from app.modules.identity.routers.auth import router as auth_router
from app.modules.identity.routers.users import router as users_router

router = APIRouter(prefix="/api/v1")
router.include_router(auth_router)
router.include_router(users_router)

__all__ = ["router"]
