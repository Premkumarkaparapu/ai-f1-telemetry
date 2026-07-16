"""
Bulk ingest + transform + load for all TARGET_SESSIONS.

Usage (from project root):
    python -m data_pipeline.bulk_load

Safely resumable - sessions already in DB are skipped.
Telemetry is loaded for the top 5 finishers only (for speed).
"""

from data_pipeline.transform import transform_laps, transform_weather
from data_pipeline.ingest import fetch_session, save_raw
from backend.app.database.models import (
    Base, Session, Driver, Lap, TelemetryPoint,
    Weather, Stint, PitStop,
)
from backend.app.database.db import SessionLocal, engine
from backend.app.core.logging import get_logger, setup_logging
from backend.app.core.config import CACHE_DIR, RAW_DIR, TARGET_SESSIONS
from sqlalchemy.orm import Session as DBSession
import fastf1
import pandas as pd
import os
import pickle
import sys
import traceback
from pathlib import Path

# Force UTF-8 output on Windows
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


setup_logging("bulk_load.log")
logger = get_logger(__name__)

CACHE_DIR.mkdir(parents=True, exist_ok=True)
fastf1.Cache.enable_cache(str(CACHE_DIR))

FUEL_MS_PER_LAP = 55    # 0.055s per lap fuel burn correction
INTERVAL_MS = 200   # 5 Hz telemetry downsample
MAX_TEL_DRIVERS = 20   # load telemetry for ALL drivers per session


def _safe(val):
    """Return val if not NaN/None, else None."""
    try:
        return None if pd.isna(val) else val
    except (TypeError, ValueError):
        return val


def session_in_db(db, year, event, stype):
    return db.query(Session).filter(
        Session.year == year,
        Session.event_name == event,
        Session.session_type == stype,
    ).first() is not None


