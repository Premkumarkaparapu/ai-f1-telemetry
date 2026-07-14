"""Telemetry service — business logic for telemetry queries and comparison."""

from fastapi import HTTPException

from backend.app.repositories.lap_repository import LapRepository
from backend.app.repositories.telemetry_repository import TelemetryRepository
from backend.app.repositories.driver_repository import DriverRepository
from backend.app.schemas.schemas import TelemetrySummaryOut, LapCompareOut, TelemetryPointOut


class TelemetryService:
    def __init__(
        self,
        telemetry_repo: TelemetryRepository,
        lap_repo: LapRepository,
        driver_repo: DriverRepository,
    ):
        self.telemetry_repo = telemetry_repo
        self.lap_repo = lap_repo
        self.driver_repo = driver_repo

    def _get_lap_or_404(self, lap_id: int):
        lap = self.lap_repo.get_by_id(lap_id)
        if not lap:
            raise HTTPException(status_code=404, detail=f"Lap {lap_id} not found.")
        return lap

    def get_telemetry(self, lap_id: int):
        self._get_lap_or_404(lap_id)
        return self.telemetry_repo.get_by_lap(lap_id)

    def get_summary(self, lap_id: int) -> TelemetrySummaryOut:
        lap = self._get_lap_or_404(lap_id)
        agg = self.telemetry_repo.get_summary(lap_id)
        return TelemetrySummaryOut(
            lap_id=lap_id,
            lap_time_ms=lap.lap_time_ms,
            sector1_ms=lap.sector1_ms,
            sector2_ms=lap.sector2_ms,
            sector3_ms=lap.sector3_ms,
            compound=lap.compound,
            tyre_life=lap.tyre_life,
            **agg,
        )

    def compare_laps(self, lap_id_1: int, lap_id_2: int) -> LapCompareOut:
        lap1 = self._get_lap_or_404(lap_id_1)
        lap2 = self._get_lap_or_404(lap_id_2)

        driver1 = self.driver_repo.get_by_id(lap1.driver_id)
        driver2 = self.driver_repo.get_by_id(lap2.driver_id)

        t1 = self.telemetry_repo.get_by_lap(lap_id_1)
        t2 = self.telemetry_repo.get_by_lap(lap_id_2)

        return LapCompareOut(
            lap_id_1=lap_id_1,
            lap_id_2=lap_id_2,
            driver_code_1=driver1.code if driver1 else "???",
            driver_code_2=driver2.code if driver2 else "???",
            telemetry_1=[TelemetryPointOut.model_validate(p) for p in t1],
            telemetry_2=[TelemetryPointOut.model_validate(p) for p in t2],
        )
