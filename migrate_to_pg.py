"""Direct psycopg2 COPY migration - fastest possible, standard privileges."""
import sys
import io
import sqlite3
import psycopg2

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SQLITE = "f1_telemetry.db"
PG_DSN = (
    "host=dpg-d9bngujbc2fs73eg2oj0-a.singapore-postgres.render.com "
    "dbname=f1_telemetry_xhv3 "
    "user=f1user "
    "password=RuLlNmXxzLY8LMNTzA3I6iZ5QU3NBXqU "
    "connect_timeout=30"
)

print("Connecting...")
sl = sqlite3.connect(SQLITE)
sl.row_factory = sqlite3.Row
sc = sl.cursor()
pg = psycopg2.connect(PG_DSN)
pc = pg.cursor()
pg.autocommit = False

# Truncate laps, stints, pitstops
print("Truncating laps, stints, pitstops...")
pc.execute("TRUNCATE TABLE pitstops, stints, laps RESTART IDENTITY CASCADE;")
pg.commit()

# -- LAPS using COPY FROM --
print("Loading all laps from SQLite...")
sc.execute("SELECT lap_id, driver_id, lap_number, lap_time_ms, "
           "fuel_corrected_lap_time_ms, sector1_ms, sector2_ms, sector3_ms, "
           "compound, tyre_life, stint_number, is_pit_lap, is_valid, "
           "track_status, air_temp, track_temp FROM laps")

rows = sc.fetchall()
print(f"  {len(rows):,} laps to upload via COPY...")

# Build CSV buffer
buf = io.StringIO()
for r in rows:
    parts = []
    for val in r:
        if val is None:
            parts.append("\\N")
        else:
            parts.append(str(val).replace("\t", " ").replace("\n", " "))
    buf.write("\t".join(parts) + "\n")

buf.seek(0)
pc.copy_from(
    buf,
    "laps",
    columns=("lap_id", "driver_id", "lap_number", "lap_time_ms",
             "fuel_corrected_lap_time_ms", "sector1_ms", "sector2_ms",
             "sector3_ms", "compound", "tyre_life", "stint_number",
             "is_pit_lap", "is_valid", "track_status", "air_temp", "track_temp"),
    sep="\t",
    null="\\N"
)
pg.commit()
pc.execute("SELECT COUNT(*) FROM laps")
print(f"  LAPS DONE: {pc.fetchone()[0]:,} rows in production")

# -- STINTS --
print("Loading stints...")
sc.execute("SELECT stint_id, driver_id, session_id, stint_number, compound, "
           "start_lap, end_lap FROM stints")
buf2 = io.StringIO()
for r in sc.fetchall():
    parts = ["\\N" if v is None else str(v).replace("\t", " ") for v in r]
    buf2.write("\t".join(parts) + "\n")
buf2.seek(0)
pc.copy_from(buf2, "stints",
             columns=("stint_id", "driver_id", "session_id", "stint_number",
                      "compound", "start_lap", "end_lap"),
             sep="\t", null="\\N")
pg.commit()
pc.execute("SELECT COUNT(*) FROM stints")
print(f"  STINTS DONE: {pc.fetchone()[0]:,} rows in production")

# -- PITSTOPS --
print("Loading pitstops...")
sc.execute("SELECT pitstop_id, driver_id, session_id, lap_number, duration_ms FROM pitstops")
buf3 = io.StringIO()
for r in sc.fetchall():
    parts = ["\\N" if v is None else str(v).replace("\t", " ") for v in r]
    buf3.write("\t".join(parts) + "\n")
buf3.seek(0)
pc.copy_from(buf3, "pitstops",
             columns=("pitstop_id", "driver_id", "session_id", "lap_number", "duration_ms"),
             sep="\t", null="\\N")
pg.commit()
pc.execute("SELECT COUNT(*) FROM pitstops")
print(f"  PITSTOPS DONE: {pc.fetchone()[0]:,} rows in production")

# Reset sequences
print("Resetting sequences...")
for table, pk in [("laps", "lap_id"), ("stints", "stint_id"), ("pitstops", "pitstop_id")]:
    pc.execute(
        f"SELECT setval(pg_get_serial_sequence('{table}', '{pk}'), "
        f"(SELECT MAX({pk}) FROM {table}))"
    )
pg.commit()

# Final report
pc.execute("SELECT pg_size_pretty(pg_database_size(current_database()))")
size = pc.fetchone()[0]
pc.execute("SELECT pg_database_size(current_database())")
size_bytes = pc.fetchone()[0]

print("\n" + "=" * 50)
print(f"  DB size: {size}")
print(f"  Used: {size_bytes / 1024 / 1024:.1f} MB / 1024 MB")
print(f"  Remaining: {(1024 * 1024 * 1024 - size_bytes) / 1024 / 1024:.0f} MB")
print("  MIGRATION COMPLETE!")
print("=" * 50)

sl.close()
pg.close()
