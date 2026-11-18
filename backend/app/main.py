from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import BACKEND_DIR, Settings
from app.db import models  # noqa: F401
from app.db.session import make_engine, make_session_factory
from app.modules.claims_returns.routers.claims import router as claims_router
from app.modules.claims_returns.routers.returns import router as returns_router
from app.modules.identity.routers import router as identity_router
from app.modules.matching.routers.matches import router as matching_router
from app.modules.notifications_admin.routers import admin_posts_router, notifications_router
from app.modules.notifications_admin.routers.reports import router as reports_router
from app.modules.posts.routers.post_router import router as posts_router
from app.shared.errors import ApiError, error_response, install_error_handlers


def create_app(settings: Settings | None = None, *, engine=None) -> FastAPI:
    settings = settings or Settings()
    database_engine = engine if engine is not None else make_engine(settings)

    @asynccontextmanager
    async def lifespan(app):
        yield
        if engine is None:
            database_engine.dispose()

    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        docs_url=None,
        redoc_url=None,
        responses={
            422: {"model": ApiError, "description": "Invalid request"},
            500: {"model": ApiError, "description": "Internal server error"},
        },
        description=(
            "Đăng tin, tìm kiếm và gợi ý, xác minh sở hữu, trao trả và kiểm duyệt. "
            "Dùng access token JWT từ /api/v1/auth/login để truy cập API yêu cầu xác thực."
        ),
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.session_factory = make_session_factory(database_engine)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()
        ],
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )

    @app.middleware("http")
    async def private_responses(request, call_next):
        request.state.request_id = str(uuid4())
        try:
            response = await call_next(request)
        except Exception:
            # Keep server tracebacks from logging request bodies or SQL parameters.
            response = error_response(request, 500, "INTERNAL_ERROR", "An internal error occurred")
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Request-ID"] = request.state.request_id
        return response

    install_error_handlers(app)
    for router in (
        identity_router,
        posts_router,
        matching_router,
        claims_router,
        returns_router,
        notifications_router,
        admin_posts_router,
        reports_router,
    ):
        app.include_router(router)

    @app.get("/health", include_in_schema=False)
    @app.get("/api/v1/health", tags=["Health"])
    def health():
        try:
            with database_engine.connect() as connection:
                connection.execute(text("SELECT 1"))
        except SQLAlchemyError:
            return JSONResponse(
                status_code=503, content={"status": "degraded", "database": "unavailable"}
            )
        return {"status": "ok", "database": "healthy"}

    app.mount(
        "/swagger-assets",
        StaticFiles(directory=BACKEND_DIR / "app/static/swagger"),
        name="swagger-assets",
    )

    @app.get("/docs", include_in_schema=False)
    def docs():
        return get_swagger_ui_html(
            openapi_url="/openapi.json",
            title="FindBack — Swagger UI",
            swagger_js_url="/swagger-assets/swagger-ui-bundle.js",
            swagger_css_url="/swagger-assets/swagger-ui.css",
            swagger_favicon_url="/swagger-assets/favicon-32x32.png",
            swagger_ui_parameters={"displayRequestDuration": True, "tryItOutEnabled": True},
        )

    return app
