"""Session service — business logic layer between API routes and the repository."""

from fastapi import HTTPException

from backend.app.repositories.session_repository import SessionRepository


class SessionService:
    def __init__(self, repo: SessionRepository):
        self.repo = repo

    def list_sessions(self):
        return self.repo.get_all()

    def get_session(self, session_id: int):
        session = self.repo.get_by_id(session_id)
        if not session:
            raise HTTPException(status_code=404, detail=f"Session {session_id} not found.")
        return session

    def get_weather(self, session_id: int):
        self.get_session(session_id)  # validates session exists
        return self.repo.get_weather(session_id)

    def get_standings(self, session_id: int):
        self.get_session(session_id)  # validates
        from backend.app.schemas.schemas import DriverStandingOut
        standings = self.repo.get_standings(session_id)
        return [DriverStandingOut(**s) for s in standings]
