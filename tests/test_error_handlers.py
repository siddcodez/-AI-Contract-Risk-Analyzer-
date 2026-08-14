"""Tests for centralized API exception handlers and error response envelope."""

from typing import Any

import pytest
from app.core.exceptions import (
    AppError,
    AuthenticationError,
    ForbiddenError,
    NotFoundError,
    RateLimitError,
    ValidationError,
    register_exception_handlers,
)
from app.middleware.request_id import RequestIDMiddleware
from fastapi import FastAPI, HTTPException, status
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel, Field
from sqlalchemy.exc import SQLAlchemyError


def _create_test_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(RequestIDMiddleware)
    register_exception_handlers(app)

    class DummyPayload(BaseModel):
        name: str = Field(min_length=3)
        count: int = Field(gt=0)

    @app.get("/test-app-error")
    async def trigger_app_error() -> Any:
        raise AppError("Custom error message", details={"field": "test"})

    @app.get("/test-not-found")
    async def trigger_not_found() -> Any:
        raise NotFoundError("Contract not found")

    @app.get("/test-auth-error")
    async def trigger_auth_error() -> Any:
        raise AuthenticationError("Invalid token")

    @app.get("/test-forbidden")
    async def trigger_forbidden() -> Any:
        raise ForbiddenError("Permission denied")

    @app.get("/test-validation")
    async def trigger_validation() -> Any:
        raise ValidationError("Invalid input")

    @app.get("/test-rate-limit")
    async def trigger_rate_limit() -> Any:
        raise RateLimitError("Too many requests")

    @app.get("/test-db-error")
    async def trigger_db_error() -> Any:
        raise SQLAlchemyError("SELECT * FROM secret_table WHERE pass = '1234'")

    @app.get("/test-unhandled")
    async def trigger_unhandled() -> Any:
        raise RuntimeError("Internal crash trace /secret/filepath.py line 42")

    @app.get("/test-http-exc")
    async def trigger_http_exc() -> Any:
        raise HTTPException(status_code=415, detail="Unsupported Media Type")

    @app.post("/test-pydantic-val")
    async def trigger_pydantic_val(payload: DummyPayload) -> Any:
        return payload.model_dump()

    return app


@pytest.fixture
def error_app_client() -> AsyncClient:
    app = _create_test_app()
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver")


@pytest.mark.asyncio
async def test_app_error_handler_envelope(error_app_client: AsyncClient) -> None:
    res = await error_app_client.get("/test-app-error", headers={"X-Request-ID": "req-app-1"})
    assert res.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    data = res.json()
    assert "error" in data
    err = data["error"]
    assert err["code"] == "INTERNAL_ERROR"
    assert err["message"] == "Custom error message"
    assert err["request_id"] == "req-app-1"
    assert err["details"] == {"field": "test"}


@pytest.mark.asyncio
async def test_not_found_error_envelope(error_app_client: AsyncClient) -> None:
    res = await error_app_client.get("/test-not-found", headers={"X-Request-ID": "req-nf-1"})
    assert res.status_code == status.HTTP_404_NOT_FOUND
    err = res.json()["error"]
    assert err["code"] == "NOT_FOUND"
    assert err["message"] == "Contract not found"
    assert err["request_id"] == "req-nf-1"


@pytest.mark.asyncio
async def test_auth_and_forbidden_envelope(error_app_client: AsyncClient) -> None:
    res1 = await error_app_client.get("/test-auth-error")
    assert res1.status_code == status.HTTP_401_UNAUTHORIZED
    assert res1.json()["error"]["code"] == "UNAUTHORIZED"

    res2 = await error_app_client.get("/test-forbidden")
    assert res2.status_code == status.HTTP_403_FORBIDDEN
    assert res2.json()["error"]["code"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_validation_error_envelope(error_app_client: AsyncClient) -> None:
    res = await error_app_client.post("/test-pydantic-val", json={"name": "a", "count": -5})
    assert res.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    err = res.json()["error"]
    assert err["code"] == "VALIDATION_ERROR"
    assert err["message"] == "Request validation failed"
    assert "details" in err
    assert "request_id" in err


@pytest.mark.asyncio
async def test_database_error_does_not_leak_sql(error_app_client: AsyncClient) -> None:
    res = await error_app_client.get("/test-db-error", headers={"X-Request-ID": "req-db-1"})
    assert res.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    err = res.json()["error"]
    assert err["code"] == "DATABASE_ERROR"
    assert err["message"] == "A database error occurred."
    assert "SELECT" not in res.text
    assert "secret_table" not in res.text


@pytest.mark.asyncio
async def test_unhandled_exception_does_not_leak_stack_trace(error_app_client: AsyncClient) -> None:
    res = await error_app_client.get("/test-unhandled", headers={"X-Request-ID": "req-crash-1"})
    assert res.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    err = res.json()["error"]
    assert err["code"] == "INTERNAL_ERROR"
    assert err["message"] == "An internal error occurred. Please try again later."
    assert "RuntimeError" not in res.text
    assert "filepath.py" not in res.text


@pytest.mark.asyncio
async def test_http_exception_envelope(error_app_client: AsyncClient) -> None:
    res = await error_app_client.get("/test-http-exc")
    assert res.status_code == status.HTTP_415_UNSUPPORTED_MEDIA_TYPE
    err = res.json()["error"]
    assert err["code"] == "UNSUPPORTED_MEDIA_TYPE"
    assert err["message"] == "Unsupported Media Type"
