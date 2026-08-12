"""Async SQLAlchemy database session management.

Provides:
- async_engine: the connection pool (created once at startup).
- AsyncSessionLocal: session factory.
- get_db(): FastAPI dependency that yields a session per request.
- check_db_connection(): utility for health checks.
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.sql import text

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Module-level references — set during lifespan startup, used throughout the app.
# Never accessed before startup completes (FastAPI lifespan guarantees this).
_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def _get_engine() -> AsyncEngine:
    if _engine is None:
        raise RuntimeError("Database engine not initialised. Call init_db() first.")
    return _engine


def _get_session_factory() -> async_sessionmaker[AsyncSession]:
    if _session_factory is None:
        raise RuntimeError("Session factory not initialised. Call init_db() first.")
    return _session_factory


def init_db() -> None:
    """Initialise the async engine and session factory.

    Called once during application startup (lifespan).
    """
    global _engine, _session_factory

    settings = get_settings()

    _engine = create_async_engine(
        settings.DATABASE_URL,
        echo=settings.is_development,  # log SQL in dev; silent in prod
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,  # recycles stale connections transparently
    )

    _session_factory = async_sessionmaker(
        bind=_engine,
        class_=AsyncSession,
        expire_on_commit=False,  # avoid lazy-load surprises after commit
        autoflush=False,
    )

    logger.info("Database engine initialised", database_url=settings.DATABASE_URL.split("@")[-1])


async def close_db() -> None:
    """Dispose the engine (called during application shutdown)."""
    global _engine

    if _engine is not None:
        await _engine.dispose()
        _engine = None
        logger.info("Database engine disposed")


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency — yields a database session for the current request.

    Commits on success, rolls back on any exception, always closes.
    Never use auto-commit — explicit commit is intentional.
    """
    async with _get_session_factory()() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def check_db_connection() -> bool:
    """Ping the database. Returns True on success, False on failure.

    Used by the health check endpoint — never raises, always returns bool.
    """
    try:
        async with _get_session_factory()() as session:
            await session.execute(text("SELECT 1"))
        return True
    except Exception as exc:
        logger.warning("Database health check failed", exc_info=exc)
        return False
