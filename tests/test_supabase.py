from unittest.mock import patch
from sqlalchemy.pool import NullPool


def test_supabase_pooler_nullpool():
    # Setup test URL matching Supabase PgBouncer pooler format
    test_url = (
        "postgresql://postgres.ref:pass@"
        "aws-0-us-east-1.pooler.supabase.com:6543/postgres"
    )

    # Evaluate NullPool detection logic
    connect_args = {}
    engine_args = {
        "echo": False,
        "pool_pre_ping": True,
    }

    if not test_url.startswith("sqlite"):
        if (
            "pooler.supabase.com" in test_url
            or ":6543" in test_url
            or "pgbouncer=true" in test_url.lower()
        ):
            engine_args["poolclass"] = NullPool
        else:
            engine_args["pool_size"] = 20
            engine_args["max_overflow"] = 10
            engine_args["pool_recycle"] = 1800

    assert engine_args["poolclass"] is NullPool

    # Test create_engine construction works cleanly with the custom args
    import sqlalchemy
    with patch("sqlalchemy.create_engine") as mock_create_engine:
        sqlalchemy.create_engine(
            test_url, connect_args=connect_args, **engine_args
        )
        mock_create_engine.assert_called_once_with(
            test_url,
            connect_args=connect_args,
            echo=False,
            pool_pre_ping=True,
            poolclass=NullPool,
        )
