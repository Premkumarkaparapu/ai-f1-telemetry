"""
Migrate local SQLite F1 data to Render PostgreSQL.
Run: python migrate_to_pg.py
"""
import sqlite3
import psycopg2
import sys

SQLITE_PATH = "f1_telemetry.db"
PG_URL = "postgresql://f1user:RuLlNmXxzLY8LMNTzA3I6iZ5QU3NBXqU@dpg-d9bngujbc2fs73eg2oj0-a/f1_telemetry_xhv3"

print("Connecting to SQLite...")
sqlite_conn = sqlite3.connect(SQLITE_PATH)
sqlite_conn.row_factory = sqlite3.Row
sc = sqlite_conn.cursor()

print("Connecting to Render PostgreSQL...")
pg_conn = psycopg2.connect(PG_URL)
pg_conn.autocommit = False
pc = pg_conn.cursor()

def migrate_table(table, insert_sql, fetch_sql, transform=None):
    sc.execute(fetch_sql)
    rows = sc.fetchall()
    print(f"  Migrating {len(rows)} rows from {table}...")
    for row in rows:
        data = dict(row)
        if transform:
            data = transform(data)
        try:
            pc.execute(insert_sql, data)
        except Exception as e:
            pg_conn.rollback()
            print(f"    SKIP row {data.get(list(data.keys())[0])}: {e}")
            pg_conn.autocommit = False
    pg_conn.commit()
    print(f"  ✓ {table} done")

# ── Clear existing data ──────────────────────────────────────────────────────
print("\nClearing existing data...")
for t in ["pitstops", "stints", "laps", "drivers", "sessions"]:
    pc.execute(f"TRUNCATE TABLE {t} CASCADE")
pg_conn.commit()

# ── Sessions ─────────────────────────────────────────────────────────────────
print("\nMigrating sessions...")
migrate_table(
    "sessions",
    """INSERT INTO sessions (session_id, year, event_name, session_type, track, country, circuit_key, total_laps, created_at)
       VALUES (%(session_id)s, %(year)s, %(event_name)s, %(session_type)s, %(track)s, %(country)s, %(circuit_key)s, %(total_laps)s, %(created_at)s)
       ON CONFLICT (session_id) DO NOTHING""",
    "SELECT * FROM sessions"
)

# ── Drivers ──────────────────────────────────────────────────────────────────
print("Migrating drivers...")
migrate_table(
    "drivers",
    """INSERT INTO drivers (driver_id, session_id, code, full_name, team, team_color)
       VALUES (%(driver_id)s, %(session_id)s, %(code)s, %(full_name)s, %(team)s, %(team_color)s)
       ON CONFLICT (driver_id) DO NOTHING""",
    "SELECT * FROM drivers"
)

# ── Laps ─────────────────────────────────────────────────────────────────────
print("Migrating laps (this may take a minute)...")
sc.execute("SELECT * FROM laps")
rows = sc.fetchall()
print(f"  {len(rows)} laps to migrate...")
batch = []
for row in rows:
    d = dict(row)
    batch.append(d)
    if len(batch) >= 1000:
        for item in batch:
            try:
                pc.execute("""INSERT INTO laps (lap_id, driver_id, lap_number, lap_time_ms, fuel_corrected_lap_time_ms,
                              sector1_ms, sector2_ms, sector3_ms, compound, tyre_life, stint_number,
                              is_pit_lap, is_valid, track_status, air_temp, track_temp)
                              VALUES (%(lap_id)s, %(driver_id)s, %(lap_number)s, %(lap_time_ms)s, %(fuel_corrected_lap_time_ms)s,
                              %(sector1_ms)s, %(sector2_ms)s, %(sector3_ms)s, %(compound)s, %(tyre_life)s, %(stint_number)s,
                              %(is_pit_lap)s, %(is_valid)s, %(track_status)s, %(air_temp)s, %(track_temp)s)
                              ON CONFLICT (lap_id) DO NOTHING""", item)
            except Exception as e:
                pass
        pg_conn.commit()
        batch = []
        print(f"    ... {rows.index(row)+1}/{len(rows)}")
# remaining batch
for item in batch:
    try:
        pc.execute("""INSERT INTO laps (lap_id, driver_id, lap_number, lap_time_ms, fuel_corrected_lap_time_ms,
                      sector1_ms, sector2_ms, sector3_ms, compound, tyre_life, stint_number,
                      is_pit_lap, is_valid, track_status, air_temp, track_temp)
                      VALUES (%(lap_id)s, %(driver_id)s, %(lap_number)s, %(lap_time_ms)s, %(fuel_corrected_lap_time_ms)s,
                      %(sector1_ms)s, %(sector2_ms)s, %(sector3_ms)s, %(compound)s, %(tyre_life)s, %(stint_number)s,
                      %(is_pit_lap)s, %(is_valid)s, %(track_status)s, %(air_temp)s, %(track_temp)s)
                      ON CONFLICT (lap_id) DO NOTHING""", item)
    except Exception as e:
        pass
pg_conn.commit()
print("  ✓ laps done")

# ── Stints ────────────────────────────────────────────────────────────────────
print("Migrating stints...")
sc.execute("PRAGMA table_info(stints)")
stint_cols = [r[1] for r in sc.fetchall()]
print(f"  stint columns: {stint_cols}")
sc.execute("SELECT * FROM stints")
rows = sc.fetchall()
for row in rows:
    d = dict(row)
    try:
        pc.execute("""INSERT INTO stints (stint_id, driver_id, session_id, stint_number, compound, start_lap, end_lap)
                      VALUES (%(stint_id)s, %(driver_id)s, %(session_id)s, %(stint_number)s, %(compound)s, %(start_lap)s, %(end_lap)s)
                      ON CONFLICT (stint_id) DO NOTHING""", d)
    except Exception as e:
        pass
pg_conn.commit()
print("  ✓ stints done")

# ── Pitstops ──────────────────────────────────────────────────────────────────
print("Migrating pitstops...")
sc.execute("PRAGMA table_info(pitstops)")
pit_cols = [r[1] for r in sc.fetchall()]
print(f"  pitstop columns: {pit_cols}")
sc.execute("SELECT * FROM pitstops")
rows = sc.fetchall()
for row in rows:
    d = dict(row)
    try:
        pc.execute("""INSERT INTO pitstops (pitstop_id, driver_id, session_id, lap_number, duration_ms)
                      VALUES (%(pitstop_id)s, %(driver_id)s, %(session_id)s, %(lap_number)s, %(duration_ms)s)
                      ON CONFLICT (pitstop_id) DO NOTHING""", d)
    except Exception as e:
        pass
pg_conn.commit()
print("  ✓ pitstops done")

# ── Verify ────────────────────────────────────────────────────────────────────
print("\n✅ Migration complete! Verifying...")
for table in ["sessions", "drivers", "laps", "stints", "pitstops"]:
    pc.execute(f"SELECT COUNT(*) FROM {table}")
    count = pc.fetchone()[0]
    print(f"  {table}: {count} rows in PostgreSQL")

sqlite_conn.close()
pg_conn.close()
print("\n🏎️  All done! Your production database is populated.")
