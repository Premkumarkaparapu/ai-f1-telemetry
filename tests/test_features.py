"""Tests — Feature engineering unit tests (offline, pure pandas, no DB)."""

import pandas as pd
import numpy as np
import pytest

from data_pipeline.features import (
    compute_tyre_degradation,
    compute_sector_deltas,
    compute_lap_consistency,
    compute_telemetry_features,
)


def _make_laps(driver="VER", n_laps=12, compound="SOFT", deg_ms_per_lap=80):
    """Helper: generate a synthetic stint with predictable degradation."""
    records = []
    for i in range(n_laps):
        lap_time = 82_000 + i * deg_ms_per_lap
        records.append({
            "DriverNumber": "33",
            "Driver": driver,
            "LapNumber": i + 1,
            "lap_time_ms": lap_time,
            "fuel_corrected_lap_time_ms": lap_time + 500,  # just offset for test
            "sector1_ms": 27_000 + i * 20,
            "sector2_ms": 28_000 + i * 30,
            "sector3_ms": 27_000 + i * 30,
            "compound": compound,
            "tyre_life": i + 1,
            "stint_number": 1,
            "is_valid": True,
            "is_pit_lap": False,
        })
    return pd.DataFrame(records)


def test_tyre_degradation_slope_sign():
    """Degradation factor should be positive (lap time increases with tyre age)."""
    laps = _make_laps(n_laps=12, deg_ms_per_lap=80)
    result = compute_tyre_degradation(laps)
    factors = result["tyre_degradation_factor"].dropna()
    assert len(factors) > 0, "Expected at least one degradation factor computed"
    assert (factors > 0).all(), f"Expected positive degradation factors, got: {factors.tolist()}"


def test_tyre_degradation_skips_short_stints():
    """Stints with fewer laps than MIN_STINT_LAPS_FOR_DEGRADATION should be NaN."""
    laps = _make_laps(n_laps=2)
    result = compute_tyre_degradation(laps)
    assert result["tyre_degradation_factor"].isna().all()


def test_sector_deltas_baseline():
    """Session-best sector should have a delta of 0."""
    laps = _make_laps(n_laps=5)
    result = compute_sector_deltas(laps)
    assert result["delta_sector1_ms"].min() == 0
    assert result["delta_sector2_ms"].min() == 0


def test_lap_consistency_std():
    """Lap time std dev should be non-zero for a degrading stint."""
    laps = _make_laps(n_laps=10)
    result = compute_lap_consistency(laps)
    stds = result["stint_lap_time_std_ms"].dropna()
    assert len(stds) > 0
    assert (stds > 0).all()


def test_telemetry_features_happy_path():
    """compute_telemetry_features returns correct aggregates."""
    tel = pd.DataFrame({
        "speed_kmh": [100.0, 200.0, 300.0],
        "throttle_pct": [50.0, 80.0, 100.0],
        "brake": [True, False, False],
        "drs": [False, True, True],
    })
    result = compute_telemetry_features(tel)
    assert result["max_speed_kmh"] == 300.0
    assert result["avg_speed_kmh"] == pytest.approx(200.0, abs=1)
    assert result["brake_pct"] == pytest.approx(33.33, abs=0.1)
    assert result["drs_pct"] == pytest.approx(66.67, abs=0.1)


def test_telemetry_features_empty():
    """compute_telemetry_features returns empty dict for empty DataFrame."""
    result = compute_telemetry_features(pd.DataFrame())
    assert result == {}
