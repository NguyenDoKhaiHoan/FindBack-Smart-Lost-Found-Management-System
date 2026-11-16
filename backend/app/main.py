from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.staticfiles import StaticFiles

from app.core.config import BACKEND_DIR, Settings
from app.db import models  # noqa: F401
from app.db.session import make_engine, make_session_factory
from app.modules.claims_returns.routers.claims import router
from app.shared.errors import error_response, install_error_handlers


def create_app(settings: Settings | None = None, *, engine=None) -> FastAPI:
    settings = settings or Settings()
    database_engine = engine if engine is not None else make_engine(settings)

    @asynccontextmanager
    async def lifespan(app):
        yield
        if engine is None:
            database_engine.dispose()

    app = FastAPI(
        title="FindBack Claims API",
        version="0.1.0",
        docs_url=None,
        redoc_url=None,
        description=(
            "Tạo và xem yêu cầu nhận đồ. Authorize bằng JWT Bearer. "
            "Chỉ người gửi claim và chủ tin được xem bằng chứng. "
            "relation: claimant (đã gửi), reviewer (trên tin của tôi), all (cả hai)."
        ),
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.session_factory = make_session_factory(database_engine)

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
    app.include_router(router)
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
