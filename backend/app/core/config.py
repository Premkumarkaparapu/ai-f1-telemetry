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
    (2023, "Italian Grand Prix",       "R"),   # Monza  — high-speed, low-df
    (2023, "Monaco Grand Prix",        "R"),   # Monaco — street, undercut
    (2023, "Dutch Grand Prix",         "R"),   # Zandvoort — mixed

    # ── 2025 Full Season (completed through British GP, Round 12) ────
    (2025, "Australian Grand Prix",    "R"),   # R01 — Melbourne
    (2025, "Chinese Grand Prix",       "R"),   # R02 — Shanghai (Sprint)
    (2025, "Japanese Grand Prix",      "R"),   # R03 — Suzuka
    (2025, "Bahrain Grand Prix",       "R"),   # R04 — Sakhir
    (2025, "Saudi Arabian Grand Prix", "R"),   # R05 — Jeddah
    (2025, "Miami Grand Prix",         "R"),   # R06 — Miami (Sprint)
    (2025, "Emilia Romagna Grand Prix","R"),   # R07 — Imola
    (2025, "Monaco Grand Prix",        "R"),   # R08 — Monaco
    (2025, "Spanish Grand Prix",       "R"),   # R09 — Barcelona
    (2025, "Canadian Grand Prix",      "R"),   # R10 — Montreal
    (2025, "Austrian Grand Prix",      "R"),   # R11 — Red Bull Ring (Sprint)
    (2025, "British Grand Prix",       "R"),   # R12 — Silverstone
]
