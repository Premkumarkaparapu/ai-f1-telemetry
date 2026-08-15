"""Reset auto-increment primary key sequences in PostgreSQL.

Solves UniqueViolation errors when inserting records after manual key insertions.
"""

import sys
from pathlib import Path
from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.database.db import SessionLocal  # noqa: E402


def reset_sequences():
    db = SessionLocal()
    # Check if database is SQLite or Postgres
    bind = db.get_bind()
    dialect = bind.dialect.name
    if dialect == "sqlite":
        print("SQLite database active; sequences reset not needed.")
        db.close()
        return

    print("PostgreSQL database active; resetting sequences...")
    tables = [
        ("sessions", "session_id"),
        ("drivers", "driver_id"),
        ("laps", "lap_id"),
        ("pitstops", "pitstop_id"),
        ("stints", "stint_id"),
        ("predictions", "prediction_id"),
        ("weather", "weather_id"),
    ]
    for table, col in tables:
        try:
            seq_fn = f"pg_get_serial_sequence('{table}', '{col}')"
            query = f"SELECT setval({seq_fn}, coalesce(max({col}), 1)) FROM {table}"
            db.execute(text(query))
            print(f"  Successfully reset sequence for {table}.{col}")
        except Exception as exc:
            db.rollback()
            print(f"  Warning: Could not reset sequence for {table}: {exc}")

    db.commit()
    db.close()
    print("Database sequence reset complete.")


if __name__ == "__main__":
    reset_sequences()
