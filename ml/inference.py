"""
ML Inference — AI F1 Telemetry Platform
========================================
Loads trained model artefacts and exposes clean prediction functions.

All functions degrade gracefully:
  - laptime_predictor.pkl missing → falls back to compound_means.json
  - compound_means.json missing   → hard-coded realistic defaults
  - degradation ridge missing     → XGB → linear estimate with track context
"""

import json
import logging
import math
from pathlib import Path

logger = logging.getLogger(__name__)

try:
    from backend.app.core.config import MODEL_PATH
except Exception:
    MODEL_PATH = Path(__file__).resolve().parent / "models"

# ── Encoding tables (must match train.py) ────────────────────────────────────
COMPOUND_ENCODE = {"SOFT": 0, "MEDIUM": 1, "HARD": 2, "INTERMEDIATE": 3, "WET": 4}
SESSION_ENCODE  = {"R": 0, "Q": 1, "FP1": 2, "FP2": 3, "FP3": 4, "S": 5, "SQ": 6}

# Realistic per-compound defaults (ms) – fallback only
DEFAULT_MEANS = {
    "SOFT":         {"mean": 82000.0,  "std": 3500.0},
    "MEDIUM":       {"mean": 85500.0,  "std": 4000.0},
    "HARD":         {"mean": 88000.0,  "std": 4500.0},
    "INTERMEDIATE": {"mean": 96000.0,  "std": 5000.0},
    "WET":          {"mean": 104000.0, "std": 6000.0},
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _load_meta() -> dict:
    """Load feature_meta.json (track encodings, compound stats). Returns {} if missing."""
    path = MODEL_PATH / "feature_meta.json"
    if path.exists():
        try:
            with open(path) as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def load_model(model_name: str):
    """Load a joblib-serialised model from MODEL_PATH/{model_name}.pkl."""
    import joblib
    path = MODEL_PATH / f"{model_name}.pkl"
    if not path.exists():
        raise FileNotFoundError(f"Model not found: {path}")
    return joblib.load(path)


def get_compound_means() -> dict:
    """Return compound stats dict from compound_means.json."""
    path = MODEL_PATH / "compound_means.json"
    if path.exists():
        try:
            with open(path) as f:
                data = json.load(f)
            # Normalise: new format has {compound: {mean,std,..}}, old has {compound: float}
            out = {}
            for k, v in data.items():
                if isinstance(v, dict):
                    out[k] = v
                else:
                    out[k] = {"mean": float(v), "std": 3000.0}
            return out
        except Exception:
            pass
    return DEFAULT_MEANS.copy()


def _track_enc(track: str, meta: dict) -> int:
    """Look up track encoding from meta. Returns median enc if unknown."""
    enc_map = meta.get("track_encode", {})
    if track in enc_map:
        return int(enc_map[track])
    # Fuzzy match by substring
    track_lower = track.lower()
    for k, v in enc_map.items():
        if track_lower in k.lower() or k.lower() in track_lower:
            return int(v)
    # Fallback: median
    vals = list(enc_map.values())
    return int(sorted(vals)[len(vals)//2]) if vals else 10


def _build_feature_row(
    tyre_life: int,
    compound: str,
    lap_number: int,
    stint_number: int,
    session_type: str,
    track: str,
    meta: dict,
) -> list:
    """Build the exact feature vector expected by laptime_predictor."""
    import math
    c_enc = COMPOUND_ENCODE.get(compound.upper(), 1)
    s_enc = SESSION_ENCODE.get(session_type.upper(), 0)
    t_enc = _track_enc(track, meta)
    tl_sq   = tyre_life ** 2
    tl_root = math.sqrt(max(tyre_life, 0))
    is_first = int(lap_number == 1)
    is_out   = int(tyre_life <= 2 and lap_number > 1)

    return [[
        tyre_life, tl_sq, tl_root,
        c_enc, s_enc, t_enc,
        lap_number, float(stint_number), is_first, is_out,
    ]]


# ── Lap Time Prediction ───────────────────────────────────────────────────────

def predict_lap_time(
    tyre_life: int,
    compound: str,
    lap_number: int = 1,
    stint_number: int = 1,
    session_type: str = "R",
    track: str = "",
) -> float:
    """Predict fuel-corrected lap time in milliseconds.

    Returns a unique value per (tyre_life, compound, lap, stint, track, session).
    Falls back gracefully if model not loaded.
    """
    import numpy as np
    compound_upper = compound.upper()
    meta = _load_meta()

    try:
        model = load_model("laptime_predictor")
        feats = _build_feature_row(tyre_life, compound_upper, lap_number,
                                   stint_number, session_type, track, meta)
        pred = float(model.predict(np.array(feats))[0])
        return max(pred, 60_000.0)
    except FileNotFoundError:
        logger.debug("laptime_predictor not found — compound mean fallback")
    except Exception as e:
        logger.warning("laptime_predictor error: %s", e)

    # Fallback: compound mean + tyre-age degradation curve
    means = get_compound_means()
    stats = means.get(compound_upper, {"mean": 90_000.0, "std": 3000.0})
    base  = stats["mean"]
    # Quadratic degradation: ~50ms/lap initially, accelerating after lap 20
    age_penalty = max(0, tyre_life - 3) * 55 + max(0, tyre_life - 20) ** 1.5 * 10
    return max(base + age_penalty, 60_000.0)


# ── Tire Degradation Curve ────────────────────────────────────────────────────

def predict_tire_degradation(
    compound: str,
    tyre_life_range: list,
    track: str = "",
    session_type: str = "R",
) -> list:
    """Return predicted lap times (ms) for each tyre life value.

    Uses per-compound Ridge (smooth) → XGB (contextual) → quadratic fallback.
    """
    import numpy as np
    compound_upper = compound.upper()
    meta = _load_meta()

    # 1. Try per-compound Ridge (smoothest curve)
    try:
        model = load_model(f"tire_degradation_ridge_{compound_upper}")
        X = np.array(tyre_life_range).reshape(-1, 1)
        preds = model.predict(X).tolist()
        return [max(p, 60_000.0) for p in preds]
    except FileNotFoundError:
        pass
    except Exception as e:
        logger.warning("Ridge degradation error for %s: %s", compound_upper, e)

    # 2. Try global XGB with track context
    try:
        model = load_model("tire_degradation_xgb")
        c_enc = COMPOUND_ENCODE.get(compound_upper, 1)
        t_enc = _track_enc(track, meta)
        X = np.array([
            [life, life**2, math.sqrt(max(life,0)), c_enc, t_enc]
            for life in tyre_life_range
        ])
        preds = model.predict(X).tolist()
        return [max(p, 60_000.0) for p in preds]
    except FileNotFoundError:
        pass
    except Exception as e:
        logger.warning("XGB degradation error: %s", e)

    # 3. Quadratic fallback from compound mean
    means = get_compound_means()
    stats = means.get(compound_upper, {"mean": 90_000.0, "std": 3000.0})
    base  = stats["mean"]
    return [
        max(base + max(0, life - 3) * 55 + max(0, life - 20)**1.5 * 10, 60_000.0)
        for life in tyre_life_range
    ]


# ── Race Strategy Simulation ──────────────────────────────────────────────────

def simulate_race_strategy(
    total_laps: int,
    pit_laps: list,
    compounds: list,
    actual_laps: dict,
    pit_time_loss_ms: int = 25_000,
    track: str = "",
    session_type: str = "R",
) -> dict:
    """Simulate total race time for a given pit strategy.

    Uses actual DB lap times where available, predicts the rest per-lap.
    """
    pit_set = set(pit_laps)
    stint_boundaries = [0] + sorted(pit_laps) + [total_laps + 1]
    lap_compound: dict = {}
    for i in range(len(compounds)):
        start = stint_boundaries[i] + 1
        end   = stint_boundaries[min(i + 1, len(stint_boundaries) - 1)]
        cmp   = compounds[i].upper() if i < len(compounds) else "MEDIUM"
        for lap_num in range(start, end + 1):
            lap_compound[lap_num] = cmp

    def stint_for_lap(ln: int) -> int:
        for idx in range(len(pit_laps) + 1):
            if stint_boundaries[idx] + 1 <= ln <= stint_boundaries[idx + 1]:
                return idx
        return 0

    per_lap_times: list = []
    stint_ages: dict = {}

    for lap_num in range(1, total_laps + 1):
        stint_idx = stint_for_lap(lap_num)
        stint_ages[stint_idx] = stint_ages.get(stint_idx, 0) + 1
        tyre_age  = stint_ages[stint_idx]
        compound  = lap_compound.get(lap_num, "MEDIUM")

        if lap_num in actual_laps and actual_laps[lap_num]:
            lap_time = float(actual_laps[lap_num])
        else:
            lap_time = predict_lap_time(
                tyre_age, compound, lap_num, stint_idx + 1, session_type, track
            )

        if lap_num in pit_set:
            lap_time += pit_time_loss_ms

        per_lap_times.append(lap_time)

    return {
        "total_race_time_ms": sum(per_lap_times),
        "per_lap_times_ms":   per_lap_times,
        "pit_stops":          len(pit_laps),
        "compounds_used":     list(dict.fromkeys(
            [lap_compound.get(n, "MEDIUM") for n in range(1, total_laps + 1)]
        )),
    }


# ── Pit Window Prediction ─────────────────────────────────────────────────────

def predict_pit_window(
    current_lap: int,
    total_laps: int,
    current_compound: str,
    current_tyre_life: int,
    track: str = "",
    session_type: str = "R",
) -> dict:
    """Return the recommended pit window using degradation model.

    Evaluates every candidate pit lap and returns the one that minimises
    projected remaining race time.
    """
    remaining_laps = total_laps - current_lap
    if remaining_laps <= 0:
        return {"earliest_lap": current_lap, "optimal_lap": current_lap,
                "latest_lap": current_lap, "reasoning": "Race effectively over."}

    earliest_lap = min(current_lap + 2, total_laps - 8)
    latest_lap   = max(earliest_lap + 2, total_laps - 6)
    compound_upper = current_compound.upper()
    fresh_compound = _suggest_next_compound(compound_upper)

    # Pre-compute stay-out degradation
    stay_range  = list(range(current_tyre_life + 1,
                              current_tyre_life + remaining_laps + 2))
    stay_times  = predict_tire_degradation(compound_upper, stay_range, track, session_type)

    best_lap  = earliest_lap
    best_cost = float("inf")

    for candidate_pit in range(earliest_lap, latest_lap + 1):
        laps_to_pit   = candidate_pit - current_lap
        laps_after_pit = total_laps - candidate_pit

        stay_cost  = sum(stay_times[:laps_to_pit])
        fresh_range = list(range(1, laps_after_pit + 1))
        fresh_times = predict_tire_degradation(fresh_compound, fresh_range, track, session_type)
        fresh_cost  = sum(fresh_times) + 25_000  # pit lane loss

        total_cost = stay_cost + fresh_cost
        if total_cost < best_cost:
            best_cost = total_cost
            best_lap  = candidate_pit

    tyre_age_at_pit = current_tyre_life + (best_lap - current_lap)
    reasoning = (
        f"Optimal pit on lap {best_lap} ({best_lap - current_lap} laps away). "
        f"Current {compound_upper} tyre will be {tyre_age_at_pit} laps old. "
        f"Suggested next compound: {fresh_compound}."
    )

    return {
        "earliest_lap": earliest_lap,
        "optimal_lap":  best_lap,
        "latest_lap":   latest_lap,
        "reasoning":    reasoning,
    }


def _suggest_next_compound(current: str) -> str:
    """SOFT→MEDIUM→HARD, others stay same."""
    return {"SOFT": "MEDIUM", "MEDIUM": "HARD"}.get(current.upper(), current.upper())
