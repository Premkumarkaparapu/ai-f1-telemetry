"""
Domain constants shared across the pipeline and backend.
Compound ordering, display names, and colour codes match F1 official branding.
"""

# ── Tyre compounds ────────────────────────────────────────────────────────────
COMPOUND_ORDER = ["SOFT", "MEDIUM", "HARD", "INTERMEDIATE", "WET"]

COMPOUND_COLORS: dict[str, str] = {
    "SOFT": "#FF3333",
    "MEDIUM": "#FFD700",
    "HARD": "#EEEEEE",
    "INTERMEDIATE": "#39B54A",
    "WET": "#0067FF",
    "UNKNOWN": "#AAAAAA",
}

# ── Telemetry channels stored in DB ───────────────────────────────────────────
TELEMETRY_CHANNELS = [
    "Time",
    "Distance",
    "Speed",
    "RPM",
    "nGear",
    "Throttle",
    "Brake",
    "DRS",
    "X",
    "Y",
    "Z",
    "Status",
    "Source",
]

# ── Session types ─────────────────────────────────────────────────────────────
SESSION_TYPE_MAP: dict[str, str] = {
    "R": "Race",
    "Q": "Qualifying",
    "FP1": "Practice 1",
    "FP2": "Practice 2",
    "FP3": "Practice 3",
    "S": "Sprint",
}

# ── Feature engineering ───────────────────────────────────────────────────────
# Minimum number of laps in a stint to fit a degradation model.
MIN_STINT_LAPS_FOR_DEGRADATION = 3

# Lap numbers at start/end of stint to exclude (in/out laps are atypical).
STINT_EXCLUSION_LAPS = 1

# Sector columns as they appear in FastF1 laps DataFrame.
SECTOR_COLS = ["Sector1Time", "Sector2Time", "Sector3Time"]
SECTOR_MS_COLS = ["sector1_ms", "sector2_ms", "sector3_ms"]
