"""
Download and ingest ALL session types for 2025 and 2026 F1 seasons.

Session types: Race (R), Qualifying (Q), Sprint (S), Sprint Qualifying (SQ),
               FP1, FP2, FP3

Usage:
  python data_pipeline/ingest_all_sessions.py [--year 2025] [--year 2026] [--dry-run]

Skips sessions already in DB and pickles that already exist.
"""
import sys, os, argparse
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = str(__import__("pathlib").Path(__file__).resolve().parents[1])
sys.path.insert(0, ROOT)

import pandas as pd
import fastf1
from pathlib import Path
from datetime import datetime

# ── Config ────────────────────────────────────────────────────────────────────
RAW_DIR   = Path(ROOT) / "data_pipeline" / "raw"
CACHE_DIR = Path(ROOT) / "data_pipeline" / "cache"
RAW_DIR.mkdir(exist_ok=True)
CACHE_DIR.mkdir(exist_ok=True)
fastf1.Cache.enable_cache(str(CACHE_DIR))

INTERVAL_MS   = 200   # 5 Hz telemetry downsample
FUEL_MS_PER_LAP = 55

# All session identifiers FastF1 understands
ALL_SESSION_TYPES = ["FP1", "FP2", "FP3", "Q", "SQ", "S", "R"]
SESSION_TYPE_LABELS = {
    "R":  "Race", "Q":  "Qualifying", "S":  "Sprint",
    "SQ": "Sprint Qualifying", "FP1": "Practice 1",
    "FP2": "Practice 2", "FP3": "Practice 3",
}

# Sprint weekends by year — match against FastF1's official EventName strings
SPRINT_EVENTS_2025 = ["Chinese", "Miami", "United States", "São Paulo", "Qatar", "Belgian"]
SPRINT_EVENTS_2026 = ["Bahrain", "Miami", "Chinese", "São Paulo", "Qatar"]


def _safe(val):
    try:
        if val is None: return None
        if isinstance(val, float) and pd.isna(val): return None
        return val
    except: return None

def ms(td):
    """Convert timedelta to ms int."""
    try:
        if pd.isna(td): return None
        return int(td.total_seconds() * 1000)
    except: return None


def get_session_types_for_event(year, event_name):
    """Return applicable session types for this event."""
    sprint_events = SPRINT_EVENTS_2025 if year == 2025 else SPRINT_EVENTS_2026
    has_sprint = any(s.lower() in event_name.lower() for s in sprint_events)
    if has_sprint:
        return ["FP1", "SQ", "S", "Q", "R"]   # Sprint weekends: FP1, SQ, Sprint, Q, Race
    return ["FP1", "FP2", "FP3", "Q", "R"]

def download_session(year, event_name, session_type):
    """Load FastF1 session using FastF1's own cache. Returns ff1 session or None."""
    print(f"    [{session_type}] Loading via FastF1 (cache: {CACHE_DIR.name})...")
    try:
        schedule = fastf1.get_event_schedule(year, include_testing=False)
        event_row = schedule[schedule["EventName"].str.contains(
            event_name.replace(" Grand Prix", "").strip(), case=False, na=False)]
        if event_row.empty:
            print(f"    [{session_type}] Event not found in {year} schedule")
            return None

        ff1 = fastf1.get_session(year, event_row.iloc[0]["EventName"], session_type)
        ff1.load(telemetry=True, weather=True, messages=False, laps=True)

        # Validate: must have usable laps
        try:
            laps = ff1.laps
            if laps is None or len(laps) == 0:
                print(f"    [{session_type}] No laps found — skipping")
                return None
            print(f"    [{session_type}] Loaded OK — {len(laps)} laps, {len(ff1.drivers)} drivers")
        except Exception as ve:
            print(f"    [{session_type}] Validation failed: {ve}")
            return None

        return ff1
    except Exception as e:
        print(f"    [{session_type}] FAILED: {e}")
        return None


