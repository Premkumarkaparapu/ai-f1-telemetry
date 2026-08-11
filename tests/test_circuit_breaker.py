"""Unit tests for the Gemini Circuit Breaker."""

import pytest
import time
from unittest.mock import AsyncMock, patch

from backend.app.core.circuit_breaker import CircuitBreaker


@pytest.mark.anyio
async def test_circuit_breaker_trip_and_cooldown():
    # max 2 failures, 1s cooldown
    breaker = CircuitBreaker(max_failures=2, cooldown_seconds=1)

    assert await breaker.get_state() == "CLOSED"

    # Record first failure
    await breaker.record_failure()
    assert await breaker.get_state() == "CLOSED"

    # Record second failure -> trips OPEN
    await breaker.record_failure()
    assert await breaker.get_state() == "OPEN"

    # Sleep to trigger cooldown transition to HALF-OPEN
    time.sleep(1.1)
    assert await breaker.get_state() == "HALF-OPEN"

    # Record success -> resets to CLOSED
    await breaker.record_success()
    assert await breaker.get_state() == "CLOSED"


@pytest.mark.anyio
@patch("backend.app.core.circuit_breaker.get_redis_client")
async def test_circuit_breaker_redis_lock(mock_get_redis):
    mock_redis = AsyncMock()
    mock_get_redis.return_value = mock_redis

    breaker = CircuitBreaker(max_failures=3, cooldown_seconds=30)

    # Set NX returns True (lock acquired)
    mock_redis.set.return_value = True
    assert await breaker.acquire_half_open_lock() is True

    # Set NX returns False (lock busy)
    mock_redis.set.return_value = False
    assert await breaker.acquire_half_open_lock() is False
