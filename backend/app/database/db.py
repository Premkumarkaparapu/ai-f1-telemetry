"""
SQLAlchemy engine and session factory.
Every other module imports `get_db` (for FastAPI) or `SessionLocal` (for pipeline scripts).
"""

from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from backend.app.core.config import DATABASE_URL, DB_POOL_SIZE, DB_MAX_OVERFLOW
from backend.app.core.logging import get_logger

logger = get_logger(__name__)

# ── Engine ────────────────────────────────────────────────────────────────────
connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine_args = {
    "echo": False,
    "pool_pre_ping": True,
}

# Apply connection pooling only for PostgreSQL/remote databases
if not DATABASE_URL.startswith("sqlite"):
    engine_args["pool_size"] = DB_POOL_SIZE
    engine_args["max_overflow"] = DB_MAX_OVERFLOW
    engine_args["pool_recycle"] = 1800

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    **engine_args
)

# Enable WAL mode for SQLite — dramatically improves concurrent read performance.
if DATABASE_URL.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, _):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# ── FastAPI dependency ────────────────────────────────────────────────────────

def get_db() -> Generator[Session, None, None]:
    """Yield a database session, ensuring it's always closed after the request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ── Pipeline context manager ──────────────────────────────────────────────────

@contextmanager
def get_pipeline_db() -> Generator[Session, None, None]:
    """Context manager for use in pipeline scripts (non-FastAPI code).

    Usage:
        with get_pipeline_db() as db:
            db.add(record)
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
