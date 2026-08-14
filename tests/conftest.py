"""
Shared pytest fixtures available to all test modules.
"""

import os

# ── Environment defaults for tests ────────────────────────────────────────────
# These ensure no test accidentally writes to the real database.
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["LOG_LEVEL"] = "WARNING"
os.environ["TELEMETRY_SAMPLE_RATE"] = "5"
os.environ["FUEL_EFFECT_SEC_PER_LAP"] = "0.055"
os.environ["AI_PROVIDER"] = "mock"


# ── Dependency Overrides for Tests ───────────────────────────────────────────
from backend.app.main import app  # noqa: E402
from backend.app.api.v1.security import verify_request, AuthenticatedUser  # noqa: E402


async def override_verify_request():
    return AuthenticatedUser(
        sub="test_user",
        scopes=["telemetry:read", "strategy:run", "ai:ask"]
    )
app.dependency_overrides[verify_request] = override_verify_request
