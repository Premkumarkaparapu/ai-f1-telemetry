"""Unit tests for CORS origin restrictions and preflight headers."""

from fastapi.testclient import TestClient

from backend.app.main import app


def test_cors_allowed_origin():
    client = TestClient(app)
    # Perform preflight OPTIONS request
    headers = {
        "Origin": "http://localhost:5173",
        "Access-Control-Request-Method": "GET",
        "Access-Control-Request-Headers": "authorization,x-api-key",
    }
    resp = client.options("/api/v1/sessions/", headers=headers)
    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") == "http://localhost:5173"
    assert resp.headers.get("access-control-allow-credentials") == "true"
    assert "GET" in resp.headers.get("access-control-allow-methods", "")


def test_cors_disallowed_origin():
    client = TestClient(app)
    # Perform actual GET request with unauthorized origin
    headers = {
        "Origin": "http://malicious.com",
    }
    resp = client.get("/api/v1/sessions/", headers=headers)
    # Starlette CORS middleware blocks cross-origin requests by omitting CORS response headers
    assert resp.headers.get("access-control-allow-origin") is None
