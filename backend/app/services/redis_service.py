"""Redis service for async caching with JSON serialization.

Provides a thin wrapper around ``redis.asyncio`` with :meth:`get`,
:meth:`set`, and :meth:`delete` methods that handle JSON
serialization/deserialization automatically, plus lifecycle helpers
and a FastAPI dependency.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import redis.asyncio as aioredis

from app.services.llm_service import settings

logger = logging.getLogger(__name__)

_redis_service: RedisService | None = None


class RedisService:
    """Async Redis client wrapper with JSON serialization.

    Attributes:
        _client: The underlying async Redis connection.
    """

    def __init__(self, client: aioredis.Redis) -> None:
        """Initialise the service with an existing Redis connection.

        Args:
            client: An ``redis.asyncio.Redis`` instance.
        """
        self._client: aioredis.Redis = client

    async def get(self, key: str) -> Any | None:
        """Retrieve and deserialise a JSON value from Redis.

        Args:
            key: The cache key.

        Returns:
            The deserialised Python object, or ``None`` if the key
            does not exist.
        """
        raw: bytes | str | None = await self._client.get(key)
        if raw is None:
            return None
        return json.loads(raw)

    async def set(
        self,
        key: str,
        value: Any,
        *,
        ttl: int | None = None,
    ) -> None:
        """Serialise a value to JSON and store it in Redis.

        Args:
            key: The cache key.
            value: Any JSON-serialisable Python object.
            ttl: Optional time-to-live in seconds.  If ``None`` the key
                will not expire.
        """
        serialised = json.dumps(value, default=str)
        if ttl is not None:
            await self._client.setex(key, ttl, serialised)
        else:
            await self._client.set(key, serialised)

    async def delete(self, key: str) -> bool:
        """Delete a key from Redis.

        Args:
            key: The cache key to remove.

        Returns:
            ``True`` if the key existed and was deleted, ``False``
            otherwise.
        """
        result: int = await self._client.delete(key)
        return result > 0

    async def close(self) -> None:
        """Gracefully close the underlying Redis connection."""
        await self._client.aclose()


# ---------------------------------------------------------------------------
# Lifecycle helpers
# ---------------------------------------------------------------------------


async def init_redis() -> RedisService:
    """Create the global :class:`RedisService` instance.

    Reads the Redis URL from :data:`settings` and pings the server to
    verify connectivity.

    Returns:
        The initialised :class:`RedisService`.

    Raises:
        ConnectionError: If the Redis server is unreachable.
    """
    global _redis_service

    client = aioredis.from_url(
        settings.REDIS_URL,
        decode_responses=False,
        encoding="utf-8",
    )

    # Verify connectivity
    try:
        await client.ping()
        logger.info("Redis connected – %s", settings.REDIS_URL)
    except Exception as exc:
        logger.warning(
            "Redis ping failed (%s); caching will be unavailable: %s",
            settings.REDIS_URL,
            exc,
        )

    _redis_service = RedisService(client)
    return _redis_service


async def close_redis() -> None:
    """Close the global Redis connection and reset the singleton."""
    global _redis_service

    if _redis_service is not None:
        await _redis_service.close()
        _redis_service = None
        logger.info("Redis connection closed")


# ---------------------------------------------------------------------------
# FastAPI dependency
# ---------------------------------------------------------------------------


async def get_redis() -> RedisService:
    """FastAPI dependency that returns the global :class:`RedisService`.

    Returns:
        The active :class:`RedisService` instance.

    Raises:
        RuntimeError: If :func:`init_redis` has not been called.
    """
    if _redis_service is None:
        raise RuntimeError(
            "RedisService is not initialised. "
            "Ensure init_redis() is called during application startup."
        )
    return _redis_service
