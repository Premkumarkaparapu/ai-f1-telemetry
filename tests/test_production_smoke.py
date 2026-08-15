import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.core.ai_config import API_KEY


@pytest.fixture
def client():
    return TestClient(app)


def test_production_health_ready(client):
    """Verify that health ready endpoint indicates ready or degraded."""
    resp = client.get("/health/ready")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] in ("ready", "degraded")
    assert data["checks"]["database"] == "ok"


def test_production_unauthorized_metrics(client):
    """Verify metrics endpoint rejects public access and allows private loopback."""
    # Public IP proxy header -> should be blocked with 403
    resp = client.get("/metrics", headers={"X-Forwarded-For": "8.8.8.8"})
    assert resp.status_code == 403

    # Local connection -> should succeed with 200
    resp = client.get("/metrics", headers={"X-Forwarded-For": "127.0.0.1"})
    assert resp.status_code == 200
    assert "# HELP" in resp.text


def test_production_m2m_auth_endpoints(client):
    """Verify protected endpoints require X-API-Key and succeed when provided."""
    from backend.app.api.v1.security import verify_request
    original_overrides = app.dependency_overrides.copy()
    if verify_request in app.dependency_overrides:
        del app.dependency_overrides[verify_request]

    try:
        headers = {"X-API-Key": "invalid_key"}
        resp = client.get("/api/v1/sessions/", headers=headers)
        assert resp.status_code == 401

        headers = {"X-API-Key": API_KEY or "dev_secret_key"}
        resp = client.get("/api/v1/sessions/", headers=headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)
    finally:
        app.dependency_overrides = original_overrides


def test_production_ai_ask_smoke(client):
    """Verify AI race engineer question routing, tool simulation, and answer formatting."""
    headers = {
        "X-API-Key": API_KEY,
        "Content-Type": "application/json",
    }
    payload = {
        "question": "What is the pace of Verstappen on mediums?",
        "session_id": 1,
        "driver_code": "VER"
    }

    # Set mock provider for AI
    with patch_ai_provider():
        resp = client.post("/api/v1/ai/ask", json=payload, headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "answer" in data
        assert "evidence" in data
        assert "tools_used" in data
        assert len(data["tools_used"]) > 0


class patch_ai_provider:
    """Helper to mock AI service provider to run offline smoke tests cleanly."""
    def __enter__(self):
        from unittest.mock import patch
        from backend.app.services.ai_service import MockProvider
        self._patcher = patch(
            "backend.app.services.ai_race_engineer.get_ai_service",
            return_value=MockProvider()
        )
        self._patcher.start()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._patcher.stop()