def ingest_session(ff1, year, event_name, session_type, db):
    """Ingest a FastF1 session into the database."""
    from backend.app.database.models import (
        Session, Driver, Lap, TelemetryPoint, Weather, Stint, PitStop
    )

    track = None
    try:
        track = str(ff1.event.get("Location", "")) or str(ff1.event.get("Country", ""))
    except: pass

    # Check if session already in DB
    existing = db.query(Session).filter(
        Session.year == year,
        Session.event_name == event_name,
        Session.session_type == session_type,
    ).first()

    if existing:
        print(f"    [{session_type}] Already in DB (session_id={existing.session_id}), checking missing drivers...")
        sess = existing
    else:
        sess = Session(
            year=year, event_name=event_name, session_type=session_type, track=track,
        )
        db.add(sess)
        db.flush()
        print(f"    [{session_type}] Created session_id={sess.session_id}")

    sid = sess.session_id

    # ── Drivers ──────────────────────────────────────────────────────────────
    existing_codes = {d.code for d in db.query(Driver).filter(Driver.session_id == sid).all()}
    driver_map = {}  # str(number) -> driver_id

    try:
        results = ff1.results
        for _, row in results.iterrows():
            num_str = str(int(row["DriverNumber"])) if _safe(row.get("DriverNumber")) is not None else None
            code    = str(row.get("Abbreviation", "UNK")).strip().upper()
            if not num_str or code in existing_codes:
                if code in existing_codes:
                    # Find existing driver_id
                    drv = db.query(Driver).filter(Driver.session_id == sid, Driver.code == code).first()
                    if drv: driver_map[num_str] = drv.driver_id
                continue
            full_name   = str(row.get("FullName", ""))
            team        = str(row.get("TeamName", ""))
            team_color  = str(row.get("TeamColor", ""))
            if team_color and not team_color.startswith("#"):
                team_color = f"#{team_color}"
            drv = Driver(
                session_id=sid, code=code, full_name=full_name,
                team=team, team_color=team_color if team_color != "#" else None,
            )
            db.add(drv)
            db.flush()
            driver_map[num_str] = drv.driver_id
            existing_codes.add(code)
    except Exception as e:
        print(f"    [{session_type}] Drivers error: {e}")

    # Also build reverse map: code -> driver_id for existing drivers
    for drv in db.query(Driver).filter(Driver.session_id == sid).all():
        # Try to find the driver number from FastF1 results
        try:
            row = results[results["Abbreviation"].str.upper() == drv.code]
            if not row.empty:
                num_str = str(int(row.iloc[0]["DriverNumber"]))
                driver_map[num_str] = drv.driver_id
        except: pass

    print(f"    [{session_type}] {len(driver_map)} drivers mapped")

    # ── Laps ─────────────────────────────────────────────────────────────────
    laps_df     = ff1.laps
    lap_id_map  = {}  # (drv_num_str, lap_num) -> lap_id

    # Load existing lap IDs
    for did in driver_map.values():
        for lap in db.query(Lap).filter(Lap.driver_id == did).all():
            k = None
            for num_str, d_id in driver_map.items():
                if d_id == did:
                    k = (num_str, lap.lap_number)
                    break
            if k:
                lap_id_map[k] = lap.lap_id

    new_laps = 0
    for _, lrow in laps_df.iterrows():
        drv_num = str(int(lrow["DriverNumber"])) if _safe(lrow.get("DriverNumber")) is not None else None
        did = driver_map.get(drv_num) if drv_num else None
        if not did: continue
        lap_num = int(lrow["LapNumber"]) if _safe(lrow.get("LapNumber")) is not None else None
        if not lap_num: continue
        k = (drv_num, lap_num)
        if k in lap_id_map: continue  # Already stored

        lt = ms(lrow.get("LapTime"))
        s1 = ms(lrow.get("Sector1Time"))
        s2 = ms(lrow.get("Sector2Time"))
        s3 = ms(lrow.get("Sector3Time"))
        fuel_corr = lt - int(FUEL_MS_PER_LAP * lap_num) if lt else None

        compound = str(lrow.get("Compound", "")).upper()
        if not compound or compound == "NAN" or compound == "NONE": compound = None

        is_valid = bool(lrow.get("IsAccurate", True))
        is_pit   = bool(_safe(lrow.get("PitInTime")) is not None)
        tyre_life= int(lrow["TyreLife"]) if _safe(lrow.get("TyreLife")) is not None else None
        stint    = int(lrow["Stint"])    if _safe(lrow.get("Stint"))    is not None else None

        lap = Lap(
            driver_id=did,
            lap_number=lap_num, lap_time_ms=lt, fuel_corrected_lap_time_ms=fuel_corr,
            sector1_ms=s1, sector2_ms=s2, sector3_ms=s3,
            compound=compound, tyre_life=tyre_life, stint_number=stint,
            is_pit_lap=is_pit, is_valid=is_valid,
        )
        db.add(lap)
        db.flush()
        lap_id_map[k] = lap.lap_id
        new_laps += 1

    print(f"    [{session_type}] {new_laps} new laps added")

    # ── COMMIT drivers + laps now so telemetry rollbacks don't wipe them ─────
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"    [{session_type}] Commit error after laps: {e}")
        return {"laps": 0, "tel": 0}

    # ── Telemetry (fastest lap per driver) ───────────────────────────────────
    tel_added = 0
    for drv_num, did in driver_map.items():
        try:
            drv_laps = laps_df[laps_df["DriverNumber"].astype(str).apply(lambda x: str(int(float(x))) if x.replace('.','').isdigit() else x) == drv_num]
            valid    = drv_laps[drv_laps["LapTime"].notna()]
            if valid.empty: continue
            fastest  = valid.loc[valid["LapTime"].idxmin()]
            lap_num  = int(fastest["LapNumber"])
            lap_id   = lap_id_map.get((drv_num, lap_num))
            if not lap_id: continue

            # Skip if already has telemetry
            existing_tel = db.query(TelemetryPoint).filter(TelemetryPoint.lap_id == lap_id).count()
            if existing_tel > 0: continue

            tel = fastest.get_telemetry()
            if tel is None or tel.empty: continue

            tel = tel.copy()
            tel["_tms"] = tel["SessionTime"].apply(
                lambda t: int(t.total_seconds() * 1000) if pd.notna(t) else None)
            tel = tel[tel["_tms"].notna()]
            tel["_bin"] = (tel["_tms"] // INTERVAL_MS) * INTERVAL_MS

            agg = {c: ("mean" if c in ("Speed","RPM","Throttle") else "last")
                   for c in ("Distance","Speed","RPM","nGear","Throttle","Brake","DRS","X","Y","Z")
                   if c in tel.columns}
            tel_s = tel.groupby("_bin").agg(agg).reset_index()

            points = []
            for _, pt in tel_s.iterrows():
                def v(col):
                    val = pt.get(col)
                    return None if (val is None or (isinstance(val, float) and pd.isna(val))) else val
                brake_raw = v("Brake"); drs_raw = v("DRS")
                points.append(TelemetryPoint(
                    lap_id=lap_id, session_id=sid, time_ms=int(pt["_bin"]),
                    distance_m  = float(v("Distance")) if v("Distance") is not None else None,
                    speed_kmh   = float(v("Speed"))    if v("Speed")    is not None else None,
                    rpm         = float(v("RPM"))      if v("RPM")      is not None else None,
                    gear        = float(v("nGear"))    if v("nGear")    is not None else None,
                    throttle_pct= float(v("Throttle")) if v("Throttle") is not None else None,
                    brake       = bool(int(brake_raw) > 0) if brake_raw is not None else False,
                    drs         = bool(int(drs_raw)   > 8) if drs_raw   is not None else False,
                    x           = float(v("X"))        if v("X")        is not None else None,
                    y           = float(v("Y"))        if v("Y")        is not None else None,
                    z           = float(v("Z"))        if v("Z")        is not None else None,
                ))
            db.bulk_save_objects(points)
            db.commit()   # commit per-driver so one failure doesn't affect others
            tel_added += len(points)
        except Exception as e:
            db.rollback()  # safe now — drivers/laps are already committed above
            print(f"    [{session_type}] Telemetry error for driver {drv_num}: {e}")

    # ── Weather ───────────────────────────────────────────────────────────────
    try:
        wx = ff1.weather_data
        if wx is not None and not wx.empty:
            step = max(1, len(wx) // 60)
            for i, (_, r) in enumerate(wx.iterrows()):
                if i % step != 0: continue
                db.add(Weather(
                    session_id=sid,
                    time_ms   = int(r["Time"].total_seconds()*1000) if _safe(r.get("Time")) is not None else None,
                    air_temp  = float(r["AirTemp"])   if _safe(r.get("AirTemp"))   is not None else None,
                    track_temp= float(r["TrackTemp"]) if _safe(r.get("TrackTemp")) is not None else None,
                    humidity  = float(r["Humidity"])  if _safe(r.get("Humidity"))  is not None else None,
                    rainfall  = bool(r.get("Rainfall", False)),
                ))
    except Exception as e:
        print(f"    [{session_type}] Weather skipped: {e}")

    # ── Stints ────────────────────────────────────────────────────────────────
    try:
        # Load existing stint keys to skip duplicates
        existing_stints = {
            (s.driver_id, s.stint_number)
            for s in db.query(Stint).filter(Stint.session_id == sid).all()
        }
        stint_df = laps_df[["DriverNumber","Stint","Compound","LapNumber"]].dropna(subset=["Stint"])
        for (drv_raw, stint_num), g in stint_df.groupby(["DriverNumber","Stint"]):
            k = str(int(drv_raw)); did = driver_map.get(k)
            if not did: continue
            key = (did, int(stint_num))
            if key in existing_stints: continue          # ← skip duplicates
            db.add(Stint(driver_id=did, session_id=sid,
                stint_number=int(stint_num),
                compound=str(g["Compound"].iloc[0]).upper(),
                start_lap=int(g["LapNumber"].min()), end_lap=int(g["LapNumber"].max())))
            existing_stints.add(key)
    except Exception as e:
        print(f"    [{session_type}] Stints skipped: {e}")

    db.commit()
    print(f"    [{session_type}] ✅ Done — {tel_added} telemetry pts")
    return {"laps": new_laps, "tel": tel_added}


def run(years, session_types_filter=None, dry_run=False):
    from backend.app.database.db import SessionLocal
    from backend.app.database.models import Session
    db = SessionLocal()

    total_sessions = 0
    total_laps     = 0
    total_tel      = 0
    errors         = []

    for year in years:
        print(f"\n{'='*60}")
        print(f"  YEAR: {year}")
        print(f"{'='*60}")

        try:
            schedule = fastf1.get_event_schedule(year, include_testing=False)
        except Exception as e:
            print(f"  ERROR fetching schedule for {year}: {e}")
            continue

        # Filter to events that have already happened
        today     = pd.Timestamp.now()  # timezone-naive to match FastF1 schedule
        past_mask = pd.to_datetime(schedule["EventDate"], utc=False) <= today
        past      = schedule[past_mask]
        print(f"  Events completed so far: {len(past)}")

        for _, event in past.iterrows():
            event_name = str(event["EventName"])
            print(f"\n  📍 {event_name}")

            stypes = get_session_types_for_event(year, event_name)
            if session_types_filter:
                stypes = [s for s in stypes if s in session_types_filter]

            for stype in stypes:
                print(f"  Checking [{stype}] {SESSION_TYPE_LABELS.get(stype, stype)}...")
                if dry_run:
                    print(f"    [DRY RUN] Would download and ingest")
                    continue

                ff1 = download_session(year, event_name, stype)
                if ff1 is None:
                    errors.append(f"{year} {event_name} [{stype}]")
                    continue

                try:
                    result = ingest_session(ff1, year, event_name, stype, db)
                    total_sessions += 1
                    total_laps     += result.get("laps", 0)
                    total_tel      += result.get("tel", 0)
                except Exception as e:
                    db.rollback()
                    print(f"    [{stype}] INGEST ERROR: {e}")
                    errors.append(f"{year} {event_name} [{stype}]: {e}")
                finally:
                    ff1 = None  # Free memory

    db.close()

    print(f"\n{'='*60}")
    print(f"SUMMARY")
    print(f"  Sessions ingested : {total_sessions}")
    print(f"  New laps          : {total_laps:,}")
    print(f"  New telemetry pts : {total_tel:,}")
    if errors:
        print(f"  Errors ({len(errors)}):")
        for e in errors:
            print(f"    ✗ {e}")
    print(f"{'='*60}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest all F1 session types for 2025/2026")
    parser.add_argument("--year",    type=int, action="append", default=[], dest="years")
    parser.add_argument("--type",    type=str, action="append", default=[], dest="types",
                        choices=["R","Q","S","SQ","FP1","FP2","FP3"],
                        help="Session types to ingest (default: all)")
   parser.add_argument(
    "--dry-run", action="store_true",
    help="List what would be done without downloading"
  )
  args = parser.parse_args()


   years = args.years or [2025]
stypes = args.types or None
run(years, stypes, args.dry_run)
