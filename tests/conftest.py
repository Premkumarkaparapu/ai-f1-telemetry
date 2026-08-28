"""
Shared pytest fixtures available to all test modules.
"""

import os
import pytest

# ── Environment defaults for tests ────────────────────────────────────────────
# These ensure no test accidentally writes to the real database.
os.environ["DATABASE_URL"] = "sqlite:///test_temp.db"
os.environ["LOG_LEVEL"] = "WARNING"
os.environ["TELEMETRY_SAMPLE_RATE"] = "5"
os.environ["FUEL_EFFECT_SEC_PER_LAP"] = "0.055"
os.environ["AI_PROVIDER"] = "mock"
os.environ["GEMINI_API_KEY"] = "mock_key"
os.environ["AUDIT_IP_SALT"] = "test_salt_value"


# ── Dependency Overrides for Tests ───────────────────────────────────────────
from backend.app.main import app  # noqa: E402
from backend.app.api.v1.security import verify_request, AuthenticatedUser  # noqa: E402
from backend.app.database.db import get_db  # noqa: E402
from backend.app.database.models import Base  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

# Shared file database
TEST_DATABASE_URL = "sqlite:///test_temp.db"
engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)

from backend.app.database.db import engine as db_engine  # noqa: E402
Base.metadata.create_all(bind=db_engine)


@pytest.fixture(scope="session", autouse=True)
def cleanup_test_db():
    yield
    # Remove temporary database files
    for filename in ("test_temp.db", "test_temp.db-wal", "test_temp.db-shm"):
        if os.path.exists(filename):
            try:
                os.remove(filename)
            except Exception:
                pass


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
