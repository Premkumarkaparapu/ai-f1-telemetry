"""
Data pipeline — Verification Script
Prints row counts and sample records from every table to confirm data loaded correctly.
Always safe to run; makes no writes to the database.

Usage:
    python -m data_pipeline.verify
"""

from backend.app.core.logging import get_logger, setup_logging
from backend.app.database.db import get_pipeline_db
from backend.app.database.models import (
    DatasetMetadata, Session as SessionModel, Driver,
    Lap, TelemetryPoint, Weather, Stint, Tyre, PitStop, Prediction,
)

setup_logging("pipeline.log")
logger = get_logger(__name__)

TABLES = [
    ("DatasetMetadata", DatasetMetadata),
    ("Sessions",        SessionModel),
    ("Drivers",         Driver),
    ("Laps",            Lap),
    ("TelemetryPoints", TelemetryPoint),
    ("Weather",         Weather),
    ("Stints",          Stint),
    ("Tyres",           Tyre),
    ("PitStops",        PitStop),
    ("Predictions",     Prediction),
]


def verify() -> bool:
    """Print row counts for every table. Returns True if all expected tables have data."""
    print("\n" + "=" * 60)
    print("  AI F1 Telemetry Platform — Database Verification")
    print("=" * 60)

    all_ok = True

    with get_pipeline_db() as db:
        for label, model in TABLES:
            count = db.query(model).count()
            status = "✓" if count > 0 else "✗ EMPTY"
            print(f"  {label:<20} {count:>8,} rows   {status}")
            if count == 0 and label not in ("Predictions",):  # Predictions are optional at this stage
                all_ok = False

        print("-" * 60)

        # Sample a session and a lap for quick sanity check
        session = db.query(SessionModel).first()
        if session:
            print(f"\n  Sample session: {session.year} {session.event_name} ({session.session_type})")
            print(f"    Track: {session.track}, Country: {session.country}")

        lap = db.query(Lap).filter(Lap.lap_time_ms.isnot(None)).first()
        if lap:
            print(f"\n  Sample lap: lap_id={lap.lap_id}, driver_id={lap.driver_id}")
            print(f"    Lap {lap.lap_number}: {lap.lap_time_ms}ms ({lap.compound}, tyre_life={lap.tyre_life})")
            print(f"    Fuel-corrected: {lap.fuel_corrected_lap_time_ms}ms, valid={lap.is_valid}")

        tel = db.query(TelemetryPoint).first()
        if tel:
            print(f"\n  Sample telemetry: lap_id={tel.lap_id}, dist={tel.distance_m}m")
            print(f"    Speed: {tel.speed_kmh}km/h, Throttle: {tel.throttle_pct}%, Brake: {tel.brake}, DRS: {tel.drs}")

        meta = db.query(DatasetMetadata).all()
        if meta:
            print(f"\n  Imported sessions ({len(meta)}):")
            for m in meta:
                print(f"    {m.year} {m.event_name} {m.session_type} — "
                      f"{m.row_count_laps} laps, {m.row_count_telemetry} telemetry rows "
                      f"(FastF1 v{m.fastf1_version})")

    print("=" * 60)
    if all_ok:
        print("  ✓ All tables populated. Database looks healthy.")
    else:
        print("  ✗ Some tables are empty. Re-run: python -m data_pipeline.load_db")
    print("=" * 60 + "\n")
    return all_ok


if __name__ == "__main__":
    verify()
