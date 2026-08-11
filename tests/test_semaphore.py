"""Unit tests for ConcurrencySemaphore."""

import pytest
from unittest.mock import AsyncMock, patch

from backend.app.core.semaphore import ConcurrencySemaphore


@pytest.mark.anyio
async def test_local_semaphore_limits():
    # Set limit to 2
    sem = ConcurrencySemaphore(limit=2)

    assert await sem.acquire("req1") is True
    assert await sem.acquire("req2") is True

    # 3rd request should fail since limit is 2
    assert await sem.acquire("req3") is False

    # Release one
    await sem.release("req1")

    # Now req3 should succeed
    assert await sem.acquire("req3") is True


@pytest.mark.anyio
@patch("backend.app.core.semaphore.get_redis_client")
async def test_redis_semaphore_acquire(mock_get_redis):
    # Setup mock Redis client
    mock_redis = AsyncMock()
    mock_get_redis.return_value = mock_redis

    # Return 1 (success) from Lua script eval
    mock_redis.eval.return_value = 1

    sem = ConcurrencySemaphore(limit=5)
    acquired = await sem.acquire("req-redis-123")

    assert acquired is True
    mock_redis.eval.assert_called_once()
