"""Redis connection manager.

Establishes and exposes a shared async Redis client pool for rate limiting,
semaphores, and caching, with graceful fallback to local memory if disconnected.
"""

import os
import redis.asyncio as redis

from backend.app.core.logging import get_logger

logger = get_logger(__name__)

REDIS_URL = os.getenv("REDIS_URL", "")


class RedisManager:
    """Manages async Redis connection pool state and connection testing."""

    def __init__(self):
        self.client = None

    async def connect(self):
        """Connect to Redis if URL is configured, else remain in offline fallback mode."""
        if not REDIS_URL:
            logger.info(
                "REDIS_URL environment variable is empty. "
                "Redis disabled; using in-memory fallbacks."
            )
            return

        try:
            # Create async redis client pool
            self.client = redis.from_url(
                REDIS_URL,
                decode_responses=True,
                socket_timeout=3.0,
                socket_connect_timeout=3.0,
            )
            # Send ping command to verify connection
            await self.client.ping()
            logger.info("Connected to Redis server successfully at %s", REDIS_URL)
        except Exception as exc:
            logger.warning(
                "Failed to connect to Redis at %s: %s. Swapping to in-memory fallbacks.",
                REDIS_URL,
                exc,
            )
            self.client = None

    async def close(self):
        """Close connection pool cleanly during lifespan shutdown."""
        if self.client:
            await self.client.close()
            logger.info("Closed Redis connection pool.")
            self.client = None


redis_manager = RedisManager()


def get_redis_client():
    """Retrieve active Redis client if online, else return None."""
    return redis_manager.client if redis_manager.client else None
