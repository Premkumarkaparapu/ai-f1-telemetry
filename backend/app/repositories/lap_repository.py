"""Lap repository — isolates all lap-related SQL queries."""

from typing import Optional

from sqlalchemy.orm import Session

from backend.app.database.models import Lap, Stint, PitStop


class LapRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_driver(self, driver_id: int, valid_only: bool = False) -> list[Lap]:
        q = self.db.query(Lap).filter(Lap.driver_id == driver_id)
        if valid_only:
            q = q.filter(Lap.is_valid.is_(True))
        return q.order_by(Lap.lap_number).all()

    def get_by_id(self, lap_id: int) -> Optional[Lap]:
        return self.db.query(Lap).filter(Lap.lap_id == lap_id).first()

    def get_fastest_by_driver(self, driver_id: int) -> Optional[Lap]:
        return (
            self.db.query(Lap)
            .filter(Lap.driver_id == driver_id, Lap.is_valid.is_(True), Lap.lap_time_ms.isnot(None))
            .order_by(Lap.lap_time_ms)
            .first()
        )

    def get_stints(self, driver_id: int, session_id: int) -> list[Stint]:
        return (
            self.db.query(Stint)
            .filter(Stint.driver_id == driver_id, Stint.session_id == session_id)
            .order_by(Stint.stint_number)
            .all()
        )

    def get_pitstops(self, driver_id: int, session_id: int) -> list[PitStop]:
        return (
            self.db.query(PitStop)
            .filter(PitStop.driver_id == driver_id, PitStop.session_id == session_id)
            .order_by(PitStop.lap_number)
            .all()
        )
