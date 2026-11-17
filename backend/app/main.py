from contextlib import asynccontextmanager
from typing import AsyncGenerator
from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.core.config import settings
from app.db.session import engine
from app.modules.notifications_admin.routers.notifications import router as notifications_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Lifespan context manager for startup and shutdown events."""
    # Startup: engine is initialized
    yield
    # Shutdown: dispose database pool
    await engine.dispose()


app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    description="FindBack – Smart Lost & Found Management System API",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get(
    "/health",
    tags=["Health"],
    summary="Health check endpoint",
    status_code=status.HTTP_200_OK,
)
@app.get(
    f"{settings.API_V1_PREFIX}/health",
    tags=["Health"],
    summary="API v1 Health check endpoint",
    status_code=status.HTTP_200_OK,
)
async def health_check() -> dict[str, str]:
    """Verifies service and database connectivity."""
    db_status = "healthy"
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"

    return {
        "status": "ok" if "unhealthy" not in db_status else "degraded",
        "app": settings.APP_NAME,
        "environment": settings.APP_ENV,
        "database": db_status,
    }


# Mount API routers
app.include_router(
    notifications_router,
    prefix=settings.API_V1_PREFIX,
)
