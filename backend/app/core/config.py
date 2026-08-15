"""Central configuration module.

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
    "postgresql://f1user:RuLlNmXxzLY8LMNTzA3I6iZ5QU3NBXqU"
    "@dpg-d9bngujbc2fs73eg2oj0-a.singapore-postgres.render.com/f1_telemetry_xhv3"
)
DB_POOL_SIZE: int = int(os.getenv("DB_POOL_SIZE", "20"))
DB_MAX_OVERFLOW: int = int(os.getenv("DB_MAX_OVERFLOW", "10"))

# ── Production ────────────────────────────────────────────────────────────────
CORS_ORIGINS: list[str] = [
    o.strip()
    for o in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000").split(",")
    if o.strip()
]

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
# 2023 originals (circuit archetypes for ML baseline)
TARGET_SESSIONS: list[tuple[int, str, str]] = [
    # ── 2023 Baseline ─────────────────────────────────────────────────
    (2023, "Italian Grand Prix", "R"),
    (2023, "Monaco Grand Prix", "R"),
    (2023, "Dutch Grand Prix", "R"),

    # ── 2024 Season (Full 24 events) ──────────────────────────────────
    (2024, "Bahrain Grand Prix", "R"),
    (2024, "Saudi Arabian Grand Prix", "R"),
    (2024, "Australian Grand Prix", "R"),
    (2024, "Japanese Grand Prix", "R"),
    (2024, "Chinese Grand Prix", "R"),
    (2024, "Miami Grand Prix", "R"),
    (2024, "Emilia Romagna Grand Prix", "R"),
    (2024, "Monaco Grand Prix", "R"),
    (2024, "Canadian Grand Prix", "R"),
    (2024, "Spanish Grand Prix", "R"),
    (2024, "Austrian Grand Prix", "R"),
    (2024, "British Grand Prix", "R"),
    (2024, "Hungarian Grand Prix", "R"),
    (2024, "Belgian Grand Prix", "R"),
    (2024, "Dutch Grand Prix", "R"),
    (2024, "Italian Grand Prix", "R"),
    (2024, "Azerbaijan Grand Prix", "R"),
    (2024, "Singapore Grand Prix", "R"),
    (2024, "United States Grand Prix", "R"),
    (2024, "Mexico City Grand Prix", "R"),
    (2024, "São Paulo Grand Prix", "R"),
    (2024, "Las Vegas Grand Prix", "R"),
    (2024, "Qatar Grand Prix", "R"),
    (2024, "Abu Dhabi Grand Prix", "R"),

    # ── 2025 Season (Full 24 events) ──────────────────────────────────
    (2025, "Australian Grand Prix", "R"),
    (2025, "Chinese Grand Prix", "R"),
    (2025, "Japanese Grand Prix", "R"),
    (2025, "Bahrain Grand Prix", "R"),
    (2025, "Saudi Arabian Grand Prix", "R"),
    (2025, "Miami Grand Prix", "R"),
    (2025, "Emilia Romagna Grand Prix", "R"),
    (2025, "Monaco Grand Prix", "R"),
    (2025, "Spanish Grand Prix", "R"),
    (2025, "Canadian Grand Prix", "R"),
    (2025, "Austrian Grand Prix", "R"),
    (2025, "British Grand Prix", "R"),
    (2025, "Belgian Grand Prix", "R"),
    (2025, "Hungarian Grand Prix", "R"),
    (2025, "Dutch Grand Prix", "R"),
    (2025, "Italian Grand Prix", "R"),
    (2025, "Azerbaijan Grand Prix", "R"),
    (2025, "Singapore Grand Prix", "R"),
    (2025, "United States Grand Prix", "R"),
    (2025, "Mexico City Grand Prix", "R"),
    (2025, "São Paulo Grand Prix", "R"),
    (2025, "Las Vegas Grand Prix", "R"),
    (2025, "Qatar Grand Prix", "R"),
    (2025, "Abu Dhabi Grand Prix", "R"),

    # ── 2026 Season (Completed to Aug 14, 2026) ──────────────────────
    (2026, "Australian Grand Prix", "R"),
    (2026, "Chinese Grand Prix", "R"),
    (2026, "Japanese Grand Prix", "R"),
    (2026, "Miami Grand Prix", "R"),
    (2026, "Canadian Grand Prix", "R"),
    (2026, "Monaco Grand Prix", "R"),
    (2026, "Barcelona Grand Prix", "R"),
    (2026, "Austrian Grand Prix", "R"),
    (2026, "British Grand Prix", "R"),
    (2026, "Belgian Grand Prix", "R"),
    (2026, "Hungarian Grand Prix", "R"),
]

# ── Backup Configuration ──────────────────────────────────────────────────────
BACKUP_RETENTION_DAYS: int = int(os.getenv("BACKUP_RETENTION_DAYS", "7"))
