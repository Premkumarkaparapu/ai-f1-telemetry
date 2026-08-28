"""Track profile repository — queries for track settings."""

from typing import Optional
from sqlalchemy.orm import Session
from backend.app.database.models import TrackProfile


class TrackProfileRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_track(self, track: str) -> Optional[TrackProfile]:
        return self.db.query(TrackProfile).filter(
            TrackProfile.track == track
        ).first()

    def create(self, profile: TrackProfile) -> TrackProfile:
        self.db.add(profile)
        self.db.commit()
        self.db.refresh(profile)
        return profile
