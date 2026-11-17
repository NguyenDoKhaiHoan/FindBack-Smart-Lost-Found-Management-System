from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .modules.matching.repositories.snapshots import SnapshotReader, UnavailableReader
from .modules.matching.routers.matches import router
from .modules.matching.schemas.contracts import ErrorBody, ErrorResponse
from .modules.matching.services.matches import MatchingError


def create_app(reader: SnapshotReader | None = None) -> FastAPI:
    app = FastAPI(title="FindBack Matching", version="0.1.0")
    app.state.matching_reader = reader if reader is not None else UnavailableReader()
    app.include_router(router)

    @app.exception_handler(MatchingError)
    async def matching_error(request: Request, exc: MatchingError):
        response = ErrorResponse(error=ErrorBody(code=exc.code, message=exc.message, details=getattr(exc, "details", [])))
        return JSONResponse(status_code=exc.status, content=response.model_dump(mode="json"))

    @app.exception_handler(Exception)
    async def unexpected_error(request: Request, exc: Exception):
        response = ErrorResponse(error=ErrorBody(code="INTERNAL_ERROR", message="Không thể xử lý yêu cầu."))
        return JSONResponse(status_code=500, content=response.model_dump(mode="json"))

    return app


app = create_app()
