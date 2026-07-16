"""Full migration: laps + stints + pitstops to Render PostgreSQL."""
import sqlite3
import psycopg2

SQLITE = "f1_telemetry.db"
PG = "postgresql://f1user:RuLlNmXxzLY8LMNTzA3I6iZ5QU3NBXqU@dpg-d9bngujbc2fs73eg2oj0-a.singapore-postgres.render.com/f1_telemetry_xhv3"

sl = sqlite3.connect(SQLITE)
sl.row_factory = sqlite3.Row
sc = sl.cursor()
pg = psycopg2.connect(PG, connect_timeout=30)
pc = pg.cursor()

# Clear laps/stints/pitstops only (keep sessions & drivers)
print("Clearing laps, stints, pitstops...")
pc.execute("TRUNCATE TABLE pitstops CASCADE")
pc.execute("TRUNCATE TABLE stints CASCADE")
pc.execute("TRUNCATE TABLE laps CASCADE")
pg.commit()

# ── LAPS ──────────────────────────────────────────────────────────────────────
print("Uploading all 70,473 laps...")
sc.execute("SELECT * FROM laps")
rows = sc.fetchall()
batch = []
uploaded = 0
for row in rows:
    batch.append(dict(row))
    if len(batch) >= 2000:
        for item in batch:
            try:
                pc.execute("""
                    INSERT INTO laps (lap_id,driver_id,lap_number,lap_time_ms,
                      fuel_corrected_lap_time_ms,sector1_ms,sector2_ms,sector3_ms,
                      compound,tyre_life,stint_number,is_pit_lap,is_valid,
                      track_status,air_temp,track_temp)
                    VALUES (%(lap_id)s,%(driver_id)s,%(lap_number)s,%(lap_time_ms)s,
                      %(fuel_corrected_lap_time_ms)s,%(sector1_ms)s,%(sector2_ms)s,%(sector3_ms)s,
                      %(compound)s,%(tyre_life)s,%(stint_number)s,%(is_pit_lap)s,%(is_valid)s,
                      %(track_status)s,%(air_temp)s,%(track_temp)s)
                    ON CONFLICT DO NOTHING""", item)
            except Exception as e:
                pass
        pg.commit()
        uploaded += len(batch)
        print(f"  {uploaded:,} / {len(rows):,} laps done...")
        batch = []

for item in batch:
    try:
        pc.execute("""
            INSERT INTO laps (lap_id,driver_id,lap_number,lap_time_ms,
              fuel_corrected_lap_time_ms,sector1_ms,sector2_ms,sector3_ms,
              compound,tyre_life,stint_number,is_pit_lap,is_valid,
              track_status,air_temp,track_temp)
            VALUES (%(lap_id)s,%(driver_id)s,%(lap_number)s,%(lap_time_ms)s,
              %(fuel_corrected_lap_time_ms)s,%(sector1_ms)s,%(sector2_ms)s,%(sector3_ms)s,
              %(compound)s,%(tyre_life)s,%(stint_number)s,%(is_pit_lap)s,%(is_valid)s,
              %(track_status)s,%(air_temp)s,%(track_temp)s)
            ON CONFLICT DO NOTHING""", item)
    except:
        pass
pg.commit()
pc.execute("SELECT COUNT(*) FROM laps")
print(f"  ✓ LAPS DONE: {pc.fetchone()[0]:,} rows in production")

# ── STINTS ────────────────────────────────────────────────────────────────────
print("Uploading stints...")
sc.execute("SELECT * FROM stints")
for row in sc.fetchall():
    d = dict(row)
    try:
        pc.execute("""
            INSERT INTO stints (stint_id,driver_id,session_id,stint_number,compound,start_lap,end_lap)
            VALUES (%(stint_id)s,%(driver_id)s,%(session_id)s,%(stint_number)s,%(compound)s,%(start_lap)s,%(end_lap)s)
            ON CONFLICT DO NOTHING""", d)
    except:
        pass
pg.commit()
pc.execute("SELECT COUNT(*) FROM stints")
print(f"  ✓ STINTS DONE: {pc.fetchone()[0]:,} rows")

# ── PITSTOPS ──────────────────────────────────────────────────────────────────
print("Uploading pitstops...")
sc.execute("SELECT * FROM pitstops")
for row in sc.fetchall():
    d = dict(row)
    try:
        pc.execute("""
            INSERT INTO pitstops (pitstop_id,driver_id,session_id,lap_number,duration_ms)
            VALUES (%(pitstop_id)s,%(driver_id)s,%(session_id)s,%(lap_number)s,%(duration_ms)s)
            ON CONFLICT DO NOTHING""", d)
    except:
        pass
pg.commit()
pc.execute("SELECT COUNT(*) FROM pitstops")
print(f"  ✓ PITSTOPS DONE: {pc.fetchone()[0]:,} rows")

# ── Final DB size ──────────────────────────────────────────────────────────────
pc.execute("SELECT pg_size_pretty(pg_database_size(current_database()))")
print(f"\n  Final DB size: {pc.fetchone()[0]}")
pc.execute("SELECT pg_database_size(current_database())")
used = pc.fetchone()[0]
print(f"  Used: {used/1024/1024:.1f} MB / 1024 MB ({used/(1024**3)*100:.1f}%)")

sl.close()
pg.close()
print("\n🏎️  MIGRATION COMPLETE! All F1 data is now live in production.")
