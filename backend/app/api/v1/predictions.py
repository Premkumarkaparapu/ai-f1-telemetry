"""API v1 — Predictions + Strategy simulation endpoints."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.app.database.db import get_db
from backend.app.repositories.prediction_repository import PredictionRepository
from backend.app.repositories.lap_repository import LapRepository
from backend.app.repositories.driver_repository import DriverRepository
from backend.app.services.prediction_service import PredictionService
from backend.app.schemas.schemas import (
    PredictionRequest, PredictionOut,
    StrategySimRequest, StrategySimOut,
    DegradationCurveOut, PitWindowOut,
)

router = APIRouter(prefix="/predict", tags=["Predictions"])


def _get_service(db: Session = Depends(get_db)) -> PredictionService:
    return PredictionService(
        PredictionRepository(db),
        LapRepository(db),
        DriverRepository(db),
    )


# ── Existing: basic lap-time prediction ───────────────────────────────────────

@router.post(
    "/",
    response_model=PredictionOut,
    status_code=201,
    summary="Run a lap-time prediction for a driver",
)
def predict(request: PredictionRequest, svc: PredictionService = Depends(_get_service)):
    """Predicts the next lap time using tyre state and historical data.
    
    Falls back to mean lap time if the ML model is not yet trained.
    """
    return svc.predict(request)


# ── Strategy simulation ────────────────────────────────────────────────────────

@router.post(
    "/strategy",
    response_model=StrategySimOut,
    status_code=201,
    summary="Simulate a full race strategy",
)
def simulate_strategy(
    request: StrategySimRequest,
    svc: PredictionService = Depends(_get_service),
):
    """Simulate total race time for a proposed pit strategy.

    - `pit_laps`: list of lap numbers to pit on (e.g. [28, 52])
    - `compounds`: compound per stint, length = len(pit_laps) + 1 (e.g. ["SOFT","MEDIUM","HARD"])
    - Returns per-lap projected times and total race time vs. a no-change baseline.
    """
    return svc.simulate_strategy(request)


# ── Degradation curve ─────────────────────────────────────────────────────────

@router.get(
    "/degradation/{compound}",
    response_model=DegradationCurveOut,
    summary="Get predicted tire degradation curve",
)
def degradation_curve(
    compound: str,
    max_life: int = Query(40, ge=1, le=80, description="Maximum tyre life laps to predict"),
    svc: PredictionService = Depends(_get_service),
):
    """Returns predicted lap times for each lap of tyre life.

    Used to render the degradation chart on the frontend dashboard.
    compound: SOFT | MEDIUM | HARD | INTERMEDIATE | WET
    """
    return svc.get_degradation_curve(compound.upper(), max_life)


# ── Pit window recommendation ─────────────────────────────────────────────────

@router.get(
    "/pit-window/{session_id}/{driver_id}",
    response_model=PitWindowOut,
    summary="Get optimal pit window for a driver",
)
def pit_window(
    session_id: int,
    driver_id: int,
    current_lap: int = Query(1, ge=1, description="Current lap number"),
    svc: PredictionService = Depends(_get_service),
):
    """Returns earliest, optimal, and latest recommended pit lap numbers.

    Uses degradation model to minimise projected remaining race time.
    Falls back to rule-of-thumb heuristics if models are not trained.
    """
    return svc.get_pit_window(session_id, driver_id, current_lap)


# ── Prediction history ────────────────────────────────────────────────────────

@router.get(
    "/history/{session_id}",
    response_model=list[PredictionOut],
    summary="Get all predictions run for a session",
)
def prediction_history(
    session_id: int,
    svc: PredictionService = Depends(_get_service),
):
    """Returns all model predictions stored for the given session, newest first."""
    return svc.get_history(session_id)
