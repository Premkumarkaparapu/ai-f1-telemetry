"""Unit tests for /health/ready degraded routing logic."""

import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient

from backend.app.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_health_ready_all_ok(client):
    # Mock DB execute success, Redis ping success, and Storage success
    with patch("sqlalchemy.orm.Session.execute") as mock_db_exec:
        mock_db_exec.return_value = None
        with patch("backend.app.core.redis.redis_manager.client") as mock_redis_client:
            mock_redis_client.ping = AsyncMock()
            with patch("pathlib.Path.touch") as mock_touch:
                mock_touch.return_value = None
                with patch("pathlib.Path.unlink") as mock_unlink:
                    mock_unlink.return_value = None

                    resp = client.get("/health/ready")
                    assert resp.status_code == 200
                    data = resp.json()
                    assert data["status"] == "ready"
                    assert data["checks"]["database"] == "ok"
                    assert data["checks"]["redis"] == "ok"
                    assert data["checks"]["storage"] == "ok"


def test_health_ready_db_down(client):
    # Mock DB execute raising error, Redis ping success, and Storage success
    with patch("sqlalchemy.orm.Session.execute") as mock_db_exec:
        mock_db_exec.side_effect = Exception("DB Connection Refused")
        with patch("backend.app.core.redis.redis_manager.client") as mock_redis_client:
            mock_redis_client.ping = AsyncMock()
            with patch("pathlib.Path.touch") as mock_touch:
                mock_touch.return_value = None
                with patch("pathlib.Path.unlink") as mock_unlink:
                    mock_unlink.return_value = None

                    resp = client.get("/health/ready")
                    assert resp.status_code == 503
                    data = resp.json()
                    assert data["status"] == "unhealthy"
                    assert "failed" in data["checks"]["database"]
                    assert data["checks"]["redis"] == "ok"


def test_health_ready_redis_down(client):
    # Mock DB execute success, Redis ping raising error, and Storage success
    with patch("sqlalchemy.orm.Session.execute") as mock_db_exec:
        mock_db_exec.return_value = None
        with patch("backend.app.core.redis.redis_manager.client") as mock_redis_client:
            # Side effect on ping to simulate connection timeout/outage
            mock_redis_client.ping = AsyncMock(side_effect=Exception("Redis connection timed out"))
            with patch("pathlib.Path.touch") as mock_touch:
                mock_touch.return_value = None
                with patch("pathlib.Path.unlink") as mock_unlink:
                    mock_unlink.return_value = None

                    resp = client.get("/health/ready")
                    assert resp.status_code == 200  # remains online in degraded state!
                    data = resp.json()
                    assert data["status"] == "degraded"
                    assert data["checks"]["database"] == "ok"
                    assert "degraded" in data["checks"]["redis"]


def test_health_ready_storage_down(client):
    # Mock DB execute success, Redis ping success, and Storage touch raising error
    with patch("sqlalchemy.orm.Session.execute") as mock_db_exec:
        mock_db_exec.return_value = None
        with patch("backend.app.core.redis.redis_manager.client") as mock_redis_client:
            mock_redis_client.ping = AsyncMock()
            with patch("pathlib.Path.touch") as mock_touch:
                mock_touch.side_effect = IOError("Permission denied / disk full")

                resp = client.get("/health/ready")
                assert resp.status_code == 503
                data = resp.json()
                assert data["status"] == "unhealthy"
                assert data["checks"]["database"] == "ok"
                assert "failed" in data["checks"]["storage"]
