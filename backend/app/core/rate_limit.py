"""Distributed rate limiter for FastAPI.

Limits request frequency using Redis Lua scripts for atomicity,
falling back gracefully to local memory on connections offline.
"""

import time
import uuid
from threading import Lock

from fastapi import HTTPException, Request, status

from backend.app.core.logging import get_logger
from backend.app.core.redis import get_redis_client

logger = get_logger(__name__)

LUA_RATE_LIMITER = """
local key = KEYS[1]
local limit = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local request_id = ARGV[3]

-- Query Redis server time to prevent clock drift (returns {seconds, microseconds})
local time_resp = redis.call('TIME')
local current_time_ms = (tonumber(time_resp[1]) * 1000) + math.floor(tonumber(time_resp[2]) / 1000)

-- Remove expired requests
redis.call('ZREMRANGEBYSCORE', key, 0, current_time_ms - (window * 1000))

-- Check request counts
local request_count = redis.call('ZCARD', key)
if request_count < limit then
    redis.call('ZADD', key, current_time_ms, request_id)
    redis.call('EXPIRE', key, window)
    return {1, limit - request_count - 1, 0}
else
    -- Calculate retry_after from oldest record in the window
    local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
    if #oldest >= 2 then
        local oldest_time = tonumber(oldest[2])
        local retry_after = math.ceil((oldest_time + (window * 1000) - current_time_ms) / 1000)
        return {0, 0, math.max(1, retry_after)}
    else
        return {0, 0, window}
    end
end
"""


class RateLimiter:
    """Combines a Redis-backed Lua rate limiter with an in-memory sliding-window fallback."""

    def __init__(self, requests_limit: int = 10, window_seconds: int = 60):
        self.requests_limit = requests_limit
        self.window_seconds = window_seconds
        self.history: dict[str, list[float]] = {}
        self._lock = Lock()

    async def check_limit(self, ip: str) -> None:
        """Enforce rate limits via Redis Lua execution, falling back to local memory if offline."""
        redis_client = get_redis_client()
        if redis_client:
            try:
                key = f"rate_limit:{ip}"
                req_id = str(uuid.uuid4())

                # Exec script: KEYS=[key], ARGS=[limit, window, req_id]
                result = await redis_client.eval(
                    LUA_RATE_LIMITER,
                    1,
                    key,
                    str(self.requests_limit),
                    str(self.window_seconds),
                    req_id,
                )

                allowed, remaining, retry_after = result
                if not allowed:
                    raise HTTPException(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        detail="Too many requests. Please try again later.",
                        headers={"Retry-After": str(retry_after)},
                    )
                return
            except HTTPException:
                raise
            except Exception as exc:
                logger.warning(
                    "Redis rate limit eval failed, falling back to memory: %s", exc
                )

        # In-Memory Fallback
        now = time.time()
        with self._lock:
            if ip not in self.history:
                self.history[ip] = []

            # Filter old timestamps
            self.history[ip] = [
                t for t in self.history[ip] if now - t < self.window_seconds
            ]

            if len(self.history[ip]) >= self.requests_limit:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=(
                        f"Too many requests. Limit is {self.requests_limit} "
                        f"per {self.window_seconds}s."
                    ),
                    headers={"Retry-After": str(self.window_seconds // 2)},
                )

            self.history[ip].append(now)


import os  # noqa: E402

RATE_LIMIT_LIMIT = int(os.getenv("RATE_LIMIT_LIMIT", "100"))
RATE_LIMIT_WINDOW = int(os.getenv("RATE_LIMIT_WINDOW", "60"))
RATE_LIMIT_DISABLED = os.getenv("RATE_LIMIT_DISABLED", "false").lower() == "true"

# Global rate limiter instance
limiter = RateLimiter(requests_limit=RATE_LIMIT_LIMIT, window_seconds=RATE_LIMIT_WINDOW)


async def rate_limit(request: Request) -> None:
    """FastAPI dependency to enforce rate limiting on endpoints."""
    if RATE_LIMIT_DISABLED:
        return
    client_ip = request.headers.get("x-forwarded-for") or (
        request.client.host if request.client else "unknown"
    )
    await limiter.check_limit(client_ip)
