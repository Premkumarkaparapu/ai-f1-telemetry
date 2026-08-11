"""Tests for Milestone 7 — Production Deployment & Scalability."""

import pytest
import os
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch

from backend.app.main import app
from backend.app.services.storage_service import (
    get_storage_provider, LocalStorageProvider, S3StorageProvider
)
from backend.app.core.request_context import get_request_id

client = TestClient(app)


# ── Storage Abstraction Tests ──────────────────────────────────────────────────

def test_storage_provider_factory():
    # Default is Local
    with patch.dict(os.environ, {}, clear=True):
        provider = get_storage_provider()
        assert isinstance(provider, LocalStorageProvider)

    # Set S3
    with patch.dict(os.environ, {"STORAGE_PROVIDER": "s3"}):
        provider = get_storage_provider()
        assert isinstance(provider, S3StorageProvider)
        assert provider.bucket == "f1-telemetry-pickles"


# ── Health Probes Tests ────────────────────────────────────────────────────────

def test_health_live_endpoint():
    res = client.get("/health/live")
    assert res.status_code == 200
    assert res.json() == {"status": "alive"}


def test_health_ready_endpoint_success():
    res = client.get("/health/ready")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ready"
    assert data["checks"]["database"] == "ok"
    assert data["checks"]["storage"] == "ok"
    assert data["checks"]["ai_provider"] == "configured"


# ── Request ID Tracing Middleware Tests ────────────────────────────────────────

def test_request_id_middleware_generates_id():
    res = client.get("/health/live")
    assert res.status_code == 200
    # Middleware should return X-Request-ID header
    assert "X-Request-ID" in res.headers
    assert len(res.headers["X-Request-ID"]) > 10


def test_request_id_middleware_propagates_incoming_id():
    incoming_id = "test-session-trace-id-12345"
    res = client.get("/health/live", headers={"X-Request-ID": incoming_id})
    assert res.status_code == 200
    assert res.headers["X-Request-ID"] == incoming_id
