"""PostgreSQL lifecycle management and FastAPI dependency.

Provides the ``get_db`` async generator for use as a FastAPI dependency,
plus ``init_db`` / ``close_db`` helpers intended to be called from the
application lifespan context manager.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import Base, dispose_engine, get_engine, get_session_factory
from app.services.llm_service import settings

logger = logging.getLogger(__name__)


async def init_db() -> None:
    """Initialise the database engine and session factory.

    Call this once during application startup (inside the lifespan
    context manager).  In production the schema is managed by Alembic;
    the ``create_all`` call here is a convenience for local development
    and can be removed when migrations are in place.
    """
    engine = get_engine(settings.DATABASE_URL, echo=settings.DEBUG)
    get_session_factory(engine)

    # Create tables that don't yet exist (dev convenience).
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    logger.info("Database engine initialised – %s", settings.DATABASE_URL)


async def close_db() -> None:
    """Dispose the database engine and release all connections.

    Call this during application shutdown.
    """
    await dispose_engine()
    logger.info("Database engine disposed")


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields an async database session.

    The session is automatically committed on success and rolled back on
    exception, then closed in the ``finally`` block.

    Yields:
        An :class:`AsyncSession` bound to the current engine.

    Raises:
        RuntimeError: If the session factory has not been initialised
            (i.e. ``init_db`` was not called).
    """
    engine = get_engine(settings.DATABASE_URL)
    factory = get_session_factory(engine)
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
