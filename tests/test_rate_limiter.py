"""Tests for the IP rate limiter."""

import pytest
from fastapi import HTTPException
from backend.app.core.rate_limit import RateLimiter


@pytest.mark.anyio
async def test_rate_limiter_under_limit():
    limiter = RateLimiter(requests_limit=5, window_seconds=60)
    # 5 requests should pass
    for _ in range(5):
        await limiter.check_limit("127.0.0.1")


@pytest.mark.anyio
async def test_rate_limiter_exceed_limit():
    limiter = RateLimiter(requests_limit=3, window_seconds=60)
    # 3 requests should pass
    await limiter.check_limit("192.168.1.1")
    await limiter.check_limit("192.168.1.1")
    await limiter.check_limit("192.168.1.1")
    
    # 4th request must raise 429 HTTPException
    with pytest.raises(HTTPException) as exc_info:
        await limiter.check_limit("192.168.1.1")
    assert exc_info.value.status_code == 429
    assert "Too many requests" in exc_info.value.detail


@pytest.mark.anyio
async def test_rate_limiter_ip_isolation():
    limiter = RateLimiter(requests_limit=2, window_seconds=60)
    # IP 1 hits limit
    await limiter.check_limit("1.1.1.1")
    await limiter.check_limit("1.1.1.1")
    with pytest.raises(HTTPException):
        await limiter.check_limit("1.1.1.1")
        
    # IP 2 should still pass since it has a separate bucket
    await limiter.check_limit("2.2.2.2")
    await limiter.check_limit("2.2.2.2")
