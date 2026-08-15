"""Shared pytest fixtures and configuration.

pytest-asyncio mode is set to 'auto' in pyproject.toml so all async test
functions are automatically treated as coroutines — no @pytest.mark.asyncio
decorator needed per test.
"""

import os
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock

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
os.environ.setdefault("SUPABASE_URL", "https://test-supabase-project.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "test-supabase-service-role-key-secret-12345")
os.environ.setdefault("SUPABASE_STORAGE_BUCKET", "contract-documents")
os.environ["ENVIRONMENT"] = "development"
os.environ["RATE_LIMIT_ENABLED"] = "False"
os.environ.setdefault("LOG_LEVEL", "DEBUG")
os.environ.setdefault("APP_VERSION", "0.1.0")
os.environ.setdefault("JWT_ALGORITHM", "HS256")
os.environ.setdefault("ACCESS_TOKEN_EXPIRE_MINUTES", "30")
os.environ.setdefault("REFRESH_TOKEN_EXPIRE_DAYS", "7")


@pytest.fixture(autouse=True)
def reset_rate_limiter() -> None:
    """Reset rate limiter state before each test."""
    from app.core.rate_limit import _in_memory_store

    _in_memory_store.clear()


@pytest.fixture(autouse=True)
def mock_get_db() -> AsyncGenerator[AsyncMock, None]:
    """Override get_db FastAPI dependency for all unit tests.

    Prevents endpoints from attempting to connect to a real database
    during unit tests where lifespan startup is not executed.
    """
    from app.db.session import get_db
    from app.main import app

    mock_session = AsyncMock()

    async def _override_get_db() -> AsyncGenerator[AsyncMock, None]:
        yield mock_session

    app.dependency_overrides[get_db] = _override_get_db
    yield mock_session
    app.dependency_overrides.pop(get_db, None)


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
