"""Unit tests for Failure Injection, Outage Recovery, and Resilience Fallbacks."""

from unittest.mock import MagicMock, patch
import pytest
from fastapi import HTTPException

from backend.app.core.redis import redis_manager, get_redis_client
from backend.app.core.rate_limit import limiter
from backend.app.core.circuit_breaker import gemini_circuit, CircuitOpenException
from backend.app.services.ai_service import GeminiProvider


@pytest.mark.anyio
async def test_redis_outage_limiter_fallback():
    """Verify that when Redis is offline, rate limiter falls back gracefully to local memory."""
    # 1. Force offline status
    original_client = redis_manager.client
    redis_manager.client = None

    assert get_redis_client() is None

    # 2. Check limiter allows requests via in-memory fallback
    # Should not raise exception under limit
    try:
        await limiter.check_limit("test-ip-outage")
        allowed = True
    except HTTPException:
        allowed = False
    assert allowed is True

    # 3. Simulate recovery
    mock_redis = MagicMock()
    # Mock eval command for rate limiter Lua script execution simulation
    # Lua script returns [allowed (0/1), remaining, retry_after]
    mock_redis.eval = MagicMock(return_value=[1, 4, 0])

    redis_manager.client = mock_redis

    # 4. Check limiter recovers and queries Redis
    try:
        await limiter.check_limit("test-ip-outage")
        allowed_recovered = True
    except HTTPException:
        allowed_recovered = False
    assert allowed_recovered is True
    assert mock_redis.eval.called

    # Restore original redis client
    redis_manager.client = original_client


def test_gemini_outage_circuit_breaker():
    """Verify Gemini circuit breaker trips on failures and returns fallbacks without crashing."""
    # Reset circuit breaker state in Redis/local
    original_redis_client = redis_manager.client
    redis_manager.client = None  # Force local fallback breaker

    gemini_circuit.state = "CLOSED"
    gemini_circuit._failures = 0
    gemini_circuit._state = "CLOSED"

    # Initialize Gemini provider with mocked client
    with patch("google.genai.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        # Setup generate_content to raise error
        mock_client.models.generate_content.side_effect = Exception("Gemini server error 500")

        provider = GeminiProvider()

        # Execute multiple attempts to trip circuit breaker
        # Config threshold is 5 failures (default)
        for _ in range(6):
            try:
                provider.complete(system_prompt="sys", user_prompt="usr")
            except Exception:
                pass

        # Verify circuit breaker trips to OPEN
        assert gemini_circuit.get_state_sync() == "OPEN"

        # Verify that subsequent calls fast-fail immediately with CircuitOpenException
        with pytest.raises(CircuitOpenException):
            provider.complete(system_prompt="sys", user_prompt="usr")

        # Cleanup circuit state
        gemini_circuit._state = "CLOSED"
        gemini_circuit._failures = 0
        redis_manager.client = original_redis_client
