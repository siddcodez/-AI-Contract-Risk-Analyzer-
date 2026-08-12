"""Unit tests for app.core modules (config, logging, exceptions)."""

import logging

from app.core.config import get_settings
from app.core.exceptions import (
    NotFoundError,
    ValidationError,
    register_exception_handlers,
)
from app.core.logging import configure_logging, get_logger
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient


class TestConfig:
    def test_settings_singleton_and_properties(self) -> None:
        settings = get_settings()
        assert settings.APP_VERSION == "0.1.0"
        assert settings.is_development is True or settings.is_production is False


class TestLogging:
    def test_get_logger(self) -> None:
        logger = get_logger("test_module")
        assert logger is not None

    def test_configure_logging(self) -> None:
        configure_logging()
        root_logger = logging.getLogger()
        assert root_logger.level in (logging.DEBUG, logging.INFO)


class TestExceptions:
    def test_app_error_attributes(self) -> None:
        exc = NotFoundError(message="Contract missing", details={"id": 42})
        assert exc.status_code == 404
        assert exc.code == "NOT_FOUND"
        assert exc.message == "Contract missing"
        assert exc.details == {"id": 42}

    def test_validation_error(self) -> None:
        exc = ValidationError(message="Invalid format")
        assert exc.status_code == 422
        assert exc.code == "VALIDATION_ERROR"

    async def test_registered_exception_handlers(self) -> None:
        test_app = FastAPI()
        register_exception_handlers(test_app)

        @test_app.get("/error")
        async def raise_error() -> None:
            raise NotFoundError(message="Not here")

        @test_app.get("/crash")
        async def raise_crash() -> None:
            raise RuntimeError("Boom")

        async with AsyncClient(
            transport=ASGITransport(app=test_app, raise_app_exceptions=False),
            base_url="http://test",
        ) as client:
            resp_404 = await client.get("/error")
            assert resp_404.status_code == 404
            assert resp_404.json()["error"]["code"] == "NOT_FOUND"

            resp_500 = await client.get("/crash")
            assert resp_500.status_code == 500
            assert resp_500.json()["error"]["code"] == "INTERNAL_ERROR"
