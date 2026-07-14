"""Prediction service — ML-backed strategy simulation and pit window prediction.

Falls back to DB-computed values gracefully if models are not yet trained.
"""

import json
from datetime import datetime
from typing import Optional

from fastapi import HTTPException

from backend.app.core.logging import get_logger
from backend.app.database.models import Prediction
from backend.app.repositories.prediction_repository import PredictionRepository
from backend.app.repositories.lap_repository import LapRepository
from backend.app.repositories.driver_repository import DriverRepository
from backend.app.schemas.schemas import (
    PredictionRequest, PredictionOut,
    StrategySimRequest, StrategySimOut,
    DegradationCurveOut, PitWindowOut,
)

logger = get_logger(__name__)


class PredictionService:
    def __init__(
        self,
        prediction_repo: PredictionRepository,
        lap_repo: LapRepository,
        driver_repo: DriverRepository,
    ):
        self.prediction_repo = prediction_repo
        self.lap_repo = lap_repo
        self.driver_repo = driver_repo

    # ── Basic lap-time prediction ─────────────────────────────────────────────

    def predict(self, request: PredictionRequest) -> PredictionOut:
        driver = self.driver_repo.get_by_id(request.driver_id)
        if not driver:
            raise HTTPException(status_code=404, detail=f"Driver {request.driver_id} not found.")

        laps = self.lap_repo.get_by_driver(request.driver_id, valid_only=True)
        if not laps:
            raise HTTPException(status_code=422, detail="No valid laps found for this driver.")

        valid_times = [l.lap_time_ms for l in laps if l.lap_time_ms]
        mean_time = sum(valid_times) / len(valid_times) if valid_times else 0.0

        predicted_value = mean_time
        model_name = "mean_fallback_v1"

        try:
            from ml.inference import predict_lap_time
            last_lap = laps[-1]
            compound = (last_lap.compound or "MEDIUM").upper()
            tyre_life = last_lap.tyre_life or 1
            lap_number = last_lap.lap_number or 1
            stint_number = last_lap.stint_number or 1
            predicted_value = predict_lap_time(tyre_life, compound, lap_number, stint_number)
            model_name = "laptime_predictor_v1"
        except Exception as e:
            logger.warning("ML predict_lap_time failed, using mean: %s", e)

        record = Prediction(
            session_id=request.session_id,
            driver_id=request.driver_id,
            model_name=model_name,
            model_version="1.0.0",
            prediction_type=request.prediction_type,
            input_features=json.dumps({
                "driver_id": request.driver_id,
                "type": request.prediction_type,
            }),
            predicted_value=predicted_value,
            created_at=datetime.utcnow(),
        )
        saved = self.prediction_repo.create(record)
        return PredictionOut.model_validate(saved)

    # ── Race strategy simulation ──────────────────────────────────────────────

    def simulate_strategy(self, request: StrategySimRequest) -> StrategySimOut:
        if len(request.compounds) != len(request.pit_laps) + 1:
            raise HTTPException(
                status_code=422,
                detail=f"compounds must have exactly {len(request.pit_laps) + 1} entries "
                       f"(one per stint). Got {len(request.compounds)}.",
            )

        laps = self.lap_repo.get_by_driver(request.driver_id, valid_only=True)
        if not laps:
            raise HTTPException(status_code=422, detail="No valid laps found for driver.")

        total_laps = max(l.lap_number for l in laps)
        actual_laps: dict[int, int] = {
            l.lap_number: l.lap_time_ms
            for l in laps
            if l.lap_time_ms
        }

        all_valid_times = list(actual_laps.values())
        mean_lap_ms = sum(all_valid_times) / len(all_valid_times) if all_valid_times else 90_000.0

        per_lap_times: list[float] = []
        total_time: float = 0.0
        model_type = "mean_fallback"

        try:
            from ml.inference import simulate_race_strategy
            result = simulate_race_strategy(
                total_laps=total_laps,
                pit_laps=request.pit_laps,
                compounds=request.compounds,
                actual_laps=actual_laps,
                pit_time_loss_ms=request.pit_time_loss_ms,
            )
            per_lap_times = result["per_lap_times_ms"]
            total_time = result["total_race_time_ms"]
            model_type = "ml"
        except Exception as e:
            logger.warning("ML simulation failed, using simple fallback: %s", e)
            pit_set = set(request.pit_laps)
            for lap_num in range(1, total_laps + 1):
                lt = float(actual_laps.get(lap_num, mean_lap_ms))
                if lap_num in pit_set:
                    lt += request.pit_time_loss_ms
                per_lap_times.append(lt)
            total_time = sum(per_lap_times)

        # Baseline: sum of actual lap times without any strategy change
        baseline_total = float(
            sum(actual_laps.get(n, mean_lap_ms) for n in range(1, total_laps + 1))
        )
        vs_baseline = total_time - baseline_total

        return StrategySimOut(
            session_id=request.session_id,
            driver_id=request.driver_id,
            pit_laps=request.pit_laps,
            compounds=request.compounds,
            total_race_time_ms=total_time,
            per_lap_times_ms=per_lap_times,
            pit_stops=len(request.pit_laps),
            vs_baseline_ms=vs_baseline,
        )

    # ── Degradation curve ─────────────────────────────────────────────────────

    def get_degradation_curve(self, compound: str, max_tyre_life: int = 40) -> DegradationCurveOut:
        compound_upper = compound.upper()
        tyre_life_range = list(range(1, max_tyre_life + 1))
        model_type = "mean_fallback"

        try:
            from ml.inference import predict_tire_degradation, get_compound_means
            predictions = predict_tire_degradation(compound_upper, tyre_life_range)
            # Determine which model was used
            from backend.app.core.config import MODEL_PATH
            if (MODEL_PATH / f"tire_degradation_ridge_{compound_upper}.pkl").exists():
                model_type = "ridge"
            elif (MODEL_PATH / "tire_degradation_xgb.pkl").exists():
                model_type = "xgb"
        except Exception as e:
            logger.warning("Degradation prediction failed: %s", e)
            try:
                from ml.inference import get_compound_means
                means = get_compound_means()
            except Exception:
                means = {"SOFT": 82000, "MEDIUM": 85000, "HARD": 88000}
            base = means.get(compound_upper, 90_000.0)
            predictions = [base + max(0, life - 5) * 80 for life in tyre_life_range]

        return DegradationCurveOut(
            compound=compound_upper,
            tyre_life_values=tyre_life_range,
            predicted_lap_times_ms=predictions,
            model_type=model_type,
        )

    # ── Pit window ────────────────────────────────────────────────────────────

    def get_pit_window(self, session_id: int, driver_id: int, current_lap: int) -> PitWindowOut:
        laps = self.lap_repo.get_by_driver(driver_id, valid_only=True)
        if not laps:
            raise HTTPException(status_code=422, detail="No valid laps for driver.")

        total_laps = max(l.lap_number for l in laps)
        last_lap = laps[-1]
        compound = (last_lap.compound or "MEDIUM").upper()
        tyre_life = last_lap.tyre_life or current_lap

        try:
            from ml.inference import predict_pit_window
            result = predict_pit_window(current_lap, total_laps, compound, tyre_life)
        except Exception as e:
            logger.warning("Pit window model failed, using heuristic: %s", e)
            earliest = min(current_lap + 2, total_laps - 5)
            latest = max(earliest + 5, total_laps - 6)
            optimal = (earliest + latest) // 2
            result = {
                "earliest_lap": earliest,
                "optimal_lap": optimal,
                "latest_lap": latest,
                "reasoning": (
                    f"Heuristic window laps {earliest}–{latest} "
                    f"(tyre life {tyre_life} laps on {compound})."
                ),
            }

        return PitWindowOut(
            session_id=session_id,
            driver_id=driver_id,
            current_lap=current_lap,
            earliest_lap=result["earliest_lap"],
            optimal_lap=result["optimal_lap"],
            latest_lap=result["latest_lap"],
            reasoning=result["reasoning"],
        )

    # ── Prediction history ────────────────────────────────────────────────────

    def get_history(self, session_id: int) -> list[PredictionOut]:
        records = self.prediction_repo.get_by_session(session_id)
        return [PredictionOut.model_validate(r) for r in records]
