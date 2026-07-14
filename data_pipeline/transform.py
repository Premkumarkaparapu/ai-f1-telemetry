"""
Data pipeline — Stage 2: Transform
Cleans raw FastF1 session data and downsamples telemetry to 5Hz.
Outputs Parquet files to data_pipeline/processed/ for downstream stages.

Usage:
    python -m data_pipeline.transform
"""

import pickle
from pathlib import Path
from typing import Optional

import pandas as pd
import fastf1

from backend.app.core.config import (
    RAW_DIR,
    PROCESSED_DIR,
    TARGET_SESSIONS,
    TELEMETRY_SAMPLE_RATE,
    FUEL_EFFECT_SEC_PER_LAP,
)
from backend.app.core.logging import get_logger, setup_logging

setup_logging("pipeline.log")
logger = get_logger(__name__)

SAMPLE_INTERVAL_MS = int(1000 / TELEMETRY_SAMPLE_RATE)  # e.g. 200ms for 5Hz


# ── Helpers ───────────────────────────────────────────────────────────────────

def _td_to_ms(td) -> Optional[int]:
    """Convert a pandas Timedelta (or NaT) to integer milliseconds."""
    if pd.isna(td):
        return None
    return int(td.total_seconds() * 1000)


def _compute_fuel_corrected_time(lap_time_ms: Optional[int], lap_number: int) -> Optional[int]:
    """Subtract the cumulative fuel burn benefit from a raw lap time.

    As fuel burns off, the car becomes lighter and naturally goes faster.
    Correcting for this isolates pure tyre/driver performance from fuel effects.
    The constant FUEL_EFFECT_SEC_PER_LAP ≈ 0.055s represents the
    approx improvement per lap from fuel burn-off (validated post-ingest).
    """
    if lap_time_ms is None:
        return None
    correction_ms = int(FUEL_EFFECT_SEC_PER_LAP * (lap_number - 1) * 1000)
    return lap_time_ms + correction_ms  # add correction to get fuel-equivalent time


# ── Laps ──────────────────────────────────────────────────────────────────────

def transform_laps(session: fastf1.core.Session) -> pd.DataFrame:
    """Clean and normalize the laps DataFrame for a session."""
    laps = session.laps.copy()

    # Drop laps with missing lap times (safety car bunching, red flags, etc.)
    laps = laps.dropna(subset=["LapTime"])

    # Convert timedelta columns to milliseconds
    laps["lap_time_ms"] = laps["LapTime"].apply(_td_to_ms)
    laps["sector1_ms"] = laps["Sector1Time"].apply(_td_to_ms)
    laps["sector2_ms"] = laps["Sector2Time"].apply(_td_to_ms)
    laps["sector3_ms"] = laps["Sector3Time"].apply(_td_to_ms)

    # Fuel-corrected lap time
    laps["fuel_corrected_lap_time_ms"] = laps.apply(
        lambda r: _compute_fuel_corrected_time(r["lap_time_ms"], r["LapNumber"]), axis=1
    )

    # Track status: "1" = green flag, "2" = yellow, "4" = SC, "5" = red, "6" = VSC
    laps["track_status"] = laps.get("TrackStatus", pd.Series(dtype=str)).fillna("1")

    # Is valid: exclude laps under yellow/SC/red flag conditions and deleted laps
    laps["is_valid"] = (
        (laps["track_status"] == "1")
        & (~laps.get("Deleted", pd.Series(False, index=laps.index)).fillna(False))
    )

    # Tyre compound — standardize to uppercase
    laps["compound"] = laps.get("Compound", pd.Series(dtype=str)).str.upper().fillna("UNKNOWN")

    # Pit lap flag
    laps["is_pit_lap"] = laps.get("PitInTime", pd.Series(dtype=object)).notna()

    # Stint number — FastF1 provides this directly
    laps["stint_number"] = laps.get("Stint", pd.Series(dtype=int)).fillna(0).astype(int)

    # Tyre life (laps on current set)
    laps["tyre_life"] = laps.get("TyreLife", pd.Series(dtype=int)).fillna(0).astype(int)

    keep_cols = [
        "DriverNumber", "Driver", "Team", "LapNumber",
        "lap_time_ms", "fuel_corrected_lap_time_ms",
        "sector1_ms", "sector2_ms", "sector3_ms",
        "compound", "tyre_life", "stint_number",
        "is_pit_lap", "is_valid", "track_status",
    ]
    existing = [c for c in keep_cols if c in laps.columns]
    return laps[existing].reset_index(drop=True)


