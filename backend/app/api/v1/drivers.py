"""API v1 — Drivers endpoints."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.app.database.db import get_db
from backend.app.repositories.driver_repository import DriverRepository
from backend.app.schemas.schemas import DriverOut
from backend.app.core.logging import get_logger

router = APIRouter(prefix="/drivers", tags=["Drivers"])
logger = get_logger(__name__)


def _get_repo(db: Session = Depends(get_db)) -> DriverRepository:
    return DriverRepository(db)


@router.get("/", response_model=list[DriverOut], summary="List drivers in a session")
def list_drivers(
    session_id: int = Query(..., description="Session ID to list drivers for"),
    repo: DriverRepository = Depends(_get_repo),
):
    return repo.get_by_session(session_id)


@router.get("/{code}", response_model=DriverOut, summary="Get a driver by 3-letter code")
def get_driver(
    code: str,
    session_id: int = Query(..., description="Session ID to scope the lookup"),
    repo: DriverRepository = Depends(_get_repo),
):
    from fastapi import HTTPException
    driver = repo.get_by_code(session_id, code)
    if not driver:
        raise HTTPException(status_code=404, detail=f"Driver '{code}' not found in session {session_id}.")
    return driver
