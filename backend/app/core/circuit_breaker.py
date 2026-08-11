"""Redis-synchronized circuit breaker for Gemini.

Protects external API dependencies from request storms when degraded,
with distributed locks to restrict probes in HALF-OPEN state.
"""

import asyncio
import time

from backend.app.core.logging import get_logger
from backend.app.core.redis import get_redis_client

logger = get_logger(__name__)


class CircuitOpenException(Exception):
    """Raised when the circuit breaker is OPEN, preventing outbound API calls."""
    pass


class CircuitBreaker:
    """Distributed and local circuit breaker state machine for Gemini."""

    def __init__(self, max_failures: int = 5, cooldown_seconds: int = 60):
        self.max_failures = max_failures
        self.cooldown_seconds = cooldown_seconds

        # Local fallback parameters if Redis is offline
        self._state = "CLOSED"
        self._failures = 0
        self._last_state_change = 0

    async def get_state(self) -> str:
        """Query circuit state from Redis or local memory, triggering cooldown changes."""
        redis_client = get_redis_client()
        current_time = time.time()

        if not redis_client:
            time_diff = current_time - self._last_state_change
            if self._state == "OPEN" and time_diff > self.cooldown_seconds:
                self._state = "HALF-OPEN"
                self._last_state_change = current_time
                logger.info("Local circuit transitioned to HALF-OPEN.")
            return self._state

        try:
            state = await redis_client.get("gemini_circuit_state") or "CLOSED"
            last_change = float(await redis_client.get("gemini_circuit_last_change") or 0)

            if state == "OPEN" and (current_time - last_change) > self.cooldown_seconds:
                # Transition to HALF-OPEN in Redis
                state = "HALF-OPEN"
                await redis_client.set("gemini_circuit_state", "HALF-OPEN")
                await redis_client.set("gemini_circuit_last_change", str(current_time))
                logger.info("Redis circuit transitioned globally to HALF-OPEN.")
            return state
        except Exception as exc:
            logger.warning("Failed to query Redis circuit state: %s", exc)
            return self._state

    async def acquire_half_open_lock(self) -> bool:
        """Acquire lock to allow a single probe request in HALF-OPEN state."""
        redis_client = get_redis_client()
        if not redis_client:
            return True  # Fallback to local memory (process-isolated test)

        try:
            # Set key with TTL of 15 seconds so lock is released if request hangs
            acquired = await redis_client.set(
                "gemini_circuit_half_open_lock", "locked", ex=15, nx=True
            )
            return bool(acquired)
        except Exception as exc:
            logger.warning("Failed to acquire HALF-OPEN lock in Redis: %s", exc)
            return True

    async def record_success(self) -> None:
        """Reset failure counts and CLOSE the circuit."""
        redis_client = get_redis_client()
        if not redis_client:
            self._state = "CLOSED"
            self._failures = 0
            return

        try:
            await redis_client.set("gemini_circuit_state", "CLOSED")
            await redis_client.set("gemini_circuit_failures", "0")
            await redis_client.delete("gemini_circuit_half_open_lock")
            logger.info("Gemini circuit closed successfully.")
        except Exception as exc:
            logger.warning("Failed to record circuit success in Redis: %s", exc)

    async def record_failure(self) -> None:
        """Increment failure count and trip the circuit OPEN if limit exceeded."""
        redis_client = get_redis_client()
        current_time = time.time()

        if not redis_client:
            self._failures += 1
            if self._failures >= self.max_failures:
                self._state = "OPEN"
                self._last_state_change = current_time
                logger.error(
                    "Gemini circuit tripped OPEN locally after %d failures",
                    self._failures,
                )
            return

        try:
            failures = await redis_client.incr("gemini_circuit_failures")
            if failures >= self.max_failures:
                await redis_client.set("gemini_circuit_state", "OPEN")
                await redis_client.set("gemini_circuit_last_change", str(current_time))
                await redis_client.delete("gemini_circuit_half_open_lock")
                logger.error("Gemini circuit tripped OPEN globally after %d failures", failures)
        except Exception as exc:
            logger.warning("Failed to record circuit failure in Redis: %s", exc)

    # ── Synchronous wrappers for worker threads ──────────────────────────────

    def get_state_sync(self) -> str:
        """Synchronous wrapper to get circuit state."""
        try:
            from asgiref.sync import async_to_sync
            return async_to_sync(self.get_state)()
        except Exception:
            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(self.get_state())
            finally:
                loop.close()

    def acquire_half_open_lock_sync(self) -> bool:
        """Synchronous wrapper to acquire HALF-OPEN probe lock."""
        try:
            from asgiref.sync import async_to_sync
            return async_to_sync(self.acquire_half_open_lock)()
        except Exception:
            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(self.acquire_half_open_lock())
            finally:
                loop.close()

    def record_success_sync(self) -> None:
        """Synchronous wrapper to record successful call."""
        try:
            from asgiref.sync import async_to_sync
            async_to_sync(self.record_success)()
        except Exception:
            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(self.record_success())
            finally:
                loop.close()

    def record_failure_sync(self) -> None:
        """Synchronous wrapper to record failed call."""
        try:
            from asgiref.sync import async_to_sync
            async_to_sync(self.record_failure)()
        except Exception:
            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(self.record_failure())
            finally:
                loop.close()


# Global circuit breaker instance
gemini_circuit = CircuitBreaker(max_failures=5, cooldown_seconds=60)
