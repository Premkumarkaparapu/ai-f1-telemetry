"""API v1 — Telemetry endpoints."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.app.database.db import get_db
from backend.app.repositories.lap_repository import LapRepository
from backend.app.repositories.telemetry_repository import TelemetryRepository
from backend.app.repositories.driver_repository import DriverRepository
from backend.app.services.telemetry_service import TelemetryService
from backend.app.schemas.schemas import TelemetryPointOut, TelemetrySummaryOut, LapCompareOut

router = APIRouter(prefix="/telemetry", tags=["Telemetry"])


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
