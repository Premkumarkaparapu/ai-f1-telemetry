"""
Database initialization script.
Run once to create all tables:

    python -m backend.app.database.init_db

Safe to re-run — uses checkfirst=True so it won't drop existing tables.
For schema migrations in production, use Alembic instead.
"""

from backend.app.core.logging import get_logger, setup_logging
from backend.app.database.db import engine
from backend.app.database.models import Base

setup_logging("pipeline.log")
logger = get_logger(__name__)


def init_db() -> None:
    logger.info("Creating database tables at: %s", engine.url)
    Base.metadata.create_all(bind=engine, checkfirst=True)
    logger.info("All tables created successfully.")


if __name__ == "__main__":
    init_db()
