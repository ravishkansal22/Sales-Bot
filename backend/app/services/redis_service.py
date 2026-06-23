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
redis_available: bool = False


def disable_redis() -> None:
    """Disable Redis caching and circuit breaker state storage globally."""
    global _redis_service, redis_available
    _redis_service = None
    redis_available = False
    logger.warning("Redis has been disabled globally.")


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
        self.is_available: bool = True

    async def get(self, key: str) -> Any | None:
        """Retrieve and deserialise a JSON value from Redis.

        Args:
            key: The cache key.

        Returns:
            The deserialised Python object, or ``None`` if the key
            does not exist.
        """
        if not self.is_available or not redis_available:
            return None
        try:
            raw: bytes | str | None = await self._client.get(key)
            if raw is None:
                return None
            return json.loads(raw)
        except Exception as exc:
            logger.warning("Redis read failed: %s. Disabling Redis globally.", exc)
            self.is_available = False
            disable_redis()
            return None

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
        if not self.is_available or not redis_available:
            return None
        try:
            serialised = json.dumps(value, default=str)
            if ttl is not None:
                await self._client.setex(key, ttl, serialised)
            else:
                await self._client.set(key, serialised)
        except Exception as exc:
            logger.warning("Redis write failed: %s. Disabling Redis globally.", exc)
            self.is_available = False
            disable_redis()

    async def delete(self, key: str) -> bool:
        """Delete a key from Redis.

        Args:
            key: The cache key to remove.

        Returns:
            ``True`` if the key existed and was deleted, ``False``
            otherwise.
        """
        if not self.is_available or not redis_available:
            return False
        try:
            result: int = await self._client.delete(key)
            return result > 0
        except Exception as exc:
            logger.warning("Redis delete failed: %s. Disabling Redis globally.", exc)
            self.is_available = False
            disable_redis()
            return False

    async def close(self) -> None:
        """Gracefully close the underlying Redis connection."""
        if self.is_available:
            try:
                await self._client.aclose()
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Lifecycle helpers
# ---------------------------------------------------------------------------


async def init_redis() -> RedisService | None:
    """Create the global :class:`RedisService` instance.

    Reads the Redis URL from :data:`settings` and pings the server to
    verify connectivity.

    Returns:
        The initialised :class:`RedisService` or None if connectivity failed.
    """
    global _redis_service, redis_available

    client = aioredis.from_url(
        settings.REDIS_URL,
        decode_responses=False,
        encoding="utf-8",
    )

    # Verify connectivity
    try:
        await client.ping()
        logger.info("Redis connected – %s", settings.REDIS_URL)
        _redis_service = RedisService(client)
        redis_available = True
    except Exception as exc:
        logger.warning(
            "Redis ping failed (%s); caching will be unavailable: %s",
            settings.REDIS_URL,
            exc,
        )
        _redis_service = None
        redis_available = False

    return _redis_service


async def close_redis() -> None:
    """Close the global Redis connection and reset the singleton."""
    global _redis_service, redis_available

    if _redis_service is not None:
        await _redis_service.close()
        _redis_service = None
        redis_available = False
        logger.info("Redis connection closed")


# ---------------------------------------------------------------------------
# FastAPI dependency
# ---------------------------------------------------------------------------


async def get_redis() -> RedisService | None:
    """FastAPI dependency that returns the global :class:`RedisService`.

    Returns:
        The active :class:`RedisService` instance.
    """
    return _redis_service
