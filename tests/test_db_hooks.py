import os
import sys
from sqlalchemy import event


def test_db_hooks_disabled_registration():
    """Verify connect hooks are NOT registered if disabled."""
    # Clear cache to force module re-evaluation
    sys.modules.pop("backend.app.database.db", None)
    os.environ["DB_DISABLE_ON_CONNECT_HOOKS"] = "true"

    try:
        from backend.app.database.db import engine, set_read_write

        # Check event registration state using SQLAlchemy's native API
        registered = event.contains(engine, "connect", set_read_write)
        assert registered is False
    finally:
        os.environ.pop("DB_DISABLE_ON_CONNECT_HOOKS", None)


def test_db_hooks_enabled_registration():
    """Verify that connect hooks are registered by default."""
    sys.modules.pop("backend.app.database.db", None)
    os.environ["DB_DISABLE_ON_CONNECT_HOOKS"] = "false"

    try:
        from backend.app.database.db import engine, set_read_write

        registered = event.contains(engine, "connect", set_read_write)
        if not str(engine.url).startswith("sqlite"):
            assert registered is True
        else:
            assert registered is False
    finally:
        os.environ.pop("DB_DISABLE_ON_CONNECT_HOOKS", None)
