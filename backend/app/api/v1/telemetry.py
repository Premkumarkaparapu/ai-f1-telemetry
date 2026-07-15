"""API v1 — Telemetry endpoints."""

import pickle
from pathlib import Path
from typing import Optional

import pandas as pd
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session

from backend.app.core.config import RAW_DIR, CACHE_DIR
from backend.app.database.db import get_db
from backend.app.repositories.lap_repository import LapRepository
from backend.app.repositories.telemetry_repository import TelemetryRepository
from backend.app.repositories.driver_repository import DriverRepository
from backend.app.services.telemetry_service import TelemetryService
from backend.app.schemas.schemas import TelemetryPointOut, TelemetrySummaryOut, LapCompareOut

router = APIRouter(prefix="/telemetry", tags=["Telemetry"])

INTERVAL_MS = 200  # 5 Hz


def _get_service(db: Session = Depends(get_db)) -> TelemetryService:
    return TelemetryService(
        TelemetryRepository(db),
        LapRepository(db),
        DriverRepository(db),
    )


@router.get(
    "/{lap_id}",
    response_model=list[TelemetryPointOut],
    summary="Get full telemetry trace for a lap",
)
def get_telemetry(lap_id: int, svc: TelemetryService = Depends(_get_service)):
    """Returns all 5Hz telemetry samples for the specified lap, ordered by distance.

    ⚠️ This returns ~450 rows per lap. Use /summary for lightweight dashboard cards.
    """
    return svc.get_telemetry(lap_id)


@router.get(
    "/{lap_id}/summary",
    response_model=TelemetrySummaryOut,
    summary="Get aggregated telemetry stats for a lap",
)
def get_telemetry_summary(lap_id: int, svc: TelemetryService = Depends(_get_service)):
    """Returns aggregated stats (max speed, avg throttle, DRS %, sector times).

    Use this for dashboard summary cards — it runs one SQL aggregation query
    instead of streaming all telemetry rows.
    """
    return svc.get_summary(lap_id)


@router.get(
    "/compare/laps",
    response_model=LapCompareOut,
    summary="Compare telemetry traces for two laps side-by-side",
)
def compare_laps(
    lap_id_1: int = Query(..., description="First lap ID"),
    lap_id_2: int = Query(..., description="Second lap ID"),
    svc: TelemetryService = Depends(_get_service),
):
    """Returns synchronized telemetry traces for both laps.
    Used to overlay speed/throttle/brake traces for driver comparison charts.
    """
    return svc.compare_laps(lap_id_1, lap_id_2)


# ── Live / On-Demand Telemetry ────────────────────────────────────────────────
# Reads directly from the FastF1 pickle cache (already on disk).
# Works for ALL 20 drivers — no DB storage needed.

def _load_live_telemetry(year: int, event: str, session_type: str,
                          driver_code: str, lap_number: int) -> list[dict]:
    """Load telemetry for any driver/lap from FastF1 pickle cache."""
    slug = f"{year}_{event.replace(' ', '_')}_{session_type}.pkl"
    raw_path = RAW_DIR / slug
    if not raw_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Session cache not found: {slug}. Run data ingestion first."
        )

    with open(raw_path, "rb") as f:
        ff1_session = pickle.load(f)

    try:
        if lap_number > 0:
            lap_obj = ff1_session.laps.pick_driver(driver_code).pick_lap(lap_number)
        else:
            # fastest lap
            drv_laps = ff1_session.laps.pick_driver(driver_code)
            valid = drv_laps[drv_laps["LapTime"].notna()]
            if valid.empty:
                return []
            lap_obj = valid.loc[valid["LapTime"].idxmin()]

        tel = lap_obj.get_telemetry()
        if tel is None or tel.empty:
            return []
    except Exception as exc:
        raise HTTPException(status_code=404, detail=f"Telemetry unavailable: {exc}")

    # Downsample to 5Hz
    tel = tel.copy()
    tel["_tms"] = tel["SessionTime"].apply(
        lambda t: int(t.total_seconds() * 1000) if pd.notna(t) else None
    )
    tel["_bin"] = (tel["_tms"] // INTERVAL_MS) * INTERVAL_MS

    agg = {c: ("mean" if c in ("Speed", "RPM", "Throttle") else "last")
           for c in ("Distance", "Speed", "RPM", "nGear", "Throttle", "Brake", "DRS", "X", "Y", "Z")
           if c in tel.columns}
    tel_s = tel.groupby("_bin").agg(agg).reset_index()

    results = []
    for _, pt in tel_s.iterrows():
        def v(col):
            val = pt.get(col)
            return None if val is None or (isinstance(val, float) and pd.isna(val)) else val

        brake_raw = v("Brake")
        drs_raw   = v("DRS")

        results.append({
            "time_ms":     int(pt["_bin"]),
            "distance_m":  float(v("Distance")) if v("Distance") is not None else None,
            "speed_kmh":   float(v("Speed"))    if v("Speed")    is not None else None,
            "rpm":         float(v("RPM"))      if v("RPM")      is not None else None,
            "gear":        int(v("nGear"))      if v("nGear")    is not None else None,
            "throttle_pct":float(v("Throttle"))if v("Throttle") is not None else None,
            "brake":       bool(int(brake_raw) > 0) if brake_raw is not None else False,
            "drs":         bool(int(drs_raw) > 8)   if drs_raw   is not None else False,
            "x":           float(v("X"))        if v("X")        is not None else None,
            "y":           float(v("Y"))        if v("Y")        is not None else None,
            "z":           float(v("Z"))        if v("Z")        is not None else None,
        })
    return results


@router.get(
    "/live/{session_id}/{driver_code}/{lap_number}",
    response_model=list[TelemetryPointOut],
    summary="Get live telemetry from FastF1 cache for any driver/lap",
)
def get_live_telemetry(
    session_id: int,
    driver_code: str,
    lap_number: int,
    db: Session = Depends(get_db),
):
    """Reads telemetry directly from FastF1 pickle cache.
    Works for ALL drivers — not just those pre-stored in the DB.
    Returns 5Hz telemetry in the same format as /{lap_id}.
    """
    # Look up session metadata from DB
    from backend.app.database.models import Session as SessionModel
    sess = db.query(SessionModel).filter(SessionModel.session_id == session_id).first()
    if not sess:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    return _load_live_telemetry(sess.year, sess.event_name, sess.session_type,
                                 driver_code.upper(), lap_number)
