"""Cleanup: Remove sessions with stub/empty pickle files (< 100KB) from DB."""
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))
RAW_DIR = ROOT_DIR / "data_pipeline" / "raw"

MIN_PICKLE_SIZE = 100_000  # 100KB — real pickles are 80MB+, stubs are ~3KB

from backend.app.database.db import SessionLocal
from backend.app.database.models import Session, Lap, Driver, Weather, TelemetryPoint, Stint, PitStop, Tyre

db = SessionLocal()
all_sessions = db.query(Session).all()
print(f"Total sessions in DB: {len(all_sessions)}")

to_remove = []
to_keep = []

for s in all_sessions:
    slug = f"{s.year}_{s.event_name.replace(' ', '_')}_{s.session_type}.pkl"
    pkl = RAW_DIR / slug
    size = pkl.stat().st_size if pkl.exists() else 0
    if size >= MIN_PICKLE_SIZE:
        to_keep.append((s, size))
    else:
        to_remove.append((s, size))

print(f"\nKEEP ({len(to_keep)}):")
for s, sz in to_keep:
    print(f"  {s.session_id:4d} | {s.year} {s.event_name:35s} ({s.session_type}) | {sz//1024//1024}MB")

print(f"\nREMOVE ({len(to_remove)}) - stub/missing pickles:")
for s, sz in to_remove:
    print(f"  {s.session_id:4d} | {s.year} {s.event_name:35s} ({s.session_type}) | {sz}B")

if to_remove:
    ids = [s.session_id for s, _ in to_remove]
    # Get driver IDs for these sessions
    driver_ids = [d.driver_id for d in db.query(Driver.driver_id).filter(Driver.session_id.in_(ids)).all()]
    # Get lap IDs via drivers
    lap_ids = [l.lap_id for l in db.query(Lap.lap_id).filter(Lap.driver_id.in_(driver_ids)).all()] if driver_ids else []
    
    if lap_ids:
        db.query(TelemetryPoint).filter(TelemetryPoint.lap_id.in_(lap_ids)).delete(synchronize_session=False)
        db.query(Tyre).filter(Tyre.lap_id.in_(lap_ids)).delete(synchronize_session=False)
        db.query(Lap).filter(Lap.lap_id.in_(lap_ids)).delete(synchronize_session=False)
    db.query(PitStop).filter(PitStop.session_id.in_(ids)).delete(synchronize_session=False)
    db.query(Stint).filter(Stint.session_id.in_(ids)).delete(synchronize_session=False)
    db.query(Weather).filter(Weather.session_id.in_(ids)).delete(synchronize_session=False)
    db.query(Driver).filter(Driver.session_id.in_(ids)).delete(synchronize_session=False)
    db.query(Session).filter(Session.session_id.in_(ids)).delete(synchronize_session=False)
    
    db.commit()
    print(f"\nRemoved {len(ids)} sessions and all dependent data.")

print(f"\nSessions remaining: {db.query(Session).count()}")
db.close()
