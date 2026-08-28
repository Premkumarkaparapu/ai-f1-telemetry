"""Unit tests for 10Hz WebSocket telemetry streaming."""

from unittest.mock import patch, AsyncMock

import pytest
from fastapi.testclient import TestClient

from backend.app.api.v1.security import AuthenticatedUser
from backend.app.database.models import (
    Session as SessionModel, Driver, Lap, TelemetryPoint
)
from backend.app.main import app
from tests.conftest import TestingSessionLocal


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def setup_teardown_db():
    # Clear DB before each test
    db = TestingSessionLocal()
    try:
        db.query(TelemetryPoint).delete()
        db.query(Lap).delete()
        db.query(Driver).delete()
        db.query(SessionModel).delete()
        db.commit()
    finally:
        db.close()
    yield


def _seed_db():
    db = TestingSessionLocal()
    try:
        session = SessionModel(
            year=2023, event_name="Monaco Grand Prix", session_type="R",
            track="Monaco", country="Monaco"
        )
        db.add(session)
        db.flush()

        driver = Driver(
            session_id=session.session_id, code="HAM",
            full_name="Lewis Hamilton", team="Mercedes"
        )
        db.add(driver)
        db.flush()

        lap = Lap(
            driver_id=driver.driver_id,
            lap_number=5,
            lap_time_ms=75_000,
            compound="MEDIUM",
            tyre_life=4
        )
        db.add(lap)
        db.flush()

        # Seed some telemetry points that are slightly uneven
        pts = [
            TelemetryPoint(
                lap_id=lap.lap_id, session_id=session.session_id,
                time_ms=10, distance_m=5.0, speed_kmh=150.0, rpm=10000,
                gear=4, throttle_pct=80.0, brake=False, drs=False,
                x=1.0, y=2.0, z=0.5
            ),
            TelemetryPoint(
                lap_id=lap.lap_id, session_id=session.session_id,
                time_ms=190, distance_m=10.0, speed_kmh=160.0, rpm=10200,
                gear=4, throttle_pct=85.0, brake=False, drs=False,
                x=2.0, y=4.0, z=0.5
            ),
            TelemetryPoint(
                lap_id=lap.lap_id, session_id=session.session_id,
                time_ms=310, distance_m=15.0, speed_kmh=170.0, rpm=10400,
                gear=5, throttle_pct=90.0, brake=False, drs=False,
                x=3.0, y=6.0, z=0.6
            ),
        ]
        for p in pts:
            db.add(p)
        db.commit()
        return session.session_id, lap.lap_id
    finally:
        db.close()


def test_websocket_stream_no_token(client):
    # Reject handshake if token is missing
    with pytest.raises(Exception):
        with client.websocket_connect(
            "/api/v1/telemetry/stream?lap_id=1"
        ):
            pass


def test_websocket_stream_invalid_token(client):
    with patch(
        "backend.app.api.v1.telemetry.verify_token_ws",
        new_callable=AsyncMock,
        side_effect=ValueError("Invalid token")
    ):
        with pytest.raises(Exception):
            with client.websocket_connect(
                "/api/v1/telemetry/stream?lap_id=1&token=invalid"
            ):
                pass


def test_websocket_stream_insufficient_scope(client):
    mock_user = AuthenticatedUser(sub="user", scopes=["other:scope"])
    with patch(
        "backend.app.api.v1.telemetry.verify_token_ws",
        new_callable=AsyncMock,
        return_value=mock_user
    ):
        with pytest.raises(Exception):
            with client.websocket_connect(
                "/api/v1/telemetry/stream?lap_id=1&token=valid"
            ):
                pass


def test_websocket_stream_mutually_exclusive(client):
    mock_user = AuthenticatedUser(sub="user", scopes=["telemetry:read"])
    with patch(
        "backend.app.api.v1.telemetry.verify_token_ws",
        new_callable=AsyncMock,
        return_value=mock_user
    ):
        with pytest.raises(Exception):
            with client.websocket_connect(
                "/api/v1/telemetry/stream?lap_id=1&session_id=1&token=valid"
            ):
                pass
        with pytest.raises(Exception):
            with client.websocket_connect(
                "/api/v1/telemetry/stream?token=valid"
            ):
                pass


def test_websocket_stream_invalid_ids(client):
    mock_user = AuthenticatedUser(sub="user", scopes=["telemetry:read"])
    with patch(
        "backend.app.api.v1.telemetry.verify_token_ws",
        new_callable=AsyncMock,
        return_value=mock_user
    ):
        with pytest.raises(Exception):
            with client.websocket_connect(
                "/api/v1/telemetry/stream?lap_id=9999&token=valid"
            ):
                pass
        with pytest.raises(Exception):
            with client.websocket_connect(
                "/api/v1/telemetry/stream?session_id=9999&token=valid"
            ):
                pass


def test_websocket_stream_lap_success(client):
    _, lap_id = _seed_db()
    mock_user = AuthenticatedUser(sub="user", scopes=["telemetry:read"])
    with patch(
        "backend.app.api.v1.telemetry.verify_token_ws",
        new_callable=AsyncMock,
        return_value=mock_user
    ):
        with client.websocket_connect(
            f"/api/v1/telemetry/stream?lap_id={lap_id}&token=valid"
        ) as ws:
            # First resampled point at time_ms = 100
            pt1 = ws.receive_json()
            assert pt1["time_ms"] == 100
            assert pt1["speed"] == 155.0  # (150 + 160) / 2
            assert pt1["throttle"] == 82.5  # (80 + 85) / 2
            assert pt1["gear"] == 4
            assert pt1["rpm"] == 10100
            assert pt1["position"]["x"] == 1.5
            assert pt1["position"]["y"] == 3.0

            # Second resampled point at time_ms = 200
            pt2 = ws.receive_json()
            assert pt2["time_ms"] == 200
            assert pt2["gear"] == 4

            # Third resampled point at time_ms = 300
            pt3 = ws.receive_json()
            assert pt3["time_ms"] == 300

            # Final message
            final_msg = ws.receive_json()
            assert final_msg["type"] == "stream_end"
            assert final_msg["lap_id"] == lap_id
            assert final_msg["samples_sent"] == 3


def test_websocket_stream_session_success(client):
    session_id, _ = _seed_db()
    mock_user = AuthenticatedUser(sub="user", scopes=["telemetry:read"])
    with patch(
        "backend.app.api.v1.telemetry.verify_token_ws",
        new_callable=AsyncMock,
        return_value=mock_user
    ):
        with client.websocket_connect(
            f"/api/v1/telemetry/stream?session_id={session_id}&token=valid"
        ) as ws:
            ws.receive_json()
            ws.receive_json()
            ws.receive_json()
            final_msg = ws.receive_json()
            assert final_msg["type"] == "stream_end"
            assert final_msg["samples_sent"] == 3


def test_websocket_stream_db_failure_in_loop(client):
    _, lap_id = _seed_db()
    mock_user = AuthenticatedUser(sub="user", scopes=["telemetry:read"])
    with patch(
        "backend.app.api.v1.telemetry.verify_token_ws",
        new_callable=AsyncMock,
        return_value=mock_user
    ):
        with patch(
            "backend.app.repositories.telemetry_repository"
            ".TelemetryRepository.get_by_lap_time_ordered",
            side_effect=Exception("Database error")
        ):
            with client.websocket_connect(
                f"/api/v1/telemetry/stream?lap_id={lap_id}&token=valid"
            ) as ws:
                with pytest.raises(Exception):
                    ws.receive_json()
