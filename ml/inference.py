"""
ML Inference — AI F1 Telemetry Platform
========================================
Loads trained model artefacts and exposes clean prediction functions
used by the FastAPI prediction service.

All functions degrade gracefully when models are not yet trained:
  - laptime_predictor.pkl missing → falls back to compound_means.json
  - compound_means.json missing   → returns hard-coded defaults
  - degradation ridge missing     → falls back to XGB → falls back to linear estimate
"""

import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ── Config (import-safe) ──────────────────────────────────────────────────────
try:
    from backend.app.core.config import MODEL_PATH
except Exception:
    MODEL_PATH = Path(__file__).resolve().parent / "models"

COMPOUND_ENCODE = {"SOFT": 0, "MEDIUM": 1, "HARD": 2, "INTERMEDIATE": 3, "WET": 4}
DEFAULT_MEANS = {"SOFT": 82000.0, "MEDIUM": 85000.0, "HARD": 88000.0,
                 "INTERMEDIATE": 95000.0, "WET": 105000.0}


# ── Helpers ───────────────────────────────────────────────────────────────────

def load_model(model_name: str):
    """Load a joblib-serialised model from MODEL_PATH/{model_name}.pkl."""
    import joblib
    path = MODEL_PATH / f"{model_name}.pkl"
    if not path.exists():
        raise FileNotFoundError(f"Model not found: {path}")
    return joblib.load(path)


def get_compound_means() -> dict[str, float]:
    """Return mean lap time per compound from compound_means.json, or hard-coded defaults."""
    path = MODEL_PATH / "compound_means.json"
    if path.exists():
        try:
            with open(path) as f:
                return json.load(f)
        except Exception:
            pass
    return DEFAULT_MEANS.copy()


# ── Lap Time Prediction ───────────────────────────────────────────────────────

def predict_lap_time(
    tyre_life: int,
    compound: str,
    lap_number: int = 1,
    stint_number: int = 1,
) -> float:
    """Predict fuel-corrected lap time in milliseconds.

    Falls back to compound mean if the trained model is unavailable.
    """
    compound_upper = compound.upper()
    compound_enc = COMPOUND_ENCODE.get(compound_upper, 1)
    tyre_life_sq = tyre_life ** 2
    is_first_lap = int(lap_number == 1)

    features = [[tyre_life, compound_enc, tyre_life_sq, lap_number, is_first_lap, stint_number]]

    try:
        model = load_model("laptime_predictor")
        import numpy as np
        pred = float(model.predict(np.array(features))[0])
        return max(pred, 60_000)  # floor at 60 s
    except FileNotFoundError:
        logger.debug("laptime_predictor not found — using compound mean fallback")
    except Exception as e:
        logger.warning("laptime_predictor inference error: %s", e)

    means = get_compound_means()
    base = means.get(compound_upper, 90_000.0)
    # Add a simple tyre-age penalty: ~80 ms/lap after lap 5
    penalty = max(0, (tyre_life - 5)) * 80
    return base + penalty


# ── Tire Degradation Curve ────────────────────────────────────────────────────

def predict_tire_degradation(
    compound: str,
    tyre_life_range: list[int],
) -> list[float]:
    """Return predicted lap times (ms) for each tyre life value in the range.

    Priority: Ridge (smooth) → XGB → linear extrapolation from compound mean.
    """
    import numpy as np
    compound_upper = compound.upper()

    # Try per-compound Ridge first (smoothest curve)
    try:
        model = load_model(f"tire_degradation_ridge_{compound_upper}")
        X = np.array(tyre_life_range).reshape(-1, 1)
        preds = model.predict(X).tolist()
        return [max(p, 60_000) for p in preds]
    except FileNotFoundError:
        pass
    except Exception as e:
        logger.warning("Ridge degradation error: %s", e)

    # Try global XGB
    try:
        model = load_model("tire_degradation_xgb")
        compound_enc = COMPOUND_ENCODE.get(compound_upper, 1)
        X = np.array([
            [life, compound_enc, life ** 2]
            for life in tyre_life_range
        ])
        preds = model.predict(X).tolist()
        return [max(p, 60_000) for p in preds]
    except FileNotFoundError:
        pass
    except Exception as e:
        logger.warning("XGB degradation error: %s", e)

    # Linear fallback from compound mean
    means = get_compound_means()
    base = means.get(compound_upper, 90_000.0)
    return [max(base + max(0, life - 5) * 80, 60_000) for life in tyre_life_range]


# ── Race Strategy Simulation ──────────────────────────────────────────────────

