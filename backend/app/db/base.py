"""Async SQLAlchemy engine, session factory, and declarative base.

This module provides the foundational database infrastructure for the
Ghost Negotiator backend, including the async engine, session factory,
and the ORM declarative base class that all models inherit from.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import (
    AsyncAttrs,
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


class Base(AsyncAttrs, DeclarativeBase):
    """Declarative base class for all ORM models.

    Inherits from ``AsyncAttrs`` so that relationship attributes can be
    awaited directly when using the async session, and from
    ``DeclarativeBase`` which is the Pydantic-v2-era replacement for the
    legacy ``declarative_base()`` function.
    """


def get_engine(database_url: str, *, echo: bool = False) -> AsyncEngine:
    """Create or return the singleton async engine.

    Args:
        database_url: The async-compatible database URL
            (e.g. ``postgresql+asyncpg://…``).
        echo: If ``True``, the engine logs all generated SQL.

    Returns:
        The global :class:`AsyncEngine` instance.
    """
    global _engine
    if _engine is None:
        _engine = create_async_engine(
            database_url,
            echo=echo,
            pool_pre_ping=True,
            pool_size=10,
            max_overflow=20,
        )
    return _engine


def get_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Create or return the singleton async session factory.

    Args:
        engine: The :class:`AsyncEngine` to bind sessions to.

    Returns:
        A configured :class:`async_sessionmaker` instance.
    """
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            bind=engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )
    return _session_factory


async def dispose_engine() -> None:
    """Dispose the global engine and reset module-level singletons.

    This should be called during application shutdown to cleanly release
    all pooled database connections.
    """
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
    _session_factory = None
