"""Session repository — isolates all session-related SQL queries."""

from typing import Optional

from sqlalchemy.orm import Session

from backend.app.database.models import Session as SessionModel, Weather


class SessionRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_all(self) -> list[SessionModel]:
        return (
            self.db.query(SessionModel)
            .order_by(SessionModel.year, SessionModel.event_name)
            .all()
        )

    def get_by_id(self, session_id: int) -> Optional[SessionModel]:
        return self.db.query(SessionModel).filter(SessionModel.session_id == session_id).first()

    def get_by_year_event(
        self, year: int, event_name: str, session_type: str
    ) -> Optional[SessionModel]:
        return (
            self.db.query(SessionModel)
            .filter(
                SessionModel.year == year,
                SessionModel.event_name == event_name,
                SessionModel.session_type == session_type,
            )
            .first()
        )

    def get_weather(self, session_id: int) -> list[Weather]:
        return (
            self.db.query(Weather)
            .filter(Weather.session_id == session_id)
            .order_by(Weather.time_ms)
            .all()
        )

    def get_standings(self, session_id: int) -> list[dict]:
        """Return per-driver race standings ordered by fastest lap."""
        from sqlalchemy import func
        from backend.app.database.models import Driver, Lap, PitStop

        rows = (
            self.db.query(
                Driver.driver_id,
                Driver.code,
                Driver.team,
                Driver.team_color,
                func.min(Lap.lap_time_ms).label("fastest_lap_ms"),
                func.count(Lap.lap_id).label("total_laps"),
                func.avg(Lap.lap_time_ms).label("avg_lap_time_ms"),
            )
            .join(Lap, Lap.driver_id == Driver.driver_id)
            .filter(
                Driver.session_id == session_id,
                Lap.is_valid.is_(True),
                Lap.lap_time_ms.isnot(None),
            )
            .group_by(Driver.driver_id)
            .order_by(func.min(Lap.lap_time_ms))
            .all()
        )

        standings = []
        for pos, row in enumerate(rows, 1):
            pit_count = (
                self.db.query(func.count(PitStop.pitstop_id))
                .filter(
                    PitStop.driver_id == row.driver_id,
                    PitStop.session_id == session_id,
                )
                .scalar() or 0
            )
            standings.append({
                "driver_id": row.driver_id,
                "driver_code": row.code,
                "team": row.team,
                "team_color": row.team_color,
                "fastest_lap_ms": row.fastest_lap_ms,
                "total_laps": int(row.total_laps),
                "avg_lap_time_ms": float(row.avg_lap_time_ms) if row.avg_lap_time_ms else None,
                "pit_stop_count": pit_count,
                "position": pos,
            })
        return standings