def simulate_race_strategy(
    total_laps: int,
    pit_laps: list[int],
    compounds: list[str],
    actual_laps: dict[int, int],
    pit_time_loss_ms: int = 25_000,
) -> dict:
    """Simulate total race time for a given pit strategy.

    Args:
        total_laps: total laps in the race
        pit_laps: lap numbers where a pit stop occurs
        compounds: compound for each stint (len = len(pit_laps) + 1)
        actual_laps: {lap_number: lap_time_ms} from DB (may be partial)
        pit_time_loss_ms: time lost in the pit lane

    Returns:
        dict with total_race_time_ms, per_lap_times_ms, pit_stops, compounds_used
    """
    pit_set = set(pit_laps)

    # Build stint assignment: which compound applies to each lap
    # stint 0 = before first pit, stint 1 = between pit[0] and pit[1], etc.
    stint_boundaries = [0] + sorted(pit_laps) + [total_laps + 1]
    lap_compound: dict[int, str] = {}
    for i in range(len(compounds)):
        start = stint_boundaries[i] + 1
        end = stint_boundaries[i + 1]
        cmp = compounds[i].upper() if i < len(compounds) else "MEDIUM"
        for lap_num in range(start, end + 1):
            lap_compound[lap_num] = cmp

    per_lap_times: list[float] = []
    tyre_age_by_stint: dict[int, int] = {}  # tracks tyre age per stint

    # Map lap_num → stint index
    def stint_for_lap(ln: int) -> int:
        for idx in range(len(pit_laps) + 1):
            start = stint_boundaries[idx] + 1
            end = stint_boundaries[idx + 1]
            if start <= ln <= end:
                return idx
        return 0

    stint_ages: dict[int, int] = {}

    for lap_num in range(1, total_laps + 1):
        stint_idx = stint_for_lap(lap_num)
        stint_ages[stint_idx] = stint_ages.get(stint_idx, 0) + 1
        tyre_age = stint_ages[stint_idx]
        compound = lap_compound.get(lap_num, "MEDIUM")

        if lap_num in actual_laps and actual_laps[lap_num]:
            lap_time = float(actual_laps[lap_num])
        else:
            lap_time = predict_lap_time(tyre_age, compound, lap_num, stint_idx + 1)

        if lap_num in pit_set:
            lap_time += pit_time_loss_ms

        per_lap_times.append(lap_time)

    return {
        "total_race_time_ms": sum(per_lap_times),
        "per_lap_times_ms": per_lap_times,
        "pit_stops": len(pit_laps),
        "compounds_used": list(dict.fromkeys(
            [lap_compound.get(n, "MEDIUM") for n in range(1, total_laps + 1)]
        )),
    }


# ── Pit Window Prediction ─────────────────────────────────────────────────────

def predict_pit_window(
    current_lap: int,
    total_laps: int,
    current_compound: str,
    current_tyre_life: int,
) -> dict:
    """Return the recommended pit window based on degradation model + race dynamics.

    Logic:
      1. Project lap times staying out (current compound, ageing tyres)
      2. For each candidate pit lap, estimate total remaining race time after pit
      3. Return the pit lap that minimises the projected remaining race time

    Returns dict with earliest_lap, optimal_lap, latest_lap, reasoning.
    """
    remaining_laps = total_laps - current_lap
    if remaining_laps <= 0:
        return {
            "earliest_lap": current_lap,
            "optimal_lap": current_lap,
            "latest_lap": current_lap,
            "reasoning": "Race is effectively over.",
        }

    # Safety constraints
    earliest_lap = min(current_lap + 2, total_laps - 5)
    latest_lap = max(earliest_lap + 2, total_laps - 6)

    compound_upper = current_compound.upper()
    fresh_compound = _suggest_next_compound(compound_upper)

    # Evaluate each candidate pit lap
    best_lap = earliest_lap
    best_cost = float("inf")
    candidate_range = list(range(earliest_lap, latest_lap + 1))

    tyre_life_range_stay = list(range(current_tyre_life + 1,
                                      current_tyre_life + remaining_laps + 1))
    stay_out_times = predict_tire_degradation(compound_upper, tyre_life_range_stay)

    for candidate_pit in candidate_range:
        laps_to_pit = candidate_pit - current_lap
        laps_after_pit = total_laps - candidate_pit

        # Cost of staying out until pit
        stay_cost = sum(stay_out_times[:laps_to_pit])
        # Cost of fresh tyres after pit
        fresh_range = list(range(1, laps_after_pit + 1))
        fresh_times = predict_tire_degradation(fresh_compound, fresh_range)
        fresh_cost = sum(fresh_times) + 25_000  # pit lane loss

        total_cost = stay_cost + fresh_cost
        if total_cost < best_cost:
            best_cost = total_cost
            best_lap = candidate_pit

    laps_remaining_on_current = current_tyre_life + (best_lap - current_lap)
    reasoning = (
        f"Optimal pit on lap {best_lap} ({best_lap - current_lap} laps away). "
        f"Current {compound_upper} tyre will be {laps_remaining_on_current} laps old. "
        f"Suggested next compound: {fresh_compound}."
    )

    return {
        "earliest_lap": earliest_lap,
        "optimal_lap": best_lap,
        "latest_lap": latest_lap,
        "reasoning": reasoning,
    }


def _suggest_next_compound(current: str) -> str:
    """Simple escalation: SOFT→MEDIUM→HARD, others stay the same."""
    escalation = {"SOFT": "MEDIUM", "MEDIUM": "HARD"}
    return escalation.get(current.upper(), current.upper())
