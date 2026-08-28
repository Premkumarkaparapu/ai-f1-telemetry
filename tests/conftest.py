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
os.environ["GEMINI_API_KEY"] = "mock_key"


# ── Dependency Overrides for Tests ───────────────────────────────────────────
from backend.app.main import app  # noqa: E402
from backend.app.api.v1.security import verify_request, AuthenticatedUser  # noqa: E402
from backend.app.database.db import get_db  # noqa: E402
from backend.app.database.models import Base  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

# Shared in-memory database using StaticPool
TEST_DATABASE_URL = "sqlite://"
engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


async def override_verify_request():
    return AuthenticatedUser(
        sub="test_user",
        scopes=["telemetry:read", "strategy:run", "ai:ask"]
    )


app.dependency_overrides[get_db] = override_get_db
app.dependency_overrides[verify_request] = override_verify_request
