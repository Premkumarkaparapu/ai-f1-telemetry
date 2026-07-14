"""
Tests — API endpoint tests (offline, no network, no FastF1 calls).
These run on every CI push.

We use FastAPI's TestClient + an in-memory SQLite DB seeded with minimal fixtures.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.database.models import Base, Session as SessionModel, Driver, Lap, TelemetryPoint
from backend.app.database.db import get_db
from backend.app.main import app

# ── In-memory test DB ─────────────────────────────────────────────────────────

from sqlalchemy.pool import StaticPool

# ── In-memory test DB — must use StaticPool so all connections share the same DB ──
# SQLite :memory: creates a fresh empty DB per connection by default.
# StaticPool forces all sessions to reuse one connection, so seed data is visible
# to the FastAPI TestClient (which runs in a worker thread).

TEST_DATABASE_URL = "sqlite://"
engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create schema once — StaticPool keeps the same connection/DB for the whole session.
Base.metadata.create_all(bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


def _clear_db():
    """Delete all rows in insertion-reverse order (respect FK constraints)."""
    db = TestingSessionLocal()
    try:
        db.query(TelemetryPoint).delete()
        db.query(Lap).delete()
        db.query(Driver).delete()
        db.query(SessionModel).delete()
        db.commit()
    finally:
        db.close()


def _seed_db():
    """Insert minimal fixture data for each test."""
    db = TestingSessionLocal()
    try:
        # Session
        session = SessionModel(
            year=2023, event_name="Italian Grand Prix", session_type="R",
            track="Monza", country="Italy"
        )
        db.add(session)
        db.flush()

        # Driver
        driver = Driver(session_id=session.session_id, code="VER",
                        full_name="Max Verstappen", team="Red Bull")
        db.add(driver)
        db.flush()

        # Lap
        lap = Lap(
            driver_id=driver.driver_id,
            lap_number=10,
            lap_time_ms=82_500,
            fuel_corrected_lap_time_ms=83_000,
            sector1_ms=27_000,
            sector2_ms=28_000,
            sector3_ms=27_500,
            compound="SOFT",
            tyre_life=5,
            stint_number=1,
            is_pit_lap=False,
            is_valid=True,
        )
        db.add(lap)
        db.flush()

        # Telemetry
        tp = TelemetryPoint(
            lap_id=lap.lap_id,
            session_id=session.session_id,
            time_ms=1000,
            distance_m=100.0,
            speed_kmh=250.0,
            throttle_pct=98.0,
            brake=False,
            drs=True,
            gear=8,
        )
        db.add(tp)
        db.commit()
    finally:
        db.close()


@pytest.fixture(autouse=True)
def setup_db():
    """Clear and re-seed the shared in-memory DB before each test."""
    _clear_db()
    _seed_db()
    yield
    # no teardown needed — next test's setup_db will clear it


client = TestClient(app)


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_list_sessions():
    resp = client.get("/api/v1/sessions/")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["event_name"] == "Italian Grand Prix"
    assert data[0]["year"] == 2023


def test_get_session():
    resp = client.get("/api/v1/sessions/1")
    assert resp.status_code == 200
    assert resp.json()["track"] == "Monza"


def test_get_session_not_found():
    resp = client.get("/api/v1/sessions/9999")
    assert resp.status_code == 404


def test_list_drivers():
    resp = client.get("/api/v1/drivers/?session_id=1")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["code"] == "VER"


def test_get_driver_by_code():
    resp = client.get("/api/v1/drivers/VER?session_id=1")
    assert resp.status_code == 200
    assert resp.json()["team"] == "Red Bull"


def test_get_driver_not_found():
    resp = client.get("/api/v1/drivers/ZZZ?session_id=1")
    assert resp.status_code == 404


def test_list_laps():
    resp = client.get("/api/v1/laps/?driver_id=1")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["lap_time_ms"] == 82_500


def test_get_lap():
    resp = client.get("/api/v1/laps/1")
    assert resp.status_code == 200
    assert resp.json()["compound"] == "SOFT"


def test_get_telemetry():
    resp = client.get("/api/v1/telemetry/1")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["speed_kmh"] == 250.0


def test_get_telemetry_summary():
    resp = client.get("/api/v1/telemetry/1/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert data["lap_id"] == 1
    assert data["max_speed_kmh"] == 250.0
    assert data["compound"] == "SOFT"
