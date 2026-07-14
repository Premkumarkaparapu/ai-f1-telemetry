"""
Shared pytest fixtures available to all test modules.
"""

import os
import pytest

# ── Environment defaults for tests ────────────────────────────────────────────
# These ensure no test accidentally writes to the real database.
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("LOG_LEVEL", "WARNING")
os.environ.setdefault("TELEMETRY_SAMPLE_RATE", "5")
os.environ.setdefault("FUEL_EFFECT_SEC_PER_LAP", "0.055")
