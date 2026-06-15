"""Alembic environment configuration — async migrations for Ghost Negotiator.

This module is executed by Alembic when running ``alembic upgrade``,
``alembic downgrade``, or ``alembic revision``.  It supports **async**
migrations via ``asyncpg`` by wrapping the migration runner in
``run_async_migrations()``.

The ``DATABASE_URL`` environment variable **must** be set.  It is read
at runtime and injected into the Alembic ``Config`` so that the
placeholder in ``alembic.ini`` is never used.
"""

from __future__ import annotations

import asyncio
import os
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# ---------------------------------------------------------------------------
# Import the declarative Base so Alembic can detect table metadata, then
# import every model module to ensure all tables are registered.
# ---------------------------------------------------------------------------
from app.db.postgres import Base
from app.models.conversation import Conversation  # noqa: F401
from app.models.customer import Customer, DigitalTwinSnapshot  # noqa: F401
from app.models.simulation import SimulationResult  # noqa: F401

# ---------------------------------------------------------------------------
# Alembic Config & logging
# ---------------------------------------------------------------------------
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# ---------------------------------------------------------------------------
# Override sqlalchemy.url from environment
# ---------------------------------------------------------------------------
DATABASE_URL: str = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://ghost:ghost_secret@localhost:5432/ghost_negotiator",
)
config.set_main_option("sqlalchemy.url", DATABASE_URL)


# ---------------------------------------------------------------------------
# Offline (SQL-script) mode
# ---------------------------------------------------------------------------


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL and not an ``Engine``,
    though an ``Engine`` is acceptable here as well.  By skipping the
    ``Engine`` creation we don't even need a DBAPI to be available.

    Calls to ``context.execute()`` here emit the given string to the
    script output.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


# ---------------------------------------------------------------------------
# Online (async engine) mode
# ---------------------------------------------------------------------------


def do_run_migrations(connection: Connection) -> None:
    """Execute migrations against a live connection.

    Parameters
    ----------
    connection:
        Synchronous connection wrapper provided by the async engine's
        ``run_sync`` method.
    """
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Create an async engine, obtain a connection, and run migrations.

    This is the primary entrypoint for online (connected) migrations
    when the ``sqlalchemy.url`` uses an async driver such as
    ``asyncpg``.
    """
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Dispatch to the async migration runner.

    Alembic's entry-point calls this function synchronously, so we use
    ``asyncio.run`` to bridge into the async world.
    """
    asyncio.run(run_async_migrations())


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
