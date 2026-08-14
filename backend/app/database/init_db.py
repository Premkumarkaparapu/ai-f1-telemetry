"""
Database initialization script.
Run once to create all tables:

    python -m backend.app.database.init_db

Safe to re-run — uses checkfirst=True so it won't drop existing tables.
For schema migrations in production, use Alembic instead.
"""

from backend.app.core.logging import get_logger, setup_logging
from backend.app.database.db import engine

setup_logging("pipeline.log")
logger = get_logger(__name__)


def init_db() -> None:
    import os
    from pathlib import Path
    from alembic.config import Config
    from alembic import command

    logger.info("Applying database migrations at: %s", engine.url)

    # Locate alembic.ini at the repository root
    root_dir = Path(__file__).resolve().parents[3]
    ini_path = str(root_dir / "alembic.ini")

    alembic_cfg = Config(ini_path)

    # Resolve dynamic DATABASE_URL
    from backend.app.core.config import DATABASE_URL
    url = os.getenv("DATABASE_URL", DATABASE_URL)
    alembic_cfg.set_main_option("sqlalchemy.url", url)

    command.upgrade(alembic_cfg, "head")
    logger.info("Database migrations applied successfully.")


if __name__ == "__main__":
    init_db()
