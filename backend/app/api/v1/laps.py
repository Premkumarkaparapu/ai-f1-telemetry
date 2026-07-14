"""API v1 — Laps endpoints."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.app.database.db import get_db
from backend.app.repositories.lap_repository import LapRepository
from backend.app.schemas.schemas import LapOut, StintOut, PitStopOut

router = APIRouter(prefix="/laps", tags=["Laps"])


def _get_repo(db: Session = Depends(get_db)) -> LapRepository:
    return LapRepository(db)


@router.get("/", response_model=list[LapOut], summary="List laps for a driver")
def list_laps(
    driver_id: int = Query(..., description="Driver ID to fetch laps for"),
    valid_only: bool = Query(False, description="If true, exclude pit/invalid laps"),
    repo: LapRepository = Depends(_get_repo),
):
    return repo.get_by_driver(driver_id, valid_only=valid_only)


@router.get("/{lap_id}", response_model=LapOut, summary="Get a specific lap")
def get_lap(lap_id: int, repo: LapRepository = Depends(_get_repo)):
    from fastapi import HTTPException
    lap = repo.get_by_id(lap_id)
    if not lap:
        raise HTTPException(status_code=404, detail=f"Lap {lap_id} not found.")
    return lap


@router.get("/stints/", response_model=list[StintOut], summary="Get stints for a driver in a session")
def get_stints(
    driver_id: int = Query(...),
    session_id: int = Query(...),
    repo: LapRepository = Depends(_get_repo),
):
    """Returns the tyre stint breakdown — use this to render the Gantt-style timeline."""
    return repo.get_stints(driver_id, session_id)


@router.get("/pitstops/", response_model=list[PitStopOut], summary="Get pit stops for a driver")
def get_pitstops(
    driver_id: int = Query(...),
    session_id: int = Query(...),
    repo: LapRepository = Depends(_get_repo),
):
    return repo.get_pitstops(driver_id, session_id)
