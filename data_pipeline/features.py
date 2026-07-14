"""
Data pipeline — Stage 3: Feature Engineering
Computes ML-ready features from cleaned laps and telemetry DataFrames.
These columns are added to the processed Parquet files before DB load.

Features computed:
  - tyre_degradation_factor: rate of lap time increase per lap of tyre life
  - sector_delta_*: driver sector vs session best
  - lap_consistency: std deviation within a stint (stability metric)
  - avg_throttle_pct: from telemetry (stored on laps summary)
  - brake_pct: % of lap distance braking
  - drs_pct: % of lap distance with DRS open
  - max_speed_kmh: highest recorded speed on the lap
  - avg_speed_kmh: mean speed across the lap

Usage:
    python -m data_pipeline.features
"""

import numpy as np
import pandas as pd

from backend.app.core.constants import MIN_STINT_LAPS_FOR_DEGRADATION, STINT_EXCLUSION_LAPS
from backend.app.core.logging import get_logger, setup_logging

setup_logging("pipeline.log")
logger = get_logger(__name__)


# ── Tyre Degradation ──────────────────────────────────────────────────────────

def compute_tyre_degradation(laps_df: pd.DataFrame) -> pd.DataFrame:
    """Compute per-stint degradation factor: Δlap_time / Δtyre_life.

    A positive value means each additional lap on the tyre costs X ms.
    Only computed for stints with enough clean laps to fit a trend.
    """
    result = laps_df.copy()
    result["tyre_degradation_factor"] = np.nan

    groups = laps_df.groupby(["DriverNumber", "stint_number"])

    for (driver, stint), group in groups:
        valid = group[group["is_valid"]].copy()
        # Exclude in/out laps (first and last lap of the stint)
        if len(valid) <= STINT_EXCLUSION_LAPS * 2:
            continue
        valid = valid.iloc[STINT_EXCLUSION_LAPS:-STINT_EXCLUSION_LAPS]
        if len(valid) < MIN_STINT_LAPS_FOR_DEGRADATION:
            continue

        x = valid["tyre_life"].values
        y = valid["fuel_corrected_lap_time_ms"].values
        mask = ~np.isnan(y.astype(float))
        if mask.sum() < 2:
            continue

        # Linear fit: slope = ms lost per tyre lap
        try:
            slope, _ = np.polyfit(x[mask], y[mask], 1)
            result.loc[group.index, "tyre_degradation_factor"] = round(slope, 3)
        except Exception:
            pass

    return result


# ── Sector Deltas ─────────────────────────────────────────────────────────────

def compute_sector_deltas(laps_df: pd.DataFrame) -> pd.DataFrame:
    """Compute each lap's sector time delta vs. the session best for that sector."""
    result = laps_df.copy()

    for col in ["sector1_ms", "sector2_ms", "sector3_ms"]:
        if col not in result.columns:
            continue
        session_best = result[col].min()
        result[f"delta_{col}"] = result[col] - session_best

    return result


# ── Lap Consistency ───────────────────────────────────────────────────────────

def compute_lap_consistency(laps_df: pd.DataFrame) -> pd.DataFrame:
    """Compute lap-time standard deviation within a stint.

    A lower value indicates the driver is more consistent on that compound.
    Useful for compound/driver classification models.
    """
    result = laps_df.copy()
    result["stint_lap_time_std_ms"] = np.nan

    groups = laps_df.groupby(["DriverNumber", "stint_number"])
    for (driver, stint), group in groups:
        valid = group[group["is_valid"] & group["fuel_corrected_lap_time_ms"].notna()]
        if len(valid) < 3:
            continue
        std = valid["fuel_corrected_lap_time_ms"].std()
        result.loc[group.index, "stint_lap_time_std_ms"] = round(std, 1)

    return result


# ── Telemetry Aggregates ──────────────────────────────────────────────────────

def compute_telemetry_features(tel_df: pd.DataFrame) -> dict:
    """Compute summary features from a single lap's telemetry DataFrame.

    Returns a dict that can be merged onto the laps DataFrame as new columns.
    """
    if tel_df.empty:
        return {}

    features = {}
    if "speed_kmh" in tel_df.columns:
        features["max_speed_kmh"] = round(tel_df["speed_kmh"].max(), 1)
        features["avg_speed_kmh"] = round(tel_df["speed_kmh"].mean(), 1)

    if "throttle_pct" in tel_df.columns:
        features["avg_throttle_pct"] = round(tel_df["throttle_pct"].mean(), 2)

    if "brake" in tel_df.columns:
        brake_arr = tel_df["brake"].astype(bool)
        features["brake_pct"] = round(brake_arr.mean() * 100, 2)

    if "drs" in tel_df.columns:
        drs_arr = tel_df["drs"].astype(bool)
        features["drs_pct"] = round(drs_arr.mean() * 100, 2)

    return features


# ── Master Feature Runner ─────────────────────────────────────────────────────

def engineer_features(laps_df: pd.DataFrame) -> pd.DataFrame:
    """Run all lap-level feature computations in sequence."""
    logger.info("Engineering features for %d laps...", len(laps_df))
    laps_df = compute_tyre_degradation(laps_df)
    laps_df = compute_sector_deltas(laps_df)
    laps_df = compute_lap_consistency(laps_df)
    logger.info("Feature engineering complete.")
    return laps_df
