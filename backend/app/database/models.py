"""
SQLAlchemy ORM models — the single source of truth for the database schema.

Both data_pipeline/ and the FastAPI backend import from here.
Never define column names anywhere else to prevent schema drift.

Integer primary keys are used throughout (not UUIDs) — optimal for SQLite and
straightforward to migrate to Postgres sequences later.
"""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


# ── Dataset Metadata ──────────────────────────────────────────────────────────


class DatasetMetadata(Base):
    """Tracks which sessions have been imported, enabling idempotent re-runs."""

    __tablename__ = "dataset_metadata"

    id = Column(Integer, primary_key=True, autoincrement=True)
    year = Column(Integer, nullable=False)
    event_name = Column(String(100), nullable=False)
    session_type = Column(String(10), nullable=False)
    import_date = Column(DateTime, default=func.now(), nullable=False)
    fastf1_version = Column(String(20))
    pipeline_version = Column(String(20), default="1.0.0")
    row_count_laps = Column(Integer)
    row_count_telemetry = Column(Integer)

    __table_args__ = (
        Index("ix_metadata_session", "year", "event_name", "session_type", unique=True),
    )


# ── Sessions ──────────────────────────────────────────────────────────────────


class Session(Base):
    """One F1 session (Race, Qualifying, Practice) at a specific event."""

    __tablename__ = "sessions"

    session_id = Column(Integer, primary_key=True, autoincrement=True)
    year = Column(Integer, nullable=False)
    event_name = Column(String(100), nullable=False)
    session_type = Column(String(10), nullable=False)
    track = Column(String(100))
    country = Column(String(100))
    circuit_key = Column(Integer)           # FastF1 internal circuit identifier
    total_laps = Column(Integer)
    created_at = Column(DateTime, default=func.now())

    # Relationships
    drivers = relationship("Driver", back_populates="session", cascade="all, delete-orphan")
    weather_points = relationship("Weather", back_populates="session", cascade="all, delete-orphan")
    stints = relationship("Stint", back_populates="session", cascade="all, delete-orphan")
    pitstops = relationship("PitStop", back_populates="session", cascade="all, delete-orphan")
    predictions = relationship("Prediction", back_populates="session", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_sessions_year_event", "year", "event_name", "session_type"),
    )


# ── Drivers ───────────────────────────────────────────────────────────────────


class Driver(Base):
    """A driver as they appeared in a specific session."""

    __tablename__ = "drivers"

    driver_id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("sessions.session_id", ondelete="CASCADE"), nullable=False)
    code = Column(String(3), nullable=False)        # e.g. VER, HAM, LEC
    full_name = Column(String(100))
    team = Column(String(100))
    team_color = Column(String(7))                  # hex colour, e.g. #1E5BC6

    # Relationships
    session = relationship("Session", back_populates="drivers")
    laps = relationship("Lap", back_populates="driver", cascade="all, delete-orphan")
    stints = relationship("Stint", back_populates="driver", cascade="all, delete-orphan")
    pitstops = relationship("PitStop", back_populates="driver", cascade="all, delete-orphan")
    predictions = relationship("Prediction", back_populates="driver", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_drivers_session", "session_id"),
        Index("ix_drivers_code", "code"),
    )


# ── Laps ──────────────────────────────────────────────────────────────────────


class Lap(Base):
    """One lap completed by a driver.

    lap_time_ms and sector times are stored as integers (milliseconds) to avoid
    floating-point rounding issues.  Fuel-corrected lap time is stored alongside
    so the backend never recomputes it at query time.
    """

    __tablename__ = "laps"

    lap_id = Column(Integer, primary_key=True, autoincrement=True)
    driver_id = Column(Integer, ForeignKey("drivers.driver_id", ondelete="CASCADE"), nullable=False)
    lap_number = Column(Integer, nullable=False)
    lap_time_ms = Column(Integer)                   # raw lap time
    fuel_corrected_lap_time_ms = Column(Integer)    # fuel-adjusted lap time
    sector1_ms = Column(Integer)
    sector2_ms = Column(Integer)
    sector3_ms = Column(Integer)
    compound = Column(String(20))                   # SOFT / MEDIUM / HARD / etc.
    tyre_life = Column(Integer)                     # laps on this set so far
    stint_number = Column(Integer)
    is_pit_lap = Column(Boolean, default=False)
    is_valid = Column(Boolean, default=True)        # False if track limits, VSC, etc.
    track_status = Column(String(10))               # e.g. "1" = Green flag
    air_temp = Column(Float)                        # snapshot from weather at lap start
    track_temp = Column(Float)

    # Relationships
    driver = relationship("Driver", back_populates="laps")
    telemetry_points = relationship("TelemetryPoint", back_populates="lap", cascade="all, delete-orphan")
    tyre = relationship("Tyre", back_populates="lap", uselist=False, cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_laps_driver", "driver_id"),
        Index("ix_laps_driver_lap", "driver_id", "lap_number"),
    )


# ── Telemetry ─────────────────────────────────────────────────────────────────


