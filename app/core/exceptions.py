"""Application exception hierarchy and FastAPI error handlers.

All domain exceptions inherit from AppError, which carries a machine-readable
`code` and an HTTP status code. FastAPI exception handlers map these to a
consistent JSON envelope:

    {"error": {"code": "NOT_FOUND", "message": "...", "details": {...}}}

This envelope is the contract every client depends on — never change its shape
without a versioned API change.
"""

from collections.abc import Callable, Coroutine
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


# ---------------------------------------------------------------------------
# FastAPI exception handlers
# ---------------------------------------------------------------------------


def _make_error_response(exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
                "details": exc.details,
            }
        },
    )


HandlerType = Callable[[Request, Any], Coroutine[Any, Any, JSONResponse]]


def register_exception_handlers(app: FastAPI) -> None:
    """Register all exception handlers on the FastAPI app instance."""

    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        return _make_error_response(exc)

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        # Log but do NOT expose internal details to the client
        from app.core.logging import get_logger

        logger = get_logger(__name__)
        logger.error(
            "Unhandled exception",
            exc_info=exc,
            path=request.url.path,
            method=request.method,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "An internal error occurred. Please try again later.",
                    "details": {},
                }
            },
        )