def load_to_db(ff1: fastf1.core.Session, year: int, event: str, stype: str, db: DBSession):
    ei = ff1.event
    track = str(ei.get("Location", ei.get("EventName", event)))
    country = str(ei.get("Country", ""))
    total_laps = int(ff1.laps["LapNumber"].max()) if not ff1.laps.empty else 0

    # Session row
    sess = Session(year=year, event_name=event, session_type=stype,
                   track=track, country=country, total_laps=total_laps)
    db.add(sess)
    db.flush()
    sid = sess.session_id
    logger.info("Session %d: %d %s %s  [%d laps total]", sid, year, event, stype, total_laps)

    # Drivers
    driver_map: dict[str, int] = {}
    for drv_num in ff1.laps["DriverNumber"].dropna().unique():
        k = str(int(drv_num))
        try:
            info = ff1.get_driver(k)
            code = str(info.get("Abbreviation", k))
            full_name = str(info.get("FullName", code))
            team = str(info.get("TeamName", ""))
            tc = str(info.get("TeamColor", "888888")).lstrip("#")
            team_color = "#" + tc if tc else "#888888"
        except Exception:
            code = k
            full_name = k
            team = ""
            team_color = "#888888"
        drv = Driver(
            session_id=sid,
            code=code,
            full_name=full_name,
            team=team,
            team_color=team_color)
        db.add(drv)
        db.flush()
        driver_map[k] = drv.driver_id
    logger.info("  Drivers: %d", len(driver_map))

    # Laps
    laps_df = transform_laps(ff1)
    lap_id_map: dict[tuple, int] = {}
    for _, r in laps_df.iterrows():
        k = str(int(r["DriverNumber"])) if _safe(r.get("DriverNumber")) is not None else None
        did = driver_map.get(k)
        if did is None:
            continue
        lap_num = int(r["LapNumber"]) if _safe(r.get("LapNumber")) is not None else 0
        lt_ms = int(r["lap_time_ms"]) if _safe(r.get("lap_time_ms")) is not None else None
        fc_raw = r.get("fuel_corrected_lap_time_ms")
        fc_ms = int(r["fuel_corrected_lap_time_ms"]) if _safe(fc_raw) is not None else (
            (lt_ms + FUEL_MS_PER_LAP * max(0, lap_num - 1)) if lt_ms else None)
        lap = Lap(
            driver_id=did,
            lap_number=lap_num,
            lap_time_ms=lt_ms,
            fuel_corrected_lap_time_ms=fc_ms,
            sector1_ms=int(
                r["sector1_ms"]) if _safe(
                r.get("sector1_ms")) is not None else None,
            sector2_ms=int(
                r["sector2_ms"]) if _safe(
                    r.get("sector2_ms")) is not None else None,
            sector3_ms=int(
                r["sector3_ms"]) if _safe(
                r.get("sector3_ms")) is not None else None,
            compound=str(
                r.get(
                    "compound",
                    "UNKNOWN")),
            tyre_life=int(
                r["tyre_life"]) if _safe(
                r.get("tyre_life")) is not None else None,
            stint_number=int(
                r["stint_number"]) if _safe(
                r.get("stint_number")) is not None else None,
            is_pit_lap=bool(
                r.get(
                    "is_pit_lap",
                    False)),
            is_valid=bool(
                r.get(
                    "is_valid",
                    True)),
        )
        db.add(lap)
        db.flush()
        lap_id_map[(k, lap_num)] = lap.lap_id
    logger.info("  Laps: %d", len(lap_id_map))

    # Weather (sampled ~60 points)
    wx_df = transform_weather(ff1)
    step = max(1, len(wx_df) // 60)
    wx_count = 0
    for i, (_, r) in enumerate(wx_df.iterrows()):
        if i % step != 0:
            continue
        db.add(Weather(
            session_id=sid,
            time_ms=int(r["time_ms"]) if _safe(r.get("time_ms")) is not None else None,
            air_temp=float(r["air_temp"]) if _safe(r.get("air_temp")) is not None else None,
            track_temp=float(r["track_temp"]) if _safe(r.get("track_temp")) is not None else None,
            humidity=float(r["humidity"]) if _safe(r.get("humidity")) is not None else None,
            pressure=float(r["pressure"]) if _safe(r.get("pressure")) is not None else None,
            wind_speed=float(r["wind_speed"]) if _safe(r.get("wind_speed")) is not None else None,
            wind_dir=float(r["wind_dir"]) if _safe(r.get("wind_dir")) is not None else None,
            rainfall=bool(r.get("rainfall", False)),
        ))
        wx_count += 1
    logger.info("  Weather: %d points", wx_count)

    # Stints
    try:
        stint_df = ff1.laps[["DriverNumber", "Stint", "Compound", "LapNumber"]].dropna(subset=[
                                                                                       "Stint"])
        for (drv_raw, stint_num), g in stint_df.groupby(["DriverNumber", "Stint"]):
            k = str(int(drv_raw))
            did = driver_map.get(k)
            if not did:
                continue
            db.add(Stint(driver_id=did, session_id=sid, stint_number=int(stint_num),
                         compound=str(g["Compound"].iloc[0]).upper(),
                         start_lap=int(g["LapNumber"].min()), end_lap=int(g["LapNumber"].max())))
        logger.info("  Stints: inserted")
    except Exception as e:
        logger.warning("  Stints skipped: %s", e)

    # Pit stops
    try:
        pit_laps = ff1.laps[ff1.laps["PitInTime"].notna()].copy()
        for _, r in pit_laps.iterrows():
            k = str(int(r["DriverNumber"]))
            did = driver_map.get(k)
            if not did:
                continue
            dur = None
            if _safe(r.get("PitInTime")) is not None and _safe(r.get("PitOutTime")) is not None:
                d = r["PitOutTime"] - r["PitInTime"]
                dur = int(d.total_seconds() * 1000) if not pd.isna(d) else None
            db.add(
                PitStop(
                    driver_id=did,
                    session_id=sid,
                    lap_number=int(
                        r["LapNumber"]),
                    duration_ms=dur))
        logger.info("  Pit stops: inserted")
    except Exception as e:
        logger.warning("  Pit stops skipped: %s", e)

    # Telemetry — fastest lap for top MAX_TEL_DRIVERS drivers only
    logger.info("  Telemetry: loading for top %d drivers...", MAX_TEL_DRIVERS)
    tel_total = 0

    # Sort drivers by their best valid lap time — take fastest MAX_TEL_DRIVERS
    best_times = {}
    for k in driver_map:
        try:
            drv_laps = ff1.laps.pick_driver(k)
            valid = drv_laps[drv_laps["LapTime"].notna()]
            if not valid.empty:
                best_times[k] = valid["LapTime"].min()
        except Exception:
            pass
    top_drivers = sorted(best_times, key=lambda k: best_times[k])[:MAX_TEL_DRIVERS]

    for drv_num in top_drivers:
        did = driver_map[drv_num]
        try:
            drv_laps = ff1.laps.pick_driver(drv_num)
            valid = drv_laps[drv_laps["LapTime"].notna()]
            fastest = valid.loc[valid["LapTime"].idxmin()]
            lap_num = int(fastest["LapNumber"])
            lap_id = lap_id_map.get((str(drv_num), lap_num))
            if not lap_id:
                continue

            # Skip if telemetry already in DB for this lap
            existing = db.query(TelemetryPoint).filter(TelemetryPoint.lap_id == lap_id).count()
            if existing > 0:
                logger.info(
                    "    Driver %s: already has %d telemetry pts, skipping",
                    drv_num,
                    existing)
                tel_total += existing
                continue

            tel = fastest.get_telemetry()
            if tel.empty:
                continue

            tel["_tms"] = tel["SessionTime"].apply(
                lambda t: int(t.total_seconds() * 1000) if not pd.isna(t) else None)
            tel["_bin"] = (tel["_tms"] // INTERVAL_MS) * INTERVAL_MS

            agg = {c: ("mean" if c in ("Speed", "RPM", "Throttle") else "last")
                   for c in (
                       "Distance", "Speed", "RPM", "nGear",
                       "Throttle", "Brake", "DRS", "X", "Y", "Z"
                   )
                   if c in tel.columns}
            tel_s = tel.groupby("_bin").agg(agg).reset_index()

            for _, pt in tel_s.iterrows():
                db.add(TelemetryPoint(
                    lap_id=lap_id,
                    session_id=sid,
                    time_ms=int(pt["_bin"]),
                    distance_m=(
                        float(pt["Distance"]) if _safe(pt.get("Distance")) is not None
                        else None
                    ),
                    speed_kmh=float(pt["Speed"]) if _safe(pt.get("Speed")) is not None else None,
                    rpm=float(pt["RPM"]) if _safe(pt.get("RPM")) is not None else None,
                    gear=int(pt["nGear"]) if _safe(pt.get("nGear")) is not None else None,
                    throttle_pct=(
                        float(pt["Throttle"]) if _safe(pt.get("Throttle")) is not None
                        else None
                    ),
                    brake=(
                        bool(int(pt["Brake"]) > 0) if _safe(pt.get("Brake")) is not None
                        else False
                    ),
                    drs=bool(int(pt["DRS"]) > 8) if _safe(pt.get("DRS")) is not None else False,
                    x=float(pt["X"]) if _safe(pt.get("X")) is not None else None,
                    y=float(pt["Y"]) if _safe(pt.get("Y")) is not None else None,
                    z=float(pt["Z"]) if _safe(pt.get("Z")) is not None else None,
                ))
            tel_total += len(tel_s)
            logger.info("    Driver %s: %d telemetry points", drv_num, len(tel_s))
        except Exception as e:
            logger.warning("    Telemetry driver %s skipped: %s", drv_num, e)

    logger.info("  Telemetry total: %d points", tel_total)
    db.commit()
    logger.info("  COMMITTED: %d %s %s", year, event, stype)


def bulk_load():
    Base.metadata.create_all(bind=engine, checkfirst=True)
    db = SessionLocal()
    ok, skipped, failed = [], [], []

    try:
        for year, event, stype in TARGET_SESSIONS:
            label = f"{year} {event} [{stype}]"
            if session_in_db(db, year, event, stype):
                logger.info("SKIP (already in DB): %s", label)
                skipped.append(label)
                continue

            logger.info("=" * 55)
            logger.info("INGESTING: %s", label)
            try:
                slug = f"{year}_{event.replace(' ', '_')}_{stype}.pkl"
                raw_path = RAW_DIR / slug
                if raw_path.exists():
                    logger.info("  Using disk cache: %s", raw_path.name)
                    with open(raw_path, "rb") as f:
                        ff1 = pickle.load(f)
                else:
                    logger.info("  Fetching from FastF1...")
                    ff1 = fetch_session(year, event, stype)
                    save_raw(ff1, year, event, stype)

                load_to_db(ff1, year, event, stype, db)
                ok.append(label)
                print(f"[OK] {label}")
            except Exception as exc:
                db.rollback()
                logger.error("FAILED %s: %s", label, exc)
                traceback.print_exc()
                failed.append(f"{label}: {exc}")
                print(f"[FAIL] {label}: {exc}")
    finally:
        db.close()

    print("\n" + "=" * 55)
    print("BULK LOAD SUMMARY")
    print(f"  Loaded:  {len(ok)}")
    for s in ok:
        print(f"    OK   {s}")
    print(f"  Skipped: {len(skipped)}")
    for s in skipped:
        print(f"    SKIP {s}")
    print(f"  Failed:  {len(failed)}")
    for s in failed:
        print(f"    FAIL {s}")
    print("=" * 55)


if __name__ == "__main__":
    bulk_load()