class TelemetryPoint(Base):
    """High-frequency (5Hz after downsampling) car sensor readings for a lap.

    Coordinates X, Y, Z give the car's 3D position on track — useful for
    racing line analysis, overtaking detection, and corner-speed heatmaps.

    BigInteger PK is used here because this is by far the largest table:
    ~5 samples/s × 90s/lap × 70 laps × 20 drivers × 3 races ≈ 1.9 M rows.
    """

    __tablename__ = "telemetry"

    id = Column(Integer, primary_key=True, autoincrement=True)
    lap_id = Column(Integer, ForeignKey("laps.lap_id", ondelete="CASCADE"), nullable=False)
    session_id = Column(Integer, ForeignKey("sessions.session_id", ondelete="CASCADE"), nullable=False)

    # Core channels
    time_ms = Column(Integer)           # milliseconds from lap start
    distance_m = Column(Float)          # metres from lap start
    speed_kmh = Column(Float)
    rpm = Column(Integer)
    gear = Column(Integer)
    throttle_pct = Column(Float)        # 0–100
    brake = Column(Boolean)
    drs = Column(Boolean)               # True = DRS open

    # 3D position (FastF1 provides these for most modern circuits)
    x = Column(Float)
    y = Column(Float)
    z = Column(Float)

    # Metadata channels
    status = Column(String(20))         # e.g. "OnTrack", "OffTrack"
    source = Column(String(20))         # "car" or "pos" in FastF1

    # Relationship
    lap = relationship("Lap", back_populates="telemetry_points")

    __table_args__ = (
        Index("ix_telemetry_lap", "lap_id"),
        Index("ix_telemetry_session", "session_id"),
        Index("ix_telemetry_lap_dist", "lap_id", "distance_m"),
        Index("ix_telemetry_lap_time", "lap_id", "time_ms"),
    )


# ── Weather ───────────────────────────────────────────────────────────────────


class Weather(Base):
    """Session-level weather telemetry (typically sampled every ~20 seconds)."""

    __tablename__ = "weather"

    weather_id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("sessions.session_id", ondelete="CASCADE"), nullable=False)
    time_ms = Column(Integer)           # ms from session start
    air_temp = Column(Float)
    track_temp = Column(Float)
    humidity = Column(Float)
    pressure = Column(Float)
    wind_speed = Column(Float)
    wind_dir = Column(Integer)          # degrees
    rainfall = Column(Boolean, default=False)

    session = relationship("Session", back_populates="weather_points")

    __table_args__ = (
        Index("ix_weather_session", "session_id"),
    )


# ── Stints ────────────────────────────────────────────────────────────────────


class Stint(Base):
    """A continuous run on a single tyre set between pit stops."""

    __tablename__ = "stints"

    stint_id = Column(Integer, primary_key=True, autoincrement=True)
    driver_id = Column(Integer, ForeignKey("drivers.driver_id", ondelete="CASCADE"), nullable=False)
    session_id = Column(Integer, ForeignKey("sessions.session_id", ondelete="CASCADE"), nullable=False)
    stint_number = Column(Integer, nullable=False)
    compound = Column(String(20))
    start_lap = Column(Integer)
    end_lap = Column(Integer)
    tyre_life_start = Column(Integer)   # age of the set at stint start (used sets have life > 1)

    driver = relationship("Driver", back_populates="stints")
    session = relationship("Session", back_populates="stints")

    __table_args__ = (
        Index("ix_stints_driver_session", "driver_id", "session_id"),
    )


# ── Tyres ─────────────────────────────────────────────────────────────────────


class Tyre(Base):
    """Per-lap tyre state snapshot and computed degradation factor."""

    __tablename__ = "tyres"

    tyre_id = Column(Integer, primary_key=True, autoincrement=True)
    lap_id = Column(Integer, ForeignKey("laps.lap_id", ondelete="CASCADE"), nullable=False, unique=True)
    compound = Column(String(20))
    tyre_life = Column(Integer)
    degradation_factor = Column(Float)  # delta_laptime / delta_tyre_life for this stint

    lap = relationship("Lap", back_populates="tyre")


# ── Pit Stops ─────────────────────────────────────────────────────────────────


class PitStop(Base):
    """Individual pit stop event."""

    __tablename__ = "pitstops"

    pitstop_id = Column(Integer, primary_key=True, autoincrement=True)
    driver_id = Column(Integer, ForeignKey("drivers.driver_id", ondelete="CASCADE"), nullable=False)
    session_id = Column(Integer, ForeignKey("sessions.session_id", ondelete="CASCADE"), nullable=False)
    lap_number = Column(Integer, nullable=False)
    duration_ms = Column(Integer)       # total pit lane time loss in ms

    driver = relationship("Driver", back_populates="pitstops")
    session = relationship("Session", back_populates="pitstops")

    __table_args__ = (
        Index("ix_pitstops_driver_session", "driver_id", "session_id"),
    )


# ── Predictions ───────────────────────────────────────────────────────────────


class Prediction(Base):
    """Stores ML model prediction results for strategy simulations.

    Keeping model_name + model_version allows A/B comparison between
    different model iterations without overwriting historical predictions.
    input_features stores the feature vector as JSON text for reproducibility.
    """

    __tablename__ = "predictions"

    prediction_id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("sessions.session_id", ondelete="CASCADE"), nullable=False)
    driver_id = Column(Integer, ForeignKey("drivers.driver_id", ondelete="CASCADE"), nullable=False)
    model_name = Column(String(100), nullable=False)    # e.g. "tire_degradation_xgb"
    model_version = Column(String(20), default="1.0.0")
    prediction_type = Column(String(50), nullable=False)  # e.g. "lap_time", "pit_window"
    input_features = Column(Text)                         # JSON blob
    predicted_value = Column(Float)
    actual_value = Column(Float)                          # filled in post-race for validation
    confidence = Column(Float)                            # model confidence or RMSE
    created_at = Column(DateTime, default=func.now())

    session = relationship("Session", back_populates="predictions")
    driver = relationship("Driver", back_populates="predictions")

    __table_args__ = (
        Index("ix_predictions_session_driver", "session_id", "driver_id"),
        Index("ix_predictions_type", "prediction_type"),
    )
