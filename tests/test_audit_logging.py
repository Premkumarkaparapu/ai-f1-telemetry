"""Unit and integration tests for the Durable Audit Logging subsystem."""

import os
# Inject AUDIT_IP_SALT before any imports to satisfy ConfigurationError checks
os.environ["AUDIT_IP_SALT"] = "test_salt_value"

import pytest  # noqa: E402
from unittest.mock import patch  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from backend.app.api.v1.security import AuthenticatedUser  # noqa: E402
from backend.app.database.models import (  # noqa: E402
    Session as SessionModel, Driver, Lap, AuditEvent
)
from backend.app.main import app  # noqa: E402
from backend.app.services.audit_service import audit_service  # noqa: E402
from tests.conftest import TestingSessionLocal  # noqa: E402


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def setup_teardown_db():
    db = TestingSessionLocal()
    try:
        db.query(AuditEvent).delete()
        db.query(Lap).delete()
        db.query(Driver).delete()
        db.query(SessionModel).delete()
        db.commit()
    finally:
        db.close()
    yield


def test_ip_salted_hash():
    # Hashing verification
    ip = "192.168.1.100"
    expected_hash = (
        "7a56d7051113917c6b7d3cc55f5661f5551f95cf9768eff"
        "1e00399ffe59de6ce"
    )
    assert audit_service.hash_ip(ip) == expected_hash

    # None client host fallback
    assert len(audit_service.hash_ip(None)) == 64


def test_synchronous_write_failure_aborts(client):
    # AUTH_*, ADMIN_ACTION, STRATEGY_SIMULATION, AI_QUERY are synchronous.
    # If the database write fails, the middleware must abort with a 500 error.
    mock_user = AuthenticatedUser(sub="user", scopes=["strategy:run"])

    req_payload = {
        "session_id": 999,
        "driver_id": 999,
        "strategies": [],
        "seed": 42
    }

    # Simulate database error on AuditEvent writes
    with patch(
        "backend.app.services.audit_service.SessionLocal"
    ) as mock_session_local:
        mock_db = mock_session_local.return_value
        mock_db.add.side_effect = Exception("Database is down")

        with patch(
            "backend.app.api.v1.predictions.require_scope"
        ) as mock_scope:
            mock_scope.return_value = lambda user: mock_user

            response = client.post(
                "/api/v1/predict/strategy/compare",
                json=req_payload,
                headers={"Authorization": "Bearer mock_token"}
            )
            # Must abort the operation with a 500 error
            assert response.status_code == 500
            assert "Action aborted" in response.json()["detail"]


def test_batched_write_failure_continues(client):
    # MODEL_PREDICTION and TELEMETRY_ACCESS are batched.
    # If a database write fails, the request must continue to succeed.
    mock_user = AuthenticatedUser(sub="user", scopes=["strategy:run"])

    # Simulate database error on bulk save during flush
    with patch(
        "backend.app.services.audit_service.SessionLocal"
    ) as mock_session_local:
        mock_db = mock_session_local.return_value
        mock_db.bulk_save_objects.side_effect = Exception("Database is down")

        with patch(
            "backend.app.api.v1.predictions.require_scope"
        ) as mock_scope:
            mock_scope.return_value = lambda user: mock_user

            # Trigger a model prediction endpoint
            response = client.get(
                "/api/v1/predict/degradation/SOFT?max_life=10",
                headers={"Authorization": "Bearer mock_token"}
            )
            # The request must succeed despite the audit database write error
            assert response.status_code == 200

            # Force audit service queue check and background flush
            audit_service.flush()
            # The application remains alive and healthy


def test_request_id_and_audit_log_propagation(client):
    # Verify X-Request-ID propagation to both response headers and audit row.
    import jwt
    mock_jwt = jwt.encode({"sub": "user_123"}, "secret", algorithm="HS256")
    mock_user = AuthenticatedUser(sub="user_123", scopes=["strategy:run"])

    with patch(
        "backend.app.api.v1.predictions.require_scope"
    ) as mock_scope:
        mock_scope.return_value = lambda user: mock_user

        custom_request_id = "11111111-2222-3333-4444-555555555555"
        response = client.get(
            "/api/v1/predict/degradation/SOFT?max_life=10",
            headers={
                "Authorization": f"Bearer {mock_jwt}",
                "X-Request-ID": custom_request_id
            }
        )

        assert response.status_code == 200
        assert response.headers.get("X-Request-ID") == custom_request_id

        # Trigger batch queue flush
        audit_service.flush()

        # Query DB to check if audit event was stored correctly
        db = TestingSessionLocal()
        try:
            event = db.query(AuditEvent).filter(
                AuditEvent.request_id == custom_request_id
            ).first()
            assert event is not None
            assert event.event_type == "MODEL_PREDICTION"
            assert event.user_id == "user_123"
            assert event.status == "SUCCESS"
        finally:
            db.close()
