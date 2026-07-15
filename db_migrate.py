"""
Migrate SQLite → PostgreSQL for production deployment.

Usage:
    python db_migrate.py --target postgresql://user:pass@host:5432/f1_telemetry
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

def migrate(target_url: str):
    from sqlalchemy import create_engine, text
    import pandas as pd

    src_url = f"sqlite:///{Path('f1_telemetry.db').resolve()}"
    print(f"Source : {src_url}")
    print(f"Target : {target_url}")

    src = create_engine(src_url, connect_args={"check_same_thread": False})
    tgt = create_engine(target_url, pool_pre_ping=True)

    # Create all tables on target
    from backend.app.database.models import Base
    print("Creating schema on target...")
    Base.metadata.create_all(tgt)

    tables = ["users", "sessions", "drivers", "laps", "telemetry", "stints", "pitstops", "predictions"]

    for table in tables:
        try:
            df = pd.read_sql(f"SELECT * FROM {table}", src)
            if df.empty:
                print(f"  {table}: empty, skipping")
                continue
            df.to_sql(table, tgt, if_exists="append", index=False, chunksize=500, method="multi")
            print(f"  {table}: {len(df):,} rows migrated")
        except Exception as e:
            print(f"  {table}: ERROR — {e}")

    # Reset sequences on PostgreSQL
    with tgt.connect() as conn:
        for table in tables:
            try:
                pk_map = {
                    "sessions": "session_id", "drivers": "driver_id", "laps": "lap_id",
                    "telemetry": "tel_id", "stints": "stint_id", "pitstops": "pitstop_id",
                    "predictions": "prediction_id", "users": "user_id"
                }
                pk = pk_map.get(table)
                if pk:
                    conn.execute(text(f"SELECT setval(pg_get_serial_sequence('{table}', '{pk}'), (SELECT MAX({pk}) FROM {table}))"))
            except Exception:
                pass
        conn.commit()
    print("Done! All sequences reset.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", required=True, help="PostgreSQL connection URL")
    args = parser.parse_args()
    migrate(args.target)
