from uuid import uuid4

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException


class ErrorDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")
    field: str
    issue: str


class ErrorBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str
    message: str
    request_id: str
    details: list[ErrorDetail]


class ApiError(BaseModel):
    model_config = ConfigDict(extra="forbid")
    error: ErrorBody


class DomainError(Exception):
    def __init__(self, status: int, code: str, message: str, details: list | None = None):
        self.status = status
        self.code = code
        self.message = message
        self.details = details or []


def error_response(request: Request, status: int, code: str, message: str, details=None):
    headers = {"Cache-Control": "no-store"}
    if status == 401:
        headers["WWW-Authenticate"] = "Bearer"
    return JSONResponse(
        status_code=status,
        headers=headers,
        content={
            "error": {
                "code": code,
                "message": message,
                "request_id": getattr(request.state, "request_id", str(uuid4())),
                "details": details or [],
            }
        },
    )


def install_error_handlers(app):
    @app.exception_handler(DomainError)
    async def domain_error(request: Request, exc: DomainError):
        return error_response(request, exc.status, exc.code, exc.message, exc.details)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        # Neither input, ctx nor error messages can echo private user-supplied content.
        details = [
            {
                "field": ".".join(str(part) for part in error["loc"]),
                "issue": "Invalid value",
            }
            for error in exc.errors()
        ]
        return error_response(request, 422, "VALIDATION_ERROR", "Invalid request data", details)

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException):
        return error_response(request, exc.status_code, "HTTP_ERROR", "Request not available")

    @app.exception_handler(SQLAlchemyError)
    @app.exception_handler(Exception)
    async def server_error(request: Request, exc: Exception):
        # Do not log exception strings: SQL parameters can contain private evidence.
        return error_response(request, 500, "INTERNAL_ERROR", "An internal error occurred")
