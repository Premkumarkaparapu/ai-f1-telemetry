"""
Centralised logging setup.
Call setup_logging() once at application/pipeline startup.
Both the backend and data pipeline import from here.
"""

import logging
import logging.handlers

from backend.app.core.config import LOG_DIR, LOG_LEVEL


def setup_logging(log_file: str = "backend.log") -> logging.Logger:
    """Configure root logger with console + rotating file handlers."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOG_DIR / log_file

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    root_logger = logging.getLogger()
    root_logger.setLevel(LOG_LEVEL)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # Rotating file handler (10MB × 5 backup files)
    file_handler = logging.handlers.RotatingFileHandler(
        log_path, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    return root_logger


def get_logger(name: str) -> logging.Logger:
    """Return a named child logger. Use in every module:

        logger = get_logger(__name__)
    """
    return logging.getLogger(name)
