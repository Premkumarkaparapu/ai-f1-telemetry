"""
Tests — Ingest unit tests (offline).
Marks integration tests with @pytest.mark.integration so they only run manually.
"""

import pytest
from data_pipeline.ingest import save_raw, load_raw


class FakeSession:
    """Module-level picklable stand-in for a FastF1 Session object."""
    event = {"EventName": "Test GP"}


def test_save_and_load_raw(tmp_path, monkeypatch):
    """Test that save_raw and load_raw work symmetrically."""
    monkeypatch.setattr("data_pipeline.ingest.RAW_DIR", tmp_path)

    save_raw(FakeSession(), 2023, "Test GP", "R")
    loaded = load_raw(2023, "Test GP", "R")
    assert loaded is not None
    assert loaded.event["EventName"] == "Test GP"



def test_load_raw_missing_raises(tmp_path, monkeypatch):
    """load_raw should raise FileNotFoundError if not ingested."""
    monkeypatch.setattr("data_pipeline.ingest.RAW_DIR", tmp_path)
    with pytest.raises(FileNotFoundError):
        load_raw(2099, "Nonexistent GP", "R")


@pytest.mark.integration
def test_real_fastf1_ingest():
    """INTEGRATION TEST: Fetches real Monza 2023 Race session from FastF1 API.
    
    Requires network access and ~30-60s.
    Run manually:  pytest -m integration
    """
    from data_pipeline.ingest import fetch_session
    session = fetch_session(2023, "Italian Grand Prix", "R")
    assert session is not None
    assert len(session.laps) > 0
