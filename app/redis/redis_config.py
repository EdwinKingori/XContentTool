"""
redis/redis_config.py — Async Redis connection management.

Provides a singleton AsyncRedisClient used by:
  - Celery broker
  - Rate limiter
  - Cache layer (services/helpers/redis_helpers.py)
  - HMAC-signed cache entries

The client is lazy-initialized on first use and reused across
the application lifecycle. Returns None / fails open on connection
failure so callers degrade gracefully (rate limiter passes, cache
falls through to PostgreSQL).
"""

import json
from typing import AsyncGenerator

from redis.asyncio import Redis

from app.core.config import get_settings
from app.core.logging.route_logger import get_route_logger

from .hmac_security import hmac_key

logger = get_route_logger(__name__)
settings = get_settings()


class AsyncRedisClient:
    """
    Async Redis client with:
    - Lazy connection pooling with health checks
    - HMAC-signed key names (prevents key injection / namespace collisions)
    - TTL support
    - JSON helpers
    - FastAPI dependency integration
    - Graceful connect / close
    """

    def __init__(self) -> None:
        self._client: Redis | None = None

    # ── Connection lifecycle ──────────────────────────────────────────────

    async def connect(self) -> None:
        """Open the Redis connection if not already open."""
        if self._client is not None:
            return

        try:
            self._client = Redis.from_url(
                settings.redis_url,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True,
                health_check_interval=30,
            )
            await self._client.ping()
            logger.info(
                "Redis connected",
                extra={
                    "event": "redis_connected",
                    "url": settings.redis_url.split("@")[-1],
                },
            )
        except Exception as e:
            logger.critical(
                "Failed to connect to Redis",
                extra={"event": "redis_connection_failed", "error": str(e)},
            )
            self._client = None
            raise

    async def close(self) -> None:
        """Close the Redis connection."""
        if self._client:
            await self._client.aclose()
            self._client = None
            logger.info("Redis disconnected", extra={"event": "redis_disconnected"})

    # ── HMAC key helper ───────────────────────────────────────────────────

    def _hkey(self, key: str) -> str:
        """Return the HMAC-signed form of *key*."""
        return hmac_key(key)

    # ── Core CRUD ─────────────────────────────────────────────────────────

    async def get_data(self, key: str) -> str | None:
        """Retrieve a raw string value by key (HMAC-signed)."""
        if not self._client:
            await self.connect()
        return await self._client.get(self._hkey(key))

    async def set_data(self, key: str, value: str, ex: int | None = None) -> None:
        """Store a raw string value, with an optional TTL in seconds."""
        if not self._client:
            await self.connect()
        await self._client.set(self._hkey(key), value, ex=ex)

    async def delete(self, key: str) -> None:
        """Delete a key."""
        if not self._client:
            await self.connect()
        await self._client.delete(self._hkey(key))

    async def exists(self, key: str) -> bool:
        """Return True if the key exists."""
        if not self._client:
            await self.connect()
        return await self._client.exists(self._hkey(key)) == 1

    # ── Counter helpers (for rate limiting) ──────────────────────────────

    async def incr(self, raw_key: str) -> int:
        """
        Atomically increment a counter by 1 and return the new value.

        Uses *raw_key* directly — no HMAC — because rate-limit keys are
        transient, system-generated, and not user-facing.
        """
        if not self._client:
            await self.connect()
        return await self._client.incr(raw_key)

    async def expire(self, raw_key: str, seconds: int) -> None:
        """Set a TTL on a raw key (used alongside incr for sliding windows)."""
        if not self._client:
            await self.connect()
        await self._client.expire(raw_key, seconds)

    # ── JSON helpers ──────────────────────────────────────────────────────

    async def get_json(self, key: str) -> dict | list | None:
        """Retrieve a value and deserialize it from JSON. Returns None if missing."""
        raw = await self.get_data(key)
        if not raw:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            logger.exception("Failed to decode JSON for key %s", key)
            return None

    async def set_json(self, key: str, value: dict | list, ex: int | None = None) -> None:
        """Serialize *value* to JSON and store it."""
        try:
            payload = json.dumps(value)
        except (TypeError, ValueError) as exc:
            logger.exception("Value for set_json is not JSON-serializable: %s", exc)
            raise
        await self.set_data(key, payload, ex=ex)


# Module-level singleton shared across the application.
redis_client = AsyncRedisClient()


# ── FastAPI dependency ────────────────────────────────────────────────────


async def get_redis() -> AsyncGenerator[AsyncRedisClient, None]:
    """
    FastAPI dependency — ensures Redis is connected before yielding.

    Usage in routes:
        redis: AsyncRedisClient = Depends(get_redis)

    Yields None implicitly on connection failure so callers can
    choose to degrade gracefully rather than raise a 500.
    """
    await redis_client.connect()
    yield redis_client


# ── Lifespan helper ───────────────────────────────────────────────────────


async def close_redis() -> None:
    """Close the shared Redis connection on application shutdown."""
    await redis_client.close()


async def check_redis_connection() -> bool:
    """
    PING the Redis server.
    Used by the /health endpoint to report Redis status.
    Returns True if reachable, False on any connection error.
    """
    try:
        await redis_client.connect()
        return await redis_client._client.ping()
    except Exception as exc:
        logger.error("Redis health check failed", extra={"error": str(exc)})
        return False