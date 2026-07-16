"""API v1 — Sessions endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy import distinct
from sqlalchemy.orm import Session

from backend.app.database.db import get_db
from backend.app.database.models import Session as SessionModel
from backend.app.repositories.session_repository import SessionRepository
from backend.app.services.session_service import SessionService
from backend.app.schemas.schemas import SessionOut, WeatherOut

router = APIRouter(prefix="/sessions", tags=["Sessions"])

SESSION_TYPE_LABELS = {
    "R": "Race",
    "Q": "Qualifying",
    "S": "Sprint",
    "SQ": "Sprint Qualifying",
    "FP1": "Practice 1",
    "FP2": "Practice 2",
    "FP3": "Practice 3",
}


def _get_service(db: Session = Depends(get_db)) -> SessionService:
    return SessionService(SessionRepository(db))


@router.get("/years", summary="List all years with sessions in DB")
def list_years(db: Session = Depends(get_db)):
    """Returns sorted list of distinct years that have sessions in the database."""
    years = db.query(distinct(SessionModel.year)).order_by(SessionModel.year.desc()).all()
    return {"years": [y[0] for y in years]}


@router.get("/by-year/{year}", summary="List sessions for a specific year")
def list_by_year(year: int, db: Session = Depends(get_db)):
    """Returns all sessions for a given year, grouped by event with all session types."""
    rows = (
        db.query(SessionModel)
        .filter(SessionModel.year == year)
        .order_by(SessionModel.event_name, SessionModel.session_type)
        .all()
    )
    # Group into {event_name: [{session_id, session_type, label}]}
    events: dict = {}
    for s in rows:
        if s.event_name not in events:
            events[s.event_name] = {"event_name": s.event_name, "track": s.track, "sessions": []}
        events[s.event_name]["sessions"].append({
            "session_id": s.session_id,
            "session_type": s.session_type,
            "label": SESSION_TYPE_LABELS.get(s.session_type, s.session_type),
        })
    return {"year": year, "events": list(events.values())}


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
