"""Atomic lease-based concurrency semaphore for Gemini.

Enforces a limit on concurrent active Gemini requests across instances
using Redis Hash leases, falling back to asyncio.Semaphore if offline.
"""

import asyncio

from backend.app.core.logging import get_logger
from backend.app.core.redis import get_redis_client

logger = get_logger(__name__)

LUA_ACQUIRE_SEMAPHORE = """
local key = KEYS[1]
local limit = tonumber(ARGV[1])
local lease_ttl_ms = tonumber(ARGV[2])
local request_id = ARGV[3]

-- Query Redis time
local time_resp = redis.call('TIME')
local current_time_ms = (tonumber(time_resp[1]) * 1000) + math.floor(tonumber(time_resp[2]) / 1000)

-- 1. Scan and delete expired leases
local leases = redis.call('HGETALL', key)
local active_count = 0
for i = 1, #leases, 2 do
    local rid = leases[i]
    local expire_time = tonumber(leases[i+1])
    if expire_time <= current_time_ms then
        redis.call('HDEL', key, rid)
    else
        active_count = active_count + 1
    end
end

-- 2. Check limits and acquire
if active_count < limit then
    local expiry = current_time_ms + lease_ttl_ms
    redis.call('HSET', key, request_id, expiry)
    redis.call('PEXPIRE', key, lease_ttl_ms * 2)
    return 1 -- SUCCESS
else
    return 0 -- FAILURE
end
"""

LUA_RELEASE_SEMAPHORE = """
local key = KEYS[1]
local request_id = ARGV[1]
return redis.call('HDEL', key, request_id)
"""


class ConcurrencySemaphore:
    """Manages lease-based concurrency limits globally via Redis, falling back locally."""

    def __init__(self, limit: int = 10, lease_ttl_seconds: int = 30):
        self.limit = limit
        self.lease_ttl_ms = lease_ttl_seconds * 1000
        self._local_semaphore = asyncio.Semaphore(limit)

    async def acquire(self, request_id: str) -> bool:
        """Acquire a slot. Returns True if slot acquired, False if rejected."""
        redis_client = get_redis_client()
        if redis_client:
            try:
                key = "gemini_semaphore"
                # Exec acquire script
                result = await redis_client.eval(
                    LUA_ACQUIRE_SEMAPHORE,
                    1,
                    key,
                    str(self.limit),
                    str(self.lease_ttl_ms),
                    request_id,
                )
                return bool(result)
            except Exception as exc:
                logger.warning(
                    "Redis acquire semaphore failed, falling back to local memory: %s",
                    exc,
                )

        # Local Fallback (non-blocking try_acquire style)
        if self._local_semaphore.locked():
            return False

        try:
            # Attempt immediate acquire without blocking forever
            await asyncio.wait_for(self._local_semaphore.acquire(), timeout=0.1)
            return True
        except asyncio.TimeoutError:
            return False

    async def release(self, request_id: str) -> None:
        """Release the acquired slot."""
        redis_client = get_redis_client()
        if redis_client:
            try:
                key = "gemini_semaphore"
                await redis_client.eval(LUA_RELEASE_SEMAPHORE, 1, key, request_id)
                return
            except Exception as exc:
                logger.warning("Redis release semaphore failed: %s", exc)

        # Local Fallback release
        try:
            self._local_semaphore.release()
        except ValueError:
            pass

    def acquire_sync(self, request_id: str) -> bool:
        """Synchronous wrapper to acquire a lease slot from synchronous worker threads."""
        try:
            from asgiref.sync import async_to_sync
            return async_to_sync(self.acquire)(request_id)
        except Exception:
            # If asgiref is not installed or errors, run inside a new temporary loop
            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(self.acquire(request_id))
            finally:
                loop.close()

    def release_sync(self, request_id: str) -> None:
        """Synchronous wrapper to release a lease slot from synchronous worker threads."""
        try:
            from asgiref.sync import async_to_sync
            async_to_sync(self.release)(request_id)
        except Exception:
            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(self.release(request_id))
            finally:
                loop.close()


# Global concurrency semaphore
gemini_semaphore = ConcurrencySemaphore(limit=10, lease_ttl_seconds=30)
