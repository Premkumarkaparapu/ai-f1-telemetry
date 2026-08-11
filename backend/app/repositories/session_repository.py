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
        # 1. Try DB first
        records = (
            self.db.query(Weather)
            .filter(Weather.session_id == session_id)
            .order_by(Weather.time_ms)
            .all()
        )
        if len(records) > 0:
            return records

        # 2. Dynamic fallback to FastF1 pickle cache
        try:
            import pickle
            import pandas as pd

            sess = self.db.query(SessionModel).filter(SessionModel.session_id == session_id).first()
            if not sess:
                return []

            slug = f"{sess.year}_{sess.event_name.replace(' ', '_')}_{sess.session_type}.pkl"
            from backend.app.services.storage_service import get_storage_provider
            try:
                provider = get_storage_provider()
                raw_path = provider.get_file(slug)
            except Exception:
                return []

            with open(raw_path, "rb") as f:
                ff1_session = pickle.load(f)

            wx = ff1_session.weather_data
            if wx is None or wx.empty:
                return []

            # Save weather readings to DB (downsampled to ~30 readings to avoid cluttering)
            step = max(1, len(wx) // 30)
            weather_records = []
            for i, (_, r) in enumerate(wx.iterrows()):
                if i % step != 0:
                    continue

                time_val = r.get("Time")
                time_ms = None
                if time_val is not None and pd.notna(time_val):
                    time_ms = int(time_val.total_seconds() * 1000)

                def f(col):
                    v = r.get(col)
                    return float(v) if v is not None and pd.notna(v) else None

                weather_records.append(
                    Weather(
                        session_id=session_id,
                        time_ms=time_ms,
                        air_temp=f("AirTemp"),
                        track_temp=f("TrackTemp"),
                        humidity=f("Humidity"),
                        pressure=f("Pressure"),
                        wind_speed=f("WindSpeed"),
                        wind_dir=(
                            int(r.get("WindDirection"))
                            if r.get("WindDirection") is not None
                            and pd.notna(r.get("WindDirection"))
                            else None
                        ),
                        rainfall=bool(r.get("Rainfall", False)),
                    )
                )

            if weather_records:
                self.db.bulk_save_objects(weather_records)
                self.db.commit()
                # Re-query to return fresh managed objects
                return (
                    self.db.query(Weather)
                    .filter(Weather.session_id == session_id)
                    .order_by(Weather.time_ms)
                    .all()
                )
        except Exception:
            pass

        return []

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
