"""Shared pytest fixtures and configuration.

pytest-asyncio mode is set to 'auto' in pyproject.toml so all async test
functions are automatically treated as coroutines — no @pytest.mark.asyncio
decorator needed per test.
"""

import os
from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient

# ---------------------------------------------------------------------------
# Ensure test env vars are set before importing the app.
# In CI these come from the workflow env block; locally from .env.
# We set minimal overrides here so tests can run without a real .env file.
# ---------------------------------------------------------------------------

os.environ.setdefault("SECRET_KEY", "test-secret-key-minimum-32-chars-long-xxx")
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://contract_user:contract_pass@localhost:5432/contract_risk_db",
)
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("CELERY_BROKER_URL", "redis://localhost:6379/1")
os.environ.setdefault("CELERY_RESULT_BACKEND", "redis://localhost:6379/2")
os.environ.setdefault("MINIO_ENDPOINT", "http://localhost:9000")
os.environ.setdefault("MINIO_ACCESS_KEY", "minioadmin")
os.environ.setdefault("MINIO_SECRET_KEY", "minioadmin")
os.environ.setdefault("MINIO_BUCKET_NAME", "contract-documents")
os.environ.setdefault("MINIO_USE_SSL", "False")
os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("LOG_LEVEL", "DEBUG")
os.environ.setdefault("APP_VERSION", "0.1.0")
os.environ.setdefault("JWT_ALGORITHM", "HS256")
os.environ.setdefault("ACCESS_TOKEN_EXPIRE_MINUTES", "30")
os.environ.setdefault("REFRESH_TOKEN_EXPIRE_DAYS", "7")


@pytest.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    """HTTP client wired directly to the FastAPI ASGI app.

    No real network call — uses httpx's ASGITransport. This means:
    - Tests run without a network stack.
    - The app's lifespan (startup/shutdown) is NOT invoked automatically
      unless we use the 'lifespan' argument below.

    For unit tests of individual endpoints we mock the service dependencies,
    so lifespan is not needed. Integration tests will use a separate fixture
    that triggers the full lifespan.
    """
    from app.main import app  # import after env vars are set

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        yield client
