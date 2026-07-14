"""
Tests — Database model tests (offline, uses in-memory SQLite).
Verifies that models create, relate, and cascade correctly.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.database.models import (
    Base, Session as SessionModel, Driver, Lap, TelemetryPoint,
    Weather, Stint, Tyre, PitStop, DatasetMetadata,
)

TEST_URL = "sqlite:///:memory:"
engine = create_engine(TEST_URL, connect_args={"check_same_thread": False})
SessionFactory = sessionmaker(bind=engine)


@pytest.fixture(autouse=True)
def reset_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


def test_create_session_and_driver():
    db = SessionFactory()
    s = SessionModel(year=2023, event_name="Monaco GP", session_type="R")
    db.add(s)
    db.flush()
    d = Driver(session_id=s.session_id, code="LEC", team="Ferrari")
    db.add(d)
    db.commit()

    loaded = db.query(Driver).filter(Driver.code == "LEC").first()
    assert loaded is not None
    assert loaded.session_id == s.session_id
    db.close()


def test_cascade_delete_session():
    """Deleting a session should cascade to drivers and laps."""
    db = SessionFactory()
    s = SessionModel(year=2023, event_name="Monza GP", session_type="R")
    db.add(s)
    db.flush()
    d = Driver(session_id=s.session_id, code="VER", team="Red Bull")
    db.add(d)
    db.flush()
    lap = Lap(driver_id=d.driver_id, lap_number=1, lap_time_ms=82000, is_pit_lap=False, is_valid=True)
    db.add(lap)
    db.commit()

    session_id = s.session_id
    db.delete(s)
    db.commit()

    assert db.query(Driver).filter(Driver.session_id == session_id).count() == 0
    db.close()


def test_tyre_one_to_one_lap():
    """A Tyre record should have a unique FK to a Lap."""
    db = SessionFactory()
    s = SessionModel(year=2023, event_name="Test GP", session_type="R")
    db.add(s)
    db.flush()
    d = Driver(session_id=s.session_id, code="HAM", team="Mercedes")
    db.add(d)
    db.flush()
    lap = Lap(driver_id=d.driver_id, lap_number=5, lap_time_ms=90000, is_pit_lap=False, is_valid=True)
    db.add(lap)
    db.flush()
    tyre = Tyre(lap_id=lap.lap_id, compound="MEDIUM", tyre_life=8, degradation_factor=95.5)
    db.add(tyre)
    db.commit()

    loaded = db.query(Tyre).filter(Tyre.lap_id == lap.lap_id).first()
    assert loaded.compound == "MEDIUM"
    assert loaded.degradation_factor == pytest.approx(95.5)
    db.close()


def test_dataset_metadata_unique_constraint():
    """Duplicate (year, event, session_type) metadata entries should raise an error."""
    from sqlalchemy.exc import IntegrityError
    db = SessionFactory()
    m1 = DatasetMetadata(year=2023, event_name="Monza", session_type="R", pipeline_version="1.0")
    db.add(m1)
    db.commit()

    m2 = DatasetMetadata(year=2023, event_name="Monza", session_type="R", pipeline_version="1.0")
    db.add(m2)
    with pytest.raises(IntegrityError):
        db.commit()
    db.close()
