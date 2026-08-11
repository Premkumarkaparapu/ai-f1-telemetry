"""F1 analytical tools — deterministic, DB-backed calculations.

Each tool:
  1. Accepts a SQLAlchemy Session as its first argument.
  2. Resolves driver codes via DriverRepository.
  3. Returns a plain dict with structured results.
  4. NEVER generates raw SQL — always uses existing repos.

The LLM is responsible for selecting which tools to call;
Python is responsible for computing the numbers.
"""

from statistics import median
from typing import Optional

from sqlalchemy.orm import Session

from backend.app.core.logging import get_logger
from backend.app.repositories.driver_repository import (
    DriverRepository,
)
from backend.app.repositories.lap_repository import LapRepository
from backend.app.repositories.session_repository import (
    SessionRepository,
)

logger = get_logger(__name__)


# ── Helpers ───────────────────────────────────────────────────────────


def _resolve_driver(db: Session, session_id: int, code: str):
    """Return Driver ORM object or None."""
    repo = DriverRepository(db)
    return repo.get_by_code(session_id, code)


def _ms_to_str(ms: int | float | None) -> str:
    """Format milliseconds as M:SS.mmm."""
    if ms is None:
        return "N/A"
    total_s = ms / 1000
    mins = int(total_s // 60)
    secs = total_s - mins * 60
    return f"{mins}:{secs:06.3f}"


# ── Tool 1: Driver Pace ──────────────────────────────────────────────


def get_driver_pace(
    db: Session,
    session_id: int,
    driver_code: str,
    start_lap: Optional[int] = None,
    end_lap: Optional[int] = None,
) -> dict:
    """Calculate pace metrics for a driver over a lap range.

    Returns avg, median, fastest lap time and per-lap breakdown.
    """
    driver = _resolve_driver(db, session_id, driver_code)
    if not driver:
        return {"error": f"Driver {driver_code} not found"}

    repo = LapRepository(db)
    laps = repo.get_by_driver(driver.driver_id, valid_only=True)

    if start_lap:
        laps = [l for l in laps if l.lap_number >= start_lap]
    if end_lap:
        laps = [l for l in laps if l.lap_number <= end_lap]

    times = [l.lap_time_ms for l in laps if l.lap_time_ms]
    if not times:
        return {
            "driver": driver_code,
            "error": "No valid lap times",
        }

    avg = sum(times) / len(times)
    med = median(times)
    fastest = min(times)

    lap_data = [
        {
            "lap": l.lap_number,
            "time_ms": l.lap_time_ms,
            "time_str": _ms_to_str(l.lap_time_ms),
            "compound": l.compound,
            "tyre_life": l.tyre_life,
        }
        for l in laps
        if l.lap_time_ms
    ]

    return {
        "driver": driver_code,
        "team": driver.team,
        "avg_lap_time_ms": round(avg, 1),
        "avg_lap_time_str": _ms_to_str(avg),
        "median_lap_time_ms": round(med, 1),
        "fastest_lap_ms": fastest,
        "fastest_lap_str": _ms_to_str(fastest),
        "valid_laps": len(times),
        "lap_range": f"{start_lap or 1}-{end_lap or 'end'}",
        "lap_times": lap_data,
    }


# ── Tool 2: Tire Degradation ─────────────────────────────────────────


def get_tire_degradation(
    db: Session,
    session_id: int,
    driver_code: str,
) -> dict:
    """Analyze tire degradation per stint.

    For each stint, compute the pace drop per lap on that
    compound by fitting a simple linear trend to lap times.
    """
    driver = _resolve_driver(db, session_id, driver_code)
    if not driver:
        return {"error": f"Driver {driver_code} not found"}

    lap_repo = LapRepository(db)
    laps = lap_repo.get_by_driver(
        driver.driver_id, valid_only=True,
    )
    stints = lap_repo.get_stints(driver.driver_id, session_id)

    stint_data = []
    for stint in stints:
        stint_laps = [
            l for l in laps
            if l.stint_number == stint.stint_number
            and l.lap_time_ms
        ]
        if len(stint_laps) < 2:
            continue

        times = [l.lap_time_ms for l in stint_laps]
        n = len(times)

        # Simple linear regression slope (ms per lap)
        x_mean = (n - 1) / 2.0
        y_mean = sum(times) / n
        num = sum(
            (i - x_mean) * (t - y_mean)
            for i, t in enumerate(times)
        )
        den = sum((i - x_mean) ** 2 for i in range(n))
        slope = num / den if den else 0.0

        stint_data.append({
            "stint_number": stint.stint_number,
            "compound": stint.compound,
            "start_lap": stint.start_lap,
            "end_lap": stint.end_lap,
            "stint_length": n,
            "degradation_per_lap_ms": round(slope, 1),
            "total_pace_loss_ms": round(slope * (n - 1), 1),
            "avg_lap_time_ms": round(y_mean, 1),
            "avg_lap_time_str": _ms_to_str(y_mean),
        })

    return {
        "driver": driver_code,
        "team": driver.team,
        "stints": stint_data,
    }


# ── Tool 3: Sector Performance ───────────────────────────────────────


def get_sector_performance(
    db: Session,
    session_id: int,
    driver_code: str,
) -> dict:
    """Return average and best sector times for a driver."""
    driver = _resolve_driver(db, session_id, driver_code)
    if not driver:
        return {"error": f"Driver {driver_code} not found"}

    repo = LapRepository(db)
    laps = repo.get_by_driver(driver.driver_id, valid_only=True)

    s1 = [l.sector1_ms for l in laps if l.sector1_ms]
    s2 = [l.sector2_ms for l in laps if l.sector2_ms]
    s3 = [l.sector3_ms for l in laps if l.sector3_ms]

    def _stats(vals):
        if not vals:
            return {"avg_ms": None, "best_ms": None}
        return {
            "avg_ms": round(sum(vals) / len(vals), 1),
            "best_ms": min(vals),
        }

    return {
        "driver": driver_code,
        "team": driver.team,
        "sector1": _stats(s1),
        "sector2": _stats(s2),
        "sector3": _stats(s3),
    }


# ── Tool 4: Compare Drivers ──────────────────────────────────────────


def compare_drivers(
    db: Session,
    session_id: int,
    driver1_code: str,
    driver2_code: str,
) -> dict:
    """Head-to-head pace comparison between two drivers."""
    p1 = get_driver_pace(db, session_id, driver1_code)
    p2 = get_driver_pace(db, session_id, driver2_code)

    if "error" in p1 or "error" in p2:
        return {"driver1": p1, "driver2": p2, "error": True}

    delta = p1["avg_lap_time_ms"] - p2["avg_lap_time_ms"]
    faster = driver1_code if delta < 0 else driver2_code

    return {
        "driver1": {
            "code": driver1_code,
            "team": p1.get("team"),
            "avg_lap_time_ms": p1["avg_lap_time_ms"],
            "fastest_lap_ms": p1["fastest_lap_ms"],
        },
        "driver2": {
            "code": driver2_code,
            "team": p2.get("team"),
            "avg_lap_time_ms": p2["avg_lap_time_ms"],
            "fastest_lap_ms": p2["fastest_lap_ms"],
        },
        "delta_ms": round(abs(delta), 1),
        "faster_driver": faster,
    }


# ── Tool 5: Pit Window ───────────────────────────────────────────────


def get_pit_window_tool(
    db: Session,
    session_id: int,
    driver_code: str,
    current_lap: int = 1,
) -> dict:
    """Calculate recommended pit window for a driver.

    Uses degradation analysis + pit time loss heuristic.
    """
    driver = _resolve_driver(db, session_id, driver_code)
    if not driver:
        return {"error": f"Driver {driver_code} not found"}

    repo = LapRepository(db)
    laps = repo.get_by_driver(driver.driver_id, valid_only=True)

    if not laps:
        return {"error": "No laps found"}

    total_laps = max(l.lap_number for l in laps)

    # Use degradation to estimate crossover
    deg = get_tire_degradation(db, session_id, driver_code)
    stints = deg.get("stints", [])

    if stints:
        current_stint = stints[-1]
        deg_rate = current_stint.get(
            "degradation_per_lap_ms", 50,
        )
        compound = current_stint.get("compound", "MEDIUM")
    else:
        deg_rate = 50
        compound = "MEDIUM"

    # Heuristic pit window
    pit_loss_ms = 23000  # ~23s average
    crossover_laps = int(pit_loss_ms / max(deg_rate, 1))
    crossover_laps = min(crossover_laps, 35)
    crossover_laps = max(crossover_laps, 10)

    earliest = max(current_lap + 3, crossover_laps - 5)
    optimal = crossover_laps
    latest = min(crossover_laps + 5, total_laps - 3)

    earliest = min(earliest, total_laps - 5)
    latest = max(latest, earliest + 1)

    reasoning = (
        f"Current compound: {compound}. "
        f"Degradation rate: {deg_rate:.0f} ms/lap. "
        f"Pit time loss: ~{pit_loss_ms / 1000:.0f}s. "
        f"Crossover at ~lap {crossover_laps}. "
        f"Recommend pitting laps {earliest}-{latest}."
    )

    return {
        "driver": driver_code,
        "current_lap": current_lap,
        "earliest_lap": earliest,
        "optimal_lap": optimal,
        "latest_lap": latest,
        "compound": compound,
        "degradation_rate_ms": round(deg_rate, 1),
        "reasoning": reasoning,
    }


# ── Tool 6: Strategy Comparison ──────────────────────────────────────


def get_strategy_comparison(
    db: Session,
    session_id: int,
    driver_code: str,
) -> dict:
    """Compare the actual strategy vs. alternatives."""
    driver = _resolve_driver(db, session_id, driver_code)
    if not driver:
        return {"error": f"Driver {driver_code} not found"}

    lap_repo = LapRepository(db)
    laps = lap_repo.get_by_driver(
        driver.driver_id, valid_only=True,
    )
    stints = lap_repo.get_stints(driver.driver_id, session_id)
    pitstops = lap_repo.get_pitstops(
        driver.driver_id, session_id,
    )

    actual_compounds = [s.compound for s in stints]
    pit_laps = [p.lap_number for p in pitstops]
    pit_durations = [p.duration_ms for p in pitstops]

    times = [l.lap_time_ms for l in laps if l.lap_time_ms]
    total = sum(times) + sum(d for d in pit_durations if d)

    return {
        "driver": driver_code,
        "actual_strategy": {
            "compounds": actual_compounds,
            "pit_laps": pit_laps,
            "pit_durations_ms": pit_durations,
            "total_race_time_ms": total,
            "num_stops": len(pit_laps),
        },
        "alternative_strategies": [
            {
                "name": "1-stop MEDIUM→HARD",
                "description": (
                    "Single stop around lap "
                    f"{max(l.lap_number for l in laps) // 2}"
                ),
            },
            {
                "name": "2-stop SOFT→MEDIUM→SOFT",
                "description": (
                    "Aggressive strategy with two short stints"
                ),
            },
        ],
    }


# ── Tool 7: Race Summary ─────────────────────────────────────────────


def get_race_summary(
    db: Session,
    session_id: int,
) -> dict:
    """Generate a full race summary with all drivers."""
    sess_repo = SessionRepository(db)
    session = sess_repo.get_by_id(session_id)
    if not session:
        return {"error": f"Session {session_id} not found"}

    standings = sess_repo.get_standings(session_id)

    return {
        "event_name": session.event_name,
        "year": session.year,
        "track": session.track,
        "country": session.country,
        "total_laps": session.total_laps,
        "drivers": [
            {
                "position": s["position"],
                "code": s["driver_code"],
                "team": s["team"],
                "team_color": s["team_color"],
                "avg_pace_ms": (
                    round(s["avg_lap_time_ms"], 1)
                    if s["avg_lap_time_ms"] else None
                ),
                "fastest_lap_ms": s["fastest_lap_ms"],
                "pit_stops": s["pit_stop_count"],
            }
            for s in standings
        ],
    }


# ── Tool Registry ────────────────────────────────────────────────────

TOOL_REGISTRY: dict[str, dict] = {
    "get_driver_pace": {
        "func": get_driver_pace,
        "description": (
            "Calculate pace metrics (average, median, fastest) "
            "for a driver, optionally within a lap range."
        ),
        "required_args": ["session_id", "driver_code"],
        "optional_args": ["start_lap", "end_lap"],
    },
    "get_tire_degradation": {
        "func": get_tire_degradation,
        "description": (
            "Analyze tire degradation per stint — returns "
            "degradation rate in ms/lap for each compound."
        ),
        "required_args": ["session_id", "driver_code"],
        "optional_args": [],
    },
    "get_sector_performance": {
        "func": get_sector_performance,
        "description": (
            "Return average and best sector times for a driver."
        ),
        "required_args": ["session_id", "driver_code"],
        "optional_args": [],
    },
    "compare_drivers": {
        "func": compare_drivers,
        "description": (
            "Head-to-head comparison of two drivers — pace "
            "delta, fastest laps, and who was quicker."
        ),
        "required_args": [
            "session_id", "driver1_code", "driver2_code",
        ],
        "optional_args": [],
    },
    "get_pit_window": {
        "func": get_pit_window_tool,
        "description": (
            "Calculate the optimal pit window for a driver "
            "based on degradation rate and pit time loss."
        ),
        "required_args": ["session_id", "driver_code"],
        "optional_args": ["current_lap"],
    },
    "get_strategy_comparison": {
        "func": get_strategy_comparison,
        "description": (
            "Compare the actual race strategy vs. "
            "alternative strategies for a driver."
        ),
        "required_args": ["session_id", "driver_code"],
        "optional_args": [],
    },
    "get_race_summary": {
        "func": get_race_summary,
        "description": (
            "Full race summary — event info, standings, "
            "each driver's pace and pit stop count."
        ),
        "required_args": ["session_id"],
        "optional_args": [],
    },
}
