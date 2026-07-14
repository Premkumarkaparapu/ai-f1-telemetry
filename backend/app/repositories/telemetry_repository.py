"""Telemetry repository — isolates all telemetry-related SQL queries."""

from typing import Optional

from sqlalchemy import func, Float
from sqlalchemy.orm import Session

from backend.app.database.models import TelemetryPoint


class TelemetryRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_lap(self, lap_id: int) -> list[TelemetryPoint]:
        return (
            self.db.query(TelemetryPoint)
            .filter(TelemetryPoint.lap_id == lap_id)
            .order_by(TelemetryPoint.distance_m)
            .all()
        )

    def get_summary(self, lap_id: int) -> dict:
        """Return aggregated stats for a lap — used by the /summary endpoint."""
        row = (
            self.db.query(
                func.max(TelemetryPoint.speed_kmh).label("max_speed_kmh"),
                func.avg(TelemetryPoint.speed_kmh).label("avg_speed_kmh"),
                func.avg(TelemetryPoint.throttle_pct).label("avg_throttle_pct"),
                func.avg(
                    func.cast(TelemetryPoint.brake, Float)
                ).label("avg_brake_pct"),
                func.avg(
                    func.cast(TelemetryPoint.drs, Float)
                ).label("drs_usage_pct"),
            )
            .filter(TelemetryPoint.lap_id == lap_id)
            .one()
        )
        return {
            "max_speed_kmh": row.max_speed_kmh,
            "avg_speed_kmh": row.avg_speed_kmh,
            "avg_throttle_pct": row.avg_throttle_pct,
            "avg_brake_pct": (row.avg_brake_pct or 0) * 100,
            "drs_usage_pct": (row.drs_usage_pct or 0) * 100,
        }
