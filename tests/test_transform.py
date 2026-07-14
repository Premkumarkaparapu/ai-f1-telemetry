"""Tests — Transform unit tests (offline, no network)."""

import pandas as pd
import pytest
from unittest.mock import MagicMock, patch

from data_pipeline.transform import _td_to_ms, _compute_fuel_corrected_time, _resample_telemetry


def test_td_to_ms_normal():
    td = pd.Timedelta("1 min 22.500 sec")
    result = _td_to_ms(td)
    assert result == 82_500


def test_td_to_ms_nat():
    result = _td_to_ms(pd.NaT)
    assert result is None


def test_fuel_correction_lap1():
    """Lap 1 correction should be 0 (no fuel burned yet)."""
    result = _compute_fuel_corrected_time(82_000, lap_number=1)
    assert result == 82_000


def test_fuel_correction_lap10():
    """Lap 10 should add correction for 9 laps of fuel burn."""
    from backend.app.core.config import FUEL_EFFECT_SEC_PER_LAP
    expected_correction = int(FUEL_EFFECT_SEC_PER_LAP * 9 * 1000)
    result = _compute_fuel_corrected_time(82_000, lap_number=10)
    assert result == 82_000 + expected_correction


def test_fuel_correction_none():
    """None input should return None."""
    result = _compute_fuel_corrected_time(None, lap_number=5)
    assert result is None


def test_resample_telemetry_reduces_rows():
    """Downsampling should produce fewer rows than the raw input."""
    import numpy as np

    n = 200
    raw = pd.DataFrame({
        "SessionTime": [pd.Timedelta(milliseconds=i * 55) for i in range(n)],  # ~18Hz
        "Distance": np.linspace(0, 5000, n),
        "Speed": np.random.uniform(100, 300, n),
        "RPM": np.random.randint(8000, 15000, n),
        "nGear": np.random.randint(1, 8, n),
        "Throttle": np.random.uniform(0, 100, n),
        "Brake": np.random.choice([True, False], n),
        "DRS": np.random.choice([True, False], n),
        "X": np.random.uniform(-1000, 1000, n),
        "Y": np.random.uniform(-1000, 1000, n),
        "Z": np.random.uniform(0, 50, n),
        "Status": ["OnTrack"] * n,
        "Source": ["car"] * n,
    })

    result = _resample_telemetry(raw)
    assert len(result) < n, "Resampled DataFrame should have fewer rows than raw input"
    assert "speed_kmh" in result.columns
    assert "throttle_pct" in result.columns
