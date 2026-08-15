"""
Migrate SQLite → PostgreSQL for production deployment.

Usage:
    python db_migrate.py --target postgresql://user:pass@host:5432/f1_telemetry
"""
import argparse
import sys
import csv
from io import StringIO
from pathlib import Path
import pandas as pd
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))

def psql_insert_copy(table, conn, keys, data_iter):
    """Custom insert method utilizing PostgreSQL COPY command for maximum speed."""
    dbapi_conn = conn.connection
    
    # Fast row-by-row cleaning generator to avoid slow pandas loops
    def clean_row(row):
        cleaned = []
        for val in row:
            if val is None or val is pd.NA or (isinstance(val, float) and np.isnan(val)):
                cleaned.append("")
            elif isinstance(val, bool):
                cleaned.append("true" if val else "false")
            elif isinstance(val, (int, float)) and int(val) == val:
                # E.g. 28000.0 -> "28000" (essential for integer columns in PG)
                cleaned.append(str(int(val)))
            else:
                cleaned.append(str(val))
        return cleaned

    with dbapi_conn.cursor() as cur:
        # Override session read-only transaction constraints
        try:
            cur.execute("SET default_transaction_read_only = off;")
            cur.execute("SET transaction_read_only = off;")
        except Exception as e:
            print(f"  Warning setting session read-write in COPY: {e}")
            
        s_buf = StringIO()
        writer = csv.writer(s_buf, delimiter='\t', lineterminator='\n', quoting=csv.QUOTE_MINIMAL)
        writer.writerows(clean_row(row) for row in data_iter)
        s_buf.seek(0)
        
        columns = ', '.join(['"{}"'.format(k) for k in keys])
        if table.schema:
            table_name = '{}.{}'.format(table.schema, table.name)
        else:
            table_name = table.name
            
        sql = 'COPY {} ({}) FROM STDIN WITH CSV DELIMITER \'\t\' NULL \'\''.format(table_name, columns)
        cur.copy_expert(sql=sql, file=s_buf)

def migrate(target_url: str):
    from sqlalchemy import create_engine, text

    src_url = f"sqlite:///{Path('f1_telemetry.db').resolve()}"
    print(f"Source : {src_url}")
    print(f"Target : {target_url}")

    src = create_engine(src_url, connect_args={"check_same_thread": False})
    tgt = create_engine(target_url, pool_pre_ping=True)

    # Tables in dependency-safe order
    tables = [
        "users",
        "sessions",
        "drivers",
        "laps",
        "weather",
        "stints",
        "tyres",
        "pitstops",
        "predictions",
        "telemetry"
    ]

    # Clean target tables before starting (with CASCADE to respect FKs)
    print("Truncating target tables...")
    with tgt.connect() as conn:
        try:
            conn.execute(text("SET default_transaction_read_only = off;"))
            conn.execute(text("SET transaction_read_only = off;"))
        except Exception as e:
            print(f"  Warning setting session read-write in TRUNCATE: {e}")
            
        for table in reversed(tables):
            try:
                conn.execute(text(f"TRUNCATE TABLE {table} RESTART IDENTITY CASCADE;"))
            except Exception as e:
                print(f"  Warning truncating {table}: {e}")
        conn.commit()

    print("Migrating tables...")
    for table in tables:
        try:
            # Read from SQLite
            if table == "telemetry":
                # Only migrate telemetry for 2023 baseline sessions to respect Supabase storage limits (500MB)
                query = """
                    SELECT t.* FROM telemetry t
                    JOIN laps l ON t.lap_id = l.lap_id
                    JOIN drivers d ON l.driver_id = d.driver_id
                    JOIN sessions s ON d.session_id = s.session_id
                    WHERE s.year = 2023
                """
                df = pd.read_sql(query, src)
            else:
                df = pd.read_sql(f"SELECT * FROM {table}", src)
                
            if df.empty:
                print(f"  {table}: empty, skipping")
                continue

            # Execute bulk COPY insertion using custom method
            df.to_sql(
                table,
                tgt,
                if_exists="append",
                index=False,
                method=psql_insert_copy
            )
            print(f"  {table}: {len(df):,} rows migrated successfully")
        except Exception as e:
            print(f"  {table}: ERROR — {e}")

    # Reset sequences on PostgreSQL
    print("Resetting PostgreSQL database sequences...")
    with tgt.connect() as conn:
        try:
            conn.execute(text("SET default_transaction_read_only = off;"))
            conn.execute(text("SET transaction_read_only = off;"))
        except Exception as e:
            print(f"  Warning setting session read-write in SEQUENCE RESET: {e}")
            
        pk_map = {
            "sessions": "session_id", "drivers": "driver_id", "laps": "lap_id",
            "telemetry": "tel_id", "stints": "stint_id", "pitstops": "pitstop_id",
            "predictions": "prediction_id", "users": "user_id", "weather": "weather_id",
            "tyres": "tyre_id"
        }
        for table in tables:
            pk = pk_map.get(table)
            if not pk:
                continue
            try:
                # Check if there is data in table
                res = conn.execute(text(f"SELECT COUNT(*) FROM {table}")).fetchone()
                if res and res[0] > 0:
                    conn.execute(text(
                        f"SELECT setval(pg_get_serial_sequence('{table}', '{pk}'), "
                        f"(SELECT MAX({pk}) FROM {table}))"
                    ))
            except Exception as e:
                print(f"  Warning resetting sequence for {table}: {e}")
        conn.commit()
    print("Done! All sequences reset.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", required=True, help="PostgreSQL connection URL")
    args = parser.parse_args()
    migrate(args.target)