# ── Telemetry ─────────────────────────────────────────────────────────────────

def _resample_telemetry(tel: pd.DataFrame) -> pd.DataFrame:
    """Downsample telemetry to TELEMETRY_SAMPLE_RATE Hz.

    FastF1 returns car data at ~18Hz and position data at ~10Hz.
    We merge them via get_telemetry() (which FastF1 does internally) then
    resample to SAMPLE_INTERVAL_MS to keep the database manageable.
    """
    if tel.empty:
        return tel

    # Ensure Time column is in milliseconds from lap start as int
    tel = tel.copy()
    tel["time_ms"] = tel["SessionTime"].apply(
        lambda t: int(t.total_seconds() * 1000) if pd.notna(t) else None
    )
    tel["distance_m"] = tel.get("Distance", pd.Series(dtype=float)).round(2)

    # Bin time into SAMPLE_INTERVAL_MS buckets and take mean per bucket
    tel["time_bin"] = (tel["time_ms"] // SAMPLE_INTERVAL_MS) * SAMPLE_INTERVAL_MS

    agg = {
        "distance_m": "last",
        "Speed": "mean",
        "RPM": "mean",
        "nGear": "last",
        "Throttle": "mean",
        "Brake": "last",
        "DRS": "last",
        "X": "last",
        "Y": "last",
        "Z": "last",
        "Status": "last",
        "Source": "last",
    }
    # Only aggregate columns that exist in this telemetry frame
    agg = {k: v for k, v in agg.items() if k in tel.columns}

    resampled = tel.groupby("time_bin").agg(agg).reset_index()
    resampled = resampled.rename(
        columns={"time_bin": "time_ms", "Speed": "speed_kmh", "nGear": "gear"})

    # Normalise bool columns
    for col in ["Brake", "DRS"]:
        if col in resampled.columns:
            resampled[col] = resampled[col].astype(bool)
            resampled = resampled.rename(columns={col: col.lower()})

    for col in ["Throttle"]:
        if col in resampled.columns:
            resampled = resampled.rename(columns={col: "throttle_pct"})

    return resampled


def transform_telemetry(
        session: fastf1.core.Session, driver_code: str, lap_number: int
) -> pd.DataFrame:
    """Return cleaned, downsampled telemetry for one lap of one driver."""
    try:
        lap = session.laps.pick_driver(driver_code).pick_lap(lap_number)
        tel = lap.get_telemetry()
        return _resample_telemetry(tel)
    except Exception as exc:
        logger.warning("Could not get telemetry for %s lap %d: %s", driver_code, lap_number, exc)
        return pd.DataFrame()


# ── Weather ───────────────────────────────────────────────────────────────────

def transform_weather(session: fastf1.core.Session) -> pd.DataFrame:
    """Clean and normalize the weather DataFrame."""
    weather = session.weather_data.copy()
    if weather.empty:
        return weather

    weather["time_ms"] = weather.get("Time", pd.Series(dtype=object)).apply(
        lambda t: int(t.total_seconds() * 1000) if pd.notna(t) else None
    )

    rename_map = {
        "AirTemp": "air_temp",
        "TrackTemp": "track_temp",
        "Humidity": "humidity",
        "Pressure": "pressure",
        "WindSpeed": "wind_speed",
        "WindDirection": "wind_dir",
        "Rainfall": "rainfall",
    }
    weather = weather.rename(columns={k: v for k, v in rename_map.items() if k in weather.columns})
    keep = ["time_ms"] + [v for v in rename_map.values() if v in weather.columns]
    return weather[[c for c in keep if c in weather.columns]].reset_index(drop=True)


# ── Orchestration ─────────────────────────────────────────────────────────────

def transform_session(year: int, event: str, session_type: str) -> dict[str, pd.DataFrame]:
    """Transform all components of one raw session. Returns DataFrames keyed by table name."""
    slug = f"{year}_{event.replace(' ', '_')}_{session_type}"
    raw_path = RAW_DIR / f"{slug}.pkl"

    if not raw_path.exists():
        raise FileNotFoundError(f"Raw session not found: {raw_path}. Run ingest first.")

    logger.info("Transforming session: %s", slug)
    with open(raw_path, "rb") as f:
        session = pickle.load(f)

    laps_df = transform_laps(session)
    weather_df = transform_weather(session)

    return {
        "session": session,         # raw FastF1 object still needed for per-lap telemetry
        "laps": laps_df,
        "weather": weather_df,
        "slug": slug,
    }


def save_processed(df: pd.DataFrame, name: str) -> Path:
    """Save a DataFrame to Parquet in the processed directory."""
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    path = PROCESSED_DIR / f"{name}.parquet"
    df.to_parquet(path, index=False)
    logger.info("Saved processed Parquet: %s (%d rows)", path, len(df))
    return path


def validate_fuel_correction(laps_df: pd.DataFrame) -> None:
    """Sanity check: for a long green-flag stint, fuel-corrected lap times
    should trend flat (or very slightly downward from tyre deg), not downward
    steeply like the raw lap times do.

    Logs a warning if the trend is still strongly downward, which would suggest
    the FUEL_EFFECT_SEC_PER_LAP constant needs adjustment.
    """
    # Find a stint with at least 10 valid laps to get a meaningful trend
    valid = laps_df[laps_df["is_valid"] & (laps_df["stint_number"] > 0)].copy()
    if valid.empty:
        return

    long_stints = (
        valid.groupby(["DriverNumber", "stint_number"])
        .filter(lambda g: len(g) >= 10)
    )
    if long_stints.empty:
        logger.warning("No long stints found for fuel correction validation.")
        return

    stint = long_stints.groupby(["DriverNumber", "stint_number"]).first().index[0]
    stint_laps = long_stints[
        (long_stints["DriverNumber"] == stint[0]) & (long_stints["stint_number"] == stint[1])
    ].sort_values("LapNumber") if "LapNumber" in long_stints.columns else long_stints.head(20)

    if len(stint_laps) < 3:
        return

    fc_times = stint_laps["fuel_corrected_lap_time_ms"].dropna().tolist()

    if len(fc_times) > 2:
        # Simple linear trend check — slope should be near 0 or slightly positive (deg)
        first_half = sum(fc_times[: len(fc_times) // 2]) / (len(fc_times) // 2)
        second_half = sum(fc_times[len(fc_times) // 2:]) / (len(fc_times) - len(fc_times) // 2)
        delta_ms = second_half - first_half

        logger.info(
            "Fuel correction validation: "
            "first-half avg=%.0fms, second-half avg=%.0fms, delta=%.0fms",
            first_half,
            second_half,
            delta_ms,
        )
        if delta_ms < -500:  # > 0.5s per half-stint improvement — constant may be too low
            logger.warning(
                "Fuel correction may be under-correcting. "
                "Consider increasing FUEL_EFFECT_SEC_PER_LAP (currently %.3f).",
                FUEL_EFFECT_SEC_PER_LAP,
            )
        else:
            logger.info("Fuel correction looks reasonable (delta < 500ms across stint).")


if __name__ == "__main__":
    setup_logging("pipeline.log")
    for year, event, session_type in TARGET_SESSIONS:
        result = transform_session(year, event, session_type)
        save_processed(result["laps"], f"{result['slug']}_laps")
        save_processed(result["weather"], f"{result['slug']}_weather")
        validate_fuel_correction(result["laps"])
