"""API v1 — Sessions endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.database.db import get_db
from backend.app.repositories.session_repository import SessionRepository
from backend.app.services.session_service import SessionService
from backend.app.schemas.schemas import SessionOut, WeatherOut

router = APIRouter(prefix="/sessions", tags=["Sessions"])


def _get_service(db: Session = Depends(get_db)) -> SessionService:
    return SessionService(SessionRepository(db))


@router.get("/", response_model=list[SessionOut], summary="List all ingested sessions")
def list_sessions(svc: SessionService = Depends(_get_service)):
    """Returns all F1 sessions loaded into the database, ordered by year and event."""
    return svc.list_sessions()


@router.get("/{session_id}", response_model=SessionOut, summary="Get a specific session")
def get_session(session_id: int, svc: SessionService = Depends(_get_service)):
    return svc.get_session(session_id)


@router.get(
    "/{session_id}/weather",
    response_model=list[WeatherOut],
    summary="Get weather data for a session",
)
def get_weather(session_id: int, svc: SessionService = Depends(_get_service)):
    """Returns session-level weather telemetry sampled every ~20 seconds."""
    return svc.get_weather(session_id)


@router.get(
    "/{session_id}/standings",
    summary="Get driver standings for a session",
)
def get_standings(session_id: int, svc: SessionService = Depends(_get_service)):
    """Returns drivers ranked by fastest lap, with pit stop counts and averages.
    
    Use this to populate the leaderboard on the frontend dashboard.
    """
    return svc.get_standings(session_id)

