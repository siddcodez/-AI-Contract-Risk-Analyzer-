"""Alembic environment configuration.

Reads the DATABASE_URL from app.core.config (which reads from environment
variables / .env) so secrets never appear in alembic.ini or version control.

Uses SQLAlchemy 2.0 async engine with run_sync to keep migration code
compatible with the async driver (asyncpg).
"""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

# Import Base so Alembic can discover all models via metadata.
# As models are added in later milestones, ensure they are imported
# somewhere that Base.metadata knows about them — the easiest way is
# to import them in app/models/__init__.py.
from app.db.base import Base
from app.core.config import get_settings

# Alembic Config object — gives access to the alembic.ini values
config = context.config

# Set up Python logging as configured in alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Metadata for autogenerate — Alembic diffs this against the live schema
target_metadata = Base.metadata


def get_url() -> str:
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
