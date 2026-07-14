"""
Data pipeline — Stage 1: Extract
Fetches F1 session data via FastF1 and pickles the raw session objects to disk.
Subsequent stages read from disk so this only needs to run once per session.

Usage:
    python -m data_pipeline.ingest
"""

import pickle
from pathlib import Path

import fastf1

from backend.app.core.config import CACHE_DIR, RAW_DIR, TARGET_SESSIONS
from backend.app.core.logging import get_logger, setup_logging

setup_logging("pipeline.log")
logger = get_logger(__name__)


def enable_cache() -> None:
    """Enable FastF1 local cache to avoid re-downloading data."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    fastf1.Cache.enable_cache(str(CACHE_DIR))
    logger.info("FastF1 cache enabled at: %s", CACHE_DIR)


def fetch_session(year: int, event: str, session_type: str) -> fastf1.core.Session:
    """Load one session from FastF1 (uses cache after first download)."""
    logger.info("Loading session: %d %s %s", year, event, session_type)
    session = fastf1.get_session(year, event, session_type)
    session.load(
        laps=True,
        telemetry=True,
        weather=True,
        messages=False,  # team radio/messages — not needed
    )
    logger.info(
        "Session loaded: %s — %d laps across %d drivers",
        session.event["EventName"],
        len(session.laps),
        session.laps["DriverNumber"].nunique(),
    )
    return session


def save_raw(session: fastf1.core.Session, year: int, event: str, session_type: str) -> Path:
    """Pickle the session object to raw/ for use by transform stage."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    slug = f"{year}_{event.replace(' ', '_')}_{session_type}.pkl"
    path = RAW_DIR / slug
    with open(path, "wb") as f:
        pickle.dump(session, f)
    logger.info("Raw session saved to: %s", path)
    return path


def load_raw(year: int, event: str, session_type: str) -> fastf1.core.Session:
    """Load a previously pickled session from disk."""
    slug = f"{year}_{event.replace(' ', '_')}_{session_type}.pkl"
    path = RAW_DIR / slug
    if not path.exists():
        raise FileNotFoundError(f"Raw session not found: {path}. Run ingest first.")
    with open(path, "rb") as f:
        return pickle.load(f)


def ingest_all(sessions=None) -> None:
    """Fetch and save all target sessions. Uses TARGET_SESSIONS if none provided."""
    enable_cache()
    targets = sessions or TARGET_SESSIONS
    for year, event, session_type in targets:
        slug = f"{year}_{event.replace(' ', '_')}_{session_type}.pkl"
        if (RAW_DIR / slug).exists():
            logger.info("Skipping (already ingested): %d %s %s", year, event, session_type)
            continue
        try:
            session = fetch_session(year, event, session_type)
            save_raw(session, year, event, session_type)
        except Exception as exc:
            logger.error("Failed to ingest %d %s %s: %s", year, event, session_type, exc)
            raise


if __name__ == "__main__":
    ingest_all()
