"""
Pydantic response/request schemas for all API v1 endpoints.

Response schemas are named with a `Out` suffix to distinguish them from ORM models.
All timestamps/durations are returned as milliseconds (integers) to keep the
frontend calculation simple and avoid timezone serialization issues.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


# ── Session ───────────────────────────────────────────────────────────────────

class SessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    session_id: int
    year: int
    event_name: str
    session_type: str
    track: Optional[str]
    country: Optional[str]
    total_laps: Optional[int]
    created_at: Optional[datetime]


# ── Driver ────────────────────────────────────────────────────────────────────

class DriverOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    driver_id: int
    session_id: int
    code: str
    full_name: Optional[str]
    team: Optional[str]
    team_color: Optional[str]


# ── Lap ───────────────────────────────────────────────────────────────────────

class LapOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    lap_id: int
    driver_id: int
    lap_number: int
    lap_time_ms: Optional[int]
    fuel_corrected_lap_time_ms: Optional[int]
    sector1_ms: Optional[int]
    sector2_ms: Optional[int]
    sector3_ms: Optional[int]
    compound: Optional[str]
    tyre_life: Optional[int]
    stint_number: Optional[int]
    is_pit_lap: bool
    is_valid: bool
    track_status: Optional[str]
    air_temp: Optional[float]
    track_temp: Optional[float]


# ── Telemetry ─────────────────────────────────────────────────────────────────

class TelemetryPointOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    lap_id: int
    time_ms: Optional[int]
    distance_m: Optional[float]
    speed_kmh: Optional[float]
    rpm: Optional[int]
    gear: Optional[int]
    throttle_pct: Optional[float]
    brake: Optional[bool]
    drs: Optional[bool]
    x: Optional[float]
    y: Optional[float]
    z: Optional[float]
    status: Optional[str]
    source: Optional[str]


class TelemetrySummaryOut(BaseModel):
    """Aggregated lap telemetry — used by frontend for summary cards.
    Returns a lightweight payload instead of streaming all 450+ data points.
    """
    lap_id: int
    lap_time_ms: Optional[int]
    sector1_ms: Optional[int]
    sector2_ms: Optional[int]
    sector3_ms: Optional[int]
    max_speed_kmh: Optional[float]
    avg_speed_kmh: Optional[float]
    avg_throttle_pct: Optional[float]
    avg_brake_pct: Optional[float]
    drs_usage_pct: Optional[float]
    compound: Optional[str]
    tyre_life: Optional[int]


class LapCompareOut(BaseModel):
    """Synchronized pair of telemetry traces for driver comparison."""
    lap_id_1: int
    lap_id_2: int
    driver_code_1: str
    driver_code_2: str
    telemetry_1: list[TelemetryPointOut]
    telemetry_2: list[TelemetryPointOut]


# ── Weather ───────────────────────────────────────────────────────────────────

class WeatherOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    weather_id: int
    session_id: int
    time_ms: Optional[int]
    air_temp: Optional[float]
    track_temp: Optional[float]
    humidity: Optional[float]
    pressure: Optional[float]
    wind_speed: Optional[float]
    wind_dir: Optional[int]
    rainfall: Optional[bool]


# ── Stint ─────────────────────────────────────────────────────────────────────

class StintOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    stint_id: int
    driver_id: int
    session_id: int
    stint_number: int
    compound: Optional[str]
    start_lap: Optional[int]
    end_lap: Optional[int]
    tyre_life_start: Optional[int]


# ── Pit Stop ──────────────────────────────────────────────────────────────────

class PitStopOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    pitstop_id: int
    driver_id: int
    session_id: int
    lap_number: int
    duration_ms: Optional[int]


# ── Predictions ───────────────────────────────────────────────────────────────

class PredictionRequest(BaseModel):
    """Request body for POST /api/v1/predict."""
    session_id: int
    driver_id: int
    prediction_type: str           # "lap_time" | "pit_window" | "race_simulation"
    pit_lap: Optional[int] = None  # for strategy simulations: proposed pit lap


class PredictionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    prediction_id: int
    session_id: int
    driver_id: int
    model_name: str
    model_version: str
    prediction_type: str
    predicted_value: Optional[float]
    actual_value: Optional[float]
    confidence: Optional[float]
    created_at: Optional[datetime]


# ── Strategy Simulation ───────────────────────────────────────────────────────

class StrategySimRequest(BaseModel):
    """Request body for POST /api/v1/predict/strategy."""
    session_id: int
    driver_id: int
    pit_laps: list[int]                # e.g. [28, 52]
    compounds: list[str]               # one per stint, len = len(pit_laps) + 1
    pit_time_loss_ms: int = 25_000     # pit lane time loss in ms


class StrategySimOut(BaseModel):
    session_id: int
    driver_id: int
    pit_laps: list[int]
    compounds: list[str]
    total_race_time_ms: float
    per_lap_times_ms: list[float]
    pit_stops: int
    vs_baseline_ms: Optional[float]    # delta vs no-strategy-change, None if not computable


class DegradationCurveOut(BaseModel):
    compound: str
    tyre_life_values: list[int]
    predicted_lap_times_ms: list[float]
    model_type: str                    # 'xgb' | 'ridge' | 'mean_fallback'


class PitWindowOut(BaseModel):
    session_id: int
    driver_id: int
    current_lap: int
    earliest_lap: int
    optimal_lap: int
    latest_lap: int
    reasoning: str


class DriverStandingOut(BaseModel):
    driver_id: int
    driver_code: str
    team: Optional[str]
    team_color: Optional[str]
    fastest_lap_ms: Optional[int]
    total_laps: int
    avg_lap_time_ms: Optional[float]
    pit_stop_count: int
    position: int
