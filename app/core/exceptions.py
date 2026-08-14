"""Application exception hierarchy and FastAPI error handlers.

All domain exceptions inherit from AppError, which carries a machine-readable
`code` and an HTTP status code. FastAPI exception handlers map these to a
consistent JSON envelope:

    {"error": {"code": "NOT_FOUND", "message": "...", "details": {...}}}

This envelope is the contract every client depends on — never change its shape
without a versioned API change.
"""

from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

# ---------------------------------------------------------------------------
# Base exception
# ---------------------------------------------------------------------------


class AppError(Exception):
    """Base class for all application-level exceptions.

    Attributes:
        message: Human-readable error description.
        code:    Machine-readable error code (SCREAMING_SNAKE_CASE).
        status_code: HTTP status code to return.
        details: Optional dict with structured extra context (safe to return
                 to clients — never include internal stack traces or secrets).
    """

    message: str = "An unexpected error occurred"
    code: str = "INTERNAL_ERROR"
    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR

    def __init__(
        self,
        message: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.message = message or self.__class__.message
        self.details = details or {}
        super().__init__(self.message)


# ---------------------------------------------------------------------------
# Concrete exception types
# ---------------------------------------------------------------------------


class NotFoundError(AppError):
    message = "Resource not found"
    code = "NOT_FOUND"
    status_code = status.HTTP_404_NOT_FOUND


class AuthenticationError(AppError):
    message = "Authentication required"
    code = "UNAUTHORIZED"
    status_code = status.HTTP_401_UNAUTHORIZED


class ForbiddenError(AppError):
    message = "You do not have permission to perform this action"
    code = "FORBIDDEN"
    status_code = status.HTTP_403_FORBIDDEN


class ConflictError(AppError):
    message = "Resource already exists"
    code = "CONFLICT"
    status_code = status.HTTP_409_CONFLICT


class ValidationError(AppError):
    message = "Request validation failed"
    code = "VALIDATION_ERROR"
    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT


class RateLimitError(AppError):
    message = "Too many requests"
    code = "RATE_LIMITED"
    status_code = status.HTTP_429_TOO_MANY_REQUESTS


class StorageError(AppError):
    message = "Object storage operation failed"
    code = "STORAGE_ERROR"
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR


class ProcessingError(AppError):
    message = "Document processing failed"
    code = "PROCESSING_ERROR"
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR


class LLMError(AppError):
    message = "AI service encountered an error"
    code = "LLM_ERROR"
    status_code = status.HTTP_502_BAD_GATEWAY


# ---------------------------------------------------------------------------
# FastAPI exception handlers
# ---------------------------------------------------------------------------


def _get_request_id(request: Request) -> str:
    """Retrieve request ID from context var or header."""
    from app.core.logging import request_id_ctx

    return request_id_ctx.get("") or request.headers.get("X-Request-ID", "")


def _make_error_response(
    status_code: int,
    code: str,
    message: str,
    request: Request,
    details: dict[str, Any] | None = None,
) -> JSONResponse:
    req_id = _get_request_id(request)
    error_body: dict[str, Any] = {
        "code": code,
        "message": message,
        "request_id": req_id,
    }
    if details:
        error_body["details"] = details

    return JSONResponse(
        status_code=status_code,
        content={"error": error_body},
        headers={"X-Request-ID": req_id} if req_id else None,
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Register all exception handlers on the FastAPI app instance."""
    from fastapi.exceptions import RequestValidationError
    from pydantic import ValidationError as PydanticValidationError
    from sqlalchemy.exc import SQLAlchemyError
    from starlette.exceptions import HTTPException as StarletteHTTPException

    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        return _make_error_response(
            status_code=exc.status_code,
            code=exc.code,
            message=exc.message,
            request=request,
            details=exc.details,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        from app.core.logging import get_logger

        logger = get_logger(__name__)
        logger.warning(
            "Request validation failed",
            path=request.url.path,
            method=request.method,
            errors=exc.errors(),
        )
        return _make_error_response(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code="VALIDATION_ERROR",
            message="Request validation failed",
            request=request,
            details={"errors": exc.errors()},
        )

    @app.exception_handler(PydanticValidationError)
    async def pydantic_validation_error_handler(
        request: Request, exc: PydanticValidationError
    ) -> JSONResponse:
        return _make_error_response(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code="VALIDATION_ERROR",
            message="Request validation failed",
            request=request,
            details={"errors": exc.errors()},
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code_map = {
            status.HTTP_401_UNAUTHORIZED: "UNAUTHORIZED",
            status.HTTP_403_FORBIDDEN: "FORBIDDEN",
            status.HTTP_404_NOT_FOUND: "NOT_FOUND",
            status.HTTP_409_CONFLICT: "CONFLICT",
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE: "UNSUPPORTED_MEDIA_TYPE",
            status.HTTP_422_UNPROCESSABLE_CONTENT: "VALIDATION_ERROR",
            status.HTTP_429_TOO_MANY_REQUESTS: "RATE_LIMITED",
        }
        code = code_map.get(exc.status_code, "HTTP_ERROR")
        return _make_error_response(
            status_code=exc.status_code,
            code=code,
            message=str(exc.detail),
            request=request,
        )

    @app.exception_handler(SQLAlchemyError)
    async def database_error_handler(request: Request, exc: SQLAlchemyError) -> JSONResponse:
        from app.core.logging import get_logger

        logger = get_logger(__name__)
        logger.error(
            "Database error",
            exc_info=exc,
            path=request.url.path,
            method=request.method,
        )
        return _make_error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            code="DATABASE_ERROR",
            message="A database error occurred.",
            request=request,
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        # Log with full traceback but do NOT expose internal details to the client
        from app.core.logging import get_logger

        logger = get_logger(__name__)
        logger.error(
            "Unhandled exception",
            exc_info=True,
            path=request.url.path,
            method=request.method,
        )
        return _make_error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            code="INTERNAL_ERROR",
            message="An internal error occurred. Please try again later.",
            request=request,
        )
