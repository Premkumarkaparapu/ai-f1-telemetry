"""
Fill in telemetry for ALL drivers in all sessions.
Skips any driver whose fastest lap already has telemetry in DB.
Reads from existing FastF1 pickle cache.
"""
import sys, pickle, os
sys.stdout.reconfigure(encoding="utf-8")

import pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]  # project root (one above data_pipeline/)
sys.path.insert(0, str(ROOT))

from backend.app.database.db import SessionLocal
from backend.app.database.models import Session, Driver, Lap, TelemetryPoint
from backend.app.core.logging import get_logger

logger = get_logger(__name__)

RAW_DIR     = ROOT / "data_pipeline" / "raw"
INTERVAL_MS = 200  # 5 Hz

def _safe(val):
    try:
        if val is None: return None
        if isinstance(val, float) and pd.isna(val): return None
        return val
    except: return None

def fill_telemetry():
    db = SessionLocal()
    sessions = db.query(Session).order_by(Session.year, Session.session_id).all()
    print(f"Sessions to process: {len(sessions)}")

    total_added = 0
    total_skipped = 0

    for sess in sessions:
        slug = f"{sess.year}_{sess.event_name.replace(' ', '_')}_{sess.session_type}.pkl"
        pkl_path = RAW_DIR / slug
        if not pkl_path.exists():
            print(f"  SKIP (no pickle): {sess.event_name}")
            continue

        drivers = db.query(Driver).filter(Driver.session_id == sess.session_id).all()
        print(f"\n{sess.year} {sess.event_name} — {len(drivers)} drivers")

        # Load FastF1 session once per session
        ff1 = None

        for drv in drivers:
            # Find fastest valid lap for this driver
            fastest_lap = (db.query(Lap)
                .filter(Lap.driver_id == drv.driver_id, Lap.lap_time_ms.isnot(None), Lap.is_valid == True)
                .order_by(Lap.lap_time_ms)
                .first())
            if not fastest_lap:
                print(f"  {drv.code}: no valid laps, skip")
                continue

            # Check if telemetry already in DB
            existing = db.query(TelemetryPoint).filter(TelemetryPoint.lap_id == fastest_lap.lap_id).count()
            if existing > 0:
                print(f"  {drv.code}: already {existing} pts ✓")
                total_skipped += 1
                continue

            # Load pickle lazily (once per session)
            if ff1 is None:
                print(f"  Loading pickle: {slug} ({pkl_path.stat().st_size // 1024 // 1024} MB)...")
                with open(pkl_path, "rb") as f:
                    ff1 = pickle.load(f)

            # Get telemetry
            try:
                drv_num = drv.code  # FastF1 uses driver numbers, try code first
                # Find driver number from laps
                num_row = ff1.laps[ff1.laps["Driver"] == drv.code]
                if num_row.empty:
                    # Try by number from DB code
                    num_row = ff1.laps[ff1.laps["DriverNumber"].astype(str) == drv.code]
                if num_row.empty:
                    print(f"  {drv.code}: not found in pickle")
                    continue
                drv_num_str = str(int(num_row["DriverNumber"].iloc[0]))

                drv_laps = ff1.laps.pick_driver(drv_num_str)
                valid = drv_laps[drv_laps["LapTime"].notna()]
                if valid.empty:
                    print(f"  {drv.code}: no valid laps in pickle")
                    continue

                # Get the specific fastest lap by lap number
                target_lap = valid[valid["LapNumber"] == fastest_lap.lap_number]
                if target_lap.empty:
                    target_lap = valid.loc[[valid["LapTime"].idxmin()]]

                lap_row = target_lap.iloc[0]
                tel = lap_row.get_telemetry()
                if tel is None or tel.empty:
                    print(f"  {drv.code}: empty telemetry")
                    continue

                tel = tel.copy()
                tel["_tms"] = tel["SessionTime"].apply(
                    lambda t: int(t.total_seconds() * 1000) if pd.notna(t) else None)
                tel = tel[tel["_tms"].notna()]
                tel["_bin"] = (tel["_tms"] // INTERVAL_MS) * INTERVAL_MS

                agg = {c: ("mean" if c in ("Speed", "RPM", "Throttle") else "last")
                       for c in ("Distance", "Speed", "RPM", "nGear", "Throttle", "Brake", "DRS", "X", "Y", "Z")
                       if c in tel.columns}
                tel_s = tel.groupby("_bin").agg(agg).reset_index()

                points = []
                for _, pt in tel_s.iterrows():
                    def v(col):
                        val = pt.get(col)
                        return None if val is None or (isinstance(val, float) and pd.isna(val)) else val

                    brake_raw = v("Brake")
                    drs_raw   = v("DRS")
                    points.append(TelemetryPoint(
                        lap_id      = fastest_lap.lap_id,
                        session_id  = sess.session_id,
                        time_ms     = int(pt["_bin"]),
                        distance_m  = float(v("Distance")) if v("Distance") is not None else None,
                        speed_kmh   = float(v("Speed"))    if v("Speed")    is not None else None,
                        rpm         = float(v("RPM"))      if v("RPM")      is not None else None,
                        gear        = int(v("nGear"))      if v("nGear")    is not None else None,
                        throttle_pct= float(v("Throttle")) if v("Throttle") is not None else None,
                        brake       = bool(int(brake_raw) > 0) if brake_raw is not None else False,
                        drs         = bool(int(drs_raw)   > 8) if drs_raw   is not None else False,
                        x           = float(v("X"))        if v("X")        is not None else None,
                        y           = float(v("Y"))        if v("Y")        is not None else None,
                        z           = float(v("Z"))        if v("Z")        is not None else None,
                    ))

                db.bulk_save_objects(points)
                db.commit()
                print(f"  {drv.code}: added {len(points)} pts ✓")
                total_added += len(points)

            except Exception as e:
                db.rollback()
                print(f"  {drv.code}: FAILED — {e}")

        # Free pickle memory
        ff1 = None

    db.close()
    print(f"\n{'='*50}")
    print(f"DONE — Added {total_added:,} new telemetry points")
    print(f"       Skipped {total_skipped} drivers (already loaded)")
    print(f"{'='*50}")

if __name__ == "__main__":
    fill_telemetry()
