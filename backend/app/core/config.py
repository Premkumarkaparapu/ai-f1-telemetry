"""
Central configuration module.
All settings are read from environment variables (set in .env or docker-compose).
Copy .env.example → .env and adjust as needed.
"""

import os
from pathlib import Path

# ── Project root ──────────────────────────────────────────────────────────────
# repo root (backend/app/core/config.py → 3 levels up = f1/)
ROOT_DIR = Path(__file__).resolve().parents[3]


# ── Database ──────────────────────────────────────────────────────────────────
DATABASE_URL: str = os.getenv(
    "DATABASE_URL",
    f"sqlite:///{ROOT_DIR / 'f1_telemetry.db'}",
)

# ── Data pipeline paths ────────────────────────────────────────────────────────
CACHE_DIR: Path = Path(os.getenv("CACHE_DIR", str(ROOT_DIR / "data_pipeline" / "cache")))
RAW_DIR: Path = ROOT_DIR / "data_pipeline" / "raw"
PROCESSED_DIR: Path = ROOT_DIR / "data_pipeline" / "processed"

# ── Logging ───────────────────────────────────────────────────────────────────
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_DIR: Path = ROOT_DIR / "logs"

# ── Telemetry ─────────────────────────────────────────────────────────────────
# Downsample rate in Hz (5Hz = one sample every 200ms).
# Raw FastF1 data is ~10–18Hz; 5Hz preserves driver comparison resolution at
# a fraction of the storage cost (~1 M rows for 3 races vs 2M+ at full rate).
TELEMETRY_SAMPLE_RATE: int = int(os.getenv("TELEMETRY_SAMPLE_RATE", "5"))

# ── ML ────────────────────────────────────────────────────────────────────────
MODEL_PATH: Path = Path(os.getenv("MODEL_PATH", str(ROOT_DIR / "ml" / "models")))

# ── API ───────────────────────────────────────────────────────────────────────
API_VERSION: str = os.getenv("API_VERSION", "v1")
API_PREFIX: str = f"/api/{API_VERSION}"

# ── Fuel correction ───────────────────────────────────────────────────────────
# Each lap the car burns ~1.5–1.8 kg of fuel. Lighter car → faster lap time.
# This constant approximates the lap-time improvement per lap as fuel depletes.
# Validated post-ingest by checking long-stint lap time trend flattens to ~flat.
FUEL_EFFECT_SEC_PER_LAP: float = float(
    os.getenv("FUEL_EFFECT_SEC_PER_LAP", "0.055")
)

# ── Sessions to ingest ────────────────────────────────────────────────────────
# Format: (year, event_name, session_type)
# Chosen to cover distinct circuit archetypes for more generalisable ML models.
TARGET_SESSIONS: list[tuple[int, str, str]] = [
    (2023, "Italian Grand Prix", "R"),    # Monza — high-speed, low-downforce
    (2023, "Monaco Grand Prix", "R"),     # Monaco — street, undercut-heavy
    (2023, "Dutch Grand Prix", "R"),      # Zandvoort — mixed conditions
]
