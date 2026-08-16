"""Alembic environment configuration.

Reads the database URL from MIGRATION_DATABASE_URL (preferred) or
DATABASE_URL (fallback).  The migration URL should point to a role
with elevated privileges (e.g. contract_user) that can create tables,
types, functions, and RLS policies.

Uses SQLAlchemy 2.0 async engine with run_sync to keep migration code
compatible with the async driver (asyncpg).
"""

import asyncio
import os
from logging.config import fileConfig

# Import all models so Base.metadata is populated before autogenerate runs.
import app.models  # noqa: F401 — side-effect import for model registration
from alembic import context
from app.core.config import get_settings

# Import Base so Alembic can discover all models via metadata.
from app.db.base import Base
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

# Alembic Config object — gives access to the alembic.ini values
config = context.config

# Set up Python logging as configured in alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Metadata for autogenerate — Alembic diffs this against the live schema
target_metadata = Base.metadata


def get_url() -> str:
    """Return the migration database URL.

    Prefers MIGRATION_DATABASE_URL (elevated privileges for schema changes)
    and falls back to DATABASE_URL (app runtime connection).
    """
    migration_url = os.environ.get("MIGRATION_DATABASE_URL")
    if migration_url:
        if migration_url.startswith("postgres://"):
            migration_url = migration_url.replace("postgres://", "postgresql+asyncpg://", 1)
        elif migration_url.startswith("postgresql://") and not migration_url.startswith("postgresql+asyncpg://"):
            migration_url = migration_url.replace("postgresql://", "postgresql+asyncpg://", 1)
        if "sslmode=" in migration_url:
            migration_url = migration_url.replace("sslmode=", "ssl=")
        return migration_url
    return get_settings().DATABASE_URL


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (no DB connection required).

    Generates SQL scripts that can be applied manually.
    Useful for auditing migrations before applying to prod.
    """
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Run migrations in 'online' mode with an active DB connection."""
    connectable = create_async_engine(
        get_url(),
        poolclass=pool.NullPool,  # don't pool connections for migration runs
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
