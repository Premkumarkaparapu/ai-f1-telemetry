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


# ── Integration Tests ─────────────────────────────────────────────────────────
import time  # noqa: E402
from cryptography.hazmat.primitives.asymmetric import rsa  # noqa: E402
from cryptography.hazmat.primitives import serialization  # noqa: E402
import jwt  # noqa: E402
from backend.app.main import app  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from backend.app.api.v1.security import jwks_client  # noqa: E402


class TestJWTIntegration:
    """End-to-End integration tests for JWT/JWKS signature checks and RBAC."""

    @classmethod
    def setup_class(cls):
        # Generate private key for signing tokens in tests
        cls.private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048
        )
        cls.pem_private = cls.private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )

        # Export public key as JWK to simulate JWKS server response
        import json
        public_key = cls.private_key.public_key()
        jwk_data = jwt.algorithms.RSAAlgorithm.to_jwk(public_key)
        if isinstance(jwk_data, str):
            cls.jwk = json.loads(jwk_data)
        else:
            cls.jwk = jwk_data
        cls.jwk["kid"] = "test-kid-1"
        cls.jwk["alg"] = "RS256"
        cls.jwk["kty"] = "RSA"

        # Generate a separate invalid key for signature mismatch tests
        cls.bad_private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        cls.pem_bad_private = cls.bad_private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )

        cls.client = TestClient(app)
        import httpx
        app.state.http_client = httpx.AsyncClient()

    def setup_method(self):
        # Temporarily clear verify_request dependency override so security is enforced
        self.original_override = app.dependency_overrides.get(verify_request)
        if verify_request in app.dependency_overrides:
            del app.dependency_overrides[verify_request]

    def teardown_method(self):
        # Restore the original override
        if self.original_override:
            app.dependency_overrides[verify_request] = self.original_override

    def _create_token(self, permissions, exp_offset=3600, kid="test-kid-1", key_pem=None):
        payload = {
            "sub": "user-123",
            "iss": "https://auth.f1-telemetry.com/",
            "aud": "https://api.f1-telemetry.com",
            "exp": int(time.time()) + exp_offset,
            "permissions": permissions,
        }
        headers = {"kid": kid}
        pk = key_pem or self.pem_private
        return jwt.encode(payload, pk, algorithm="RS256", headers=headers)

    @pytest.mark.anyio
    async def test_endpoint_telemetry_scope_happy_path(self):
        token = self._create_token(["telemetry:read"])
        headers = {"Authorization": f"Bearer {token}"}

        # Mock JWKS client keys cache to return our public key
        mock_keys = {"test-kid-1": jwt.algorithms.RSAAlgorithm.from_jwk(self.jwk)}
        with patch.object(jwks_client, "_keys", mock_keys):
            with patch.object(jwks_client, "_last_fetched", time.time()):
                resp = self.client.get("/api/v1/sessions/", headers=headers)
                assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_endpoint_insufficient_scope_returns_403(self):
        token = self._create_token(["strategy:run"])  # missing telemetry:read
        headers = {"Authorization": f"Bearer {token}"}

        mock_keys = {"test-kid-1": jwt.algorithms.RSAAlgorithm.from_jwk(self.jwk)}
        with patch.object(jwks_client, "_keys", mock_keys):
            with patch.object(jwks_client, "_last_fetched", time.time()):
                resp = self.client.get("/api/v1/sessions/", headers=headers)
                assert resp.status_code == 403
                assert resp.json()["detail"] == "Access forbidden: insufficient permissions"

    @pytest.mark.anyio
    async def test_expired_token_returns_401(self):
        token = self._create_token(["telemetry:read"], exp_offset=-60)
        headers = {"Authorization": f"Bearer {token}"}

        mock_keys = {"test-kid-1": jwt.algorithms.RSAAlgorithm.from_jwk(self.jwk)}
        with patch.object(jwks_client, "_keys", mock_keys):
            with patch.object(jwks_client, "_last_fetched", time.time()):
                resp = self.client.get("/api/v1/sessions/", headers=headers)
                assert resp.status_code == 401
                assert resp.json()["detail"] == "Invalid authentication credentials"

    @pytest.mark.anyio
    async def test_invalid_signature_returns_401(self):
        token = self._create_token(["telemetry:read"], key_pem=self.pem_bad_private)
        headers = {"Authorization": f"Bearer {token}"}

        mock_keys = {"test-kid-1": jwt.algorithms.RSAAlgorithm.from_jwk(self.jwk)}
        with patch.object(jwks_client, "_keys", mock_keys):
            with patch.object(jwks_client, "_last_fetched", time.time()):
                resp = self.client.get("/api/v1/sessions/", headers=headers)
                assert resp.status_code == 401
                assert resp.json()["detail"] == "Invalid authentication credentials"

    @pytest.mark.anyio
    async def test_unauthenticated_request_returns_401(self):
        resp = self.client.get("/api/v1/sessions/")
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Invalid authentication credentials"

    @pytest.mark.anyio
    async def test_m2m_api_key_auth_allowed(self):
        headers = {"X-API-Key": "dev_secret_key"}
        resp = self.client.get("/api/v1/sessions/", headers=headers)
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_m2m_invalid_api_key_returns_401(self):
        headers = {"X-API-Key": "wrong_secret_key"}
        resp = self.client.get("/api/v1/sessions/", headers=headers)
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Invalid authentication credentials"

    @pytest.mark.anyio
    async def test_viewer_predict_returns_403(self):
        token = self._create_token(["telemetry:read"])  # missing strategy:run
        headers = {"Authorization": f"Bearer {token}"}
        mock_keys = {"test-kid-1": jwt.algorithms.RSAAlgorithm.from_jwk(self.jwk)}
        with patch.object(jwks_client, "_keys", mock_keys):
            with patch.object(jwks_client, "_last_fetched", time.time()):
                resp = self.client.post("/api/v1/predict/", json={"session_id": 1, "driver_id": 1, "prediction_type": "lap_time"}, headers=headers)
                assert resp.status_code == 403

    @pytest.mark.anyio
    async def test_viewer_ai_ask_returns_403(self):
        token = self._create_token(["telemetry:read"])  # missing ai:ask
        headers = {"Authorization": f"Bearer {token}"}
        mock_keys = {"test-kid-1": jwt.algorithms.RSAAlgorithm.from_jwk(self.jwk)}
        with patch.object(jwks_client, "_keys", mock_keys):
            with patch.object(jwks_client, "_last_fetched", time.time()):
                resp = self.client.post("/api/v1/ai/ask", json={"prompt": "F1 strategy info"}, headers=headers)
                assert resp.status_code == 403

    @pytest.mark.anyio
    async def test_analyst_predict_is_not_403(self):
        token = self._create_token(["telemetry:read", "strategy:run"])
        headers = {"Authorization": f"Bearer {token}"}
        mock_keys = {"test-kid-1": jwt.algorithms.RSAAlgorithm.from_jwk(self.jwk)}
        with patch.object(jwks_client, "_keys", mock_keys):
            with patch.object(jwks_client, "_last_fetched", time.time()):
                resp = self.client.post("/api/v1/predict/", json={"session_id": 1, "driver_id": 1, "prediction_type": "lap_time"}, headers=headers)
                assert resp.status_code != 403

    @pytest.mark.anyio
    async def test_analyst_ai_ask_is_not_403(self):
        token = self._create_token(["telemetry:read", "ai:ask"])
        headers = {"Authorization": f"Bearer {token}"}
        mock_keys = {"test-kid-1": jwt.algorithms.RSAAlgorithm.from_jwk(self.jwk)}
        with patch.object(jwks_client, "_keys", mock_keys):
            with patch.object(jwks_client, "_last_fetched", time.time()):
                resp = self.client.post("/api/v1/ai/ask", json={"prompt": "F1 strategy info"}, headers=headers)
                assert resp.status_code != 403

