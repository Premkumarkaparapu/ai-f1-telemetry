"""Unit tests for Unified security, JWKS caching, and RBAC controls."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import HTTPException, status

from backend.app.api.v1.security import (
    hash_api_key, AsyncJWKSClient, verify_request, require_scope, AuthenticatedUser
)


@pytest.mark.anyio
async def test_hash_api_key():
    key = "dev_secret_key"
    hashed = hash_api_key(key)
    # Validate SHA-256 output length
    assert len(hashed) == 64
    assert hashed == hash_api_key(key)


@pytest.mark.anyio
async def test_async_jwks_client_caching():
    jwks_client = AsyncJWKSClient("https://auth.f1-telemetry.com/jwks")
    http_mock = AsyncMock()
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "keys": [
            {
                "kty": "RSA",
                "kid": "key-1",
                "n": "u1W_O5y...dummy...nQ",
                "e": "AQAB"
            }
        ]
    }
    mock_response.raise_for_status = MagicMock()
    http_mock.get.return_value = mock_response
    
    # First fetch should call network client
    with patch("jwt.algorithms.RSAAlgorithm.from_jwk") as mock_from_jwk:
        mock_from_jwk.return_value = "public-key-object"
        
        pub_key = await jwks_client.get_signing_key("key-1", http_mock)
        assert pub_key == "public-key-object"
        http_mock.get.assert_called_once()
        
        # Second call within TTL should return cached key
        pub_key_cached = await jwks_client.get_signing_key("key-1", http_mock)
        assert pub_key_cached == "public-key-object"
        # Network call count remains 1
        assert http_mock.get.call_count == 1


@pytest.mark.anyio
async def test_verify_request_api_key():
    req = MagicMock()
    # Happy Path
    user = await verify_request(req, x_api_key="dev_secret_key")
    assert user.sub == "machine_client"
    assert "ai:ask" in user.scopes

    # Error Path
    with pytest.raises(HTTPException) as exc:
        await verify_request(req, x_api_key="wrong_key")
    assert exc.value.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.anyio
async def test_require_scope_dependency():
    user = AuthenticatedUser("test-sub", ["ai:ask"])
    
    # Authorized
    dep = require_scope("ai:ask")
    res = dep(user)
    assert res == user
    
    # Unauthorized
    dep_unauth = require_scope("strategy:run")
    with pytest.raises(HTTPException) as exc:
        dep_unauth(user)
    assert exc.value.status_code == status.HTTP_403_FORBIDDEN
