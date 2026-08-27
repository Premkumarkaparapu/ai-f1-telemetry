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
    if (
        "pooler.supabase.com" in DATABASE_URL
        or ":6543" in DATABASE_URL
        or "pgbouncer=true" in DATABASE_URL.lower()
    ):
        from sqlalchemy.pool import NullPool
        logger.info("Supabase pooler/PgBouncer detected. Using NullPool.")
        engine_args["poolclass"] = NullPool
    else:
        engine_args["pool_size"] = DB_POOL_SIZE
        engine_args["max_overflow"] = DB_MAX_OVERFLOW
        engine_args["pool_recycle"] = 1800

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    **engine_args
)

def set_read_write(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("SET default_transaction_read_only = off;")
    cursor.execute("SET transaction_read_only = off;")
    cursor.close()


# Automatically override session read-only transaction constraints for PostgreSQL/Supabase
if not DATABASE_URL.startswith("sqlite"):
    import os
    if os.getenv("DB_DISABLE_ON_CONNECT_HOOKS", "false").lower() != "true":
        event.listen(engine, "connect", set_read_write)

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
