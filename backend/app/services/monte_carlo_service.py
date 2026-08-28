"""Monte Carlo strategy engine — vectorized F1 race simulations."""

from typing import Optional
import numpy as np

from backend.app.repositories.track_profile_repository import (
    TrackProfileRepository
)
from backend.app.api.v1.security import require_scope  # noqa: F401


class MonteCarloService:
    def __init__(self, track_profile_repo: TrackProfileRepository):
        self.track_profile_repo = track_profile_repo

    def get_track_profile(self, track_name: str) -> dict:
        profile = None
        if track_name:
            profile = self.track_profile_repo.get_by_track(track_name)

        if profile:
            return {
                "safety_car_lambda": profile.safety_car_lambda,
                "vsc_lambda": profile.vsc_lambda,
                "pit_loss_base_ms": profile.pit_loss_base_ms,
                "pit_loss_variance_ms": profile.pit_loss_variance_ms,
                "degradation_multiplier": profile.degradation_multiplier,
                "traffic_lambda": profile.traffic_lambda,
            }

        # Default fallback settings derived from F1 historical averages
        return {
            "safety_car_lambda": 0.005,
            "vsc_lambda": 0.008,
            "pit_loss_base_ms": 25000.0,
            "pit_loss_variance_ms": 2000.0,
            "degradation_multiplier": 1.0,
            "traffic_lambda": 1.2,
        }

    def simulate_strategies(
        self,
        total_laps: int,
        strategies: list[dict],
        track_name: str,
        seed: Optional[int] = None,
        is_test: bool = False
    ) -> list[dict]:
        """Runs 10k simulations per strategy with aligned events."""
        # 1. Initialize RNG
        if seed is not None:
            # Seed parameter is blocked in production unless is_test is True
            rng_seed_val = seed if is_test else None
            rng = np.random.default_rng(seed)
        else:
            rng_seed_val = None
            rng = np.random.default_rng()

        num_sims = 10000
        track_profile = self.get_track_profile(track_name)

        # 2. Pre-generate identical stochastic scenarios
        sc_lambda = track_profile["safety_car_lambda"]
        vsc_lambda = track_profile["vsc_lambda"]
        sc_triggers = rng.poisson(sc_lambda, size=(num_sims, total_laps))
        vsc_triggers = rng.poisson(vsc_lambda, size=(num_sims, total_laps))
        t_coef = rng.normal(1.0, 0.05, size=(num_sims, 1))
        pace_variance = rng.normal(0, 300.0, size=(num_sims, total_laps))
        sc_durations = rng.integers(3, 9, size=(num_sims, total_laps))

        # 3. Simulate each strategy
        results = []
        strategy_race_times = []

        for strat in strategies:
            pit_laps = strat["pit_laps"]
            compounds = strat["compounds"]

            res = self._run_single_simulation(
                total_laps=total_laps,
                pit_laps=pit_laps,
                compounds=compounds,
                track_profile=track_profile,
                num_sims=num_sims,
                rng=rng,
                sc_triggers=sc_triggers,
                vsc_triggers=vsc_triggers,
                t_coef=t_coef,
                pace_variance=pace_variance,
                sc_durations=sc_durations
            )
            strategy_race_times.append(res["race_times"])
            results.append({
                "strategy_name": strat["strategy_name"],
                "pit_laps": pit_laps,
                "compounds": compounds,
                "race_times": res["race_times"],
                "simulated_laps": res["simulated_laps"]
            })

        # 4. Cross-Strategy Comparison (Calculate P(Best))
        if len(strategies) > 0:
            stacked_times = np.column_stack(strategy_race_times)
            best_strategy_indices = np.argmin(stacked_times, axis=1)

            for idx, res in enumerate(results):
                wins = np.sum(best_strategy_indices == idx)
                prob_best = float(wins) / num_sims * 100.0

                race_times_ms = res["race_times"]
                expected_ms = int(np.mean(race_times_ms))
                median_ms = int(np.median(race_times_ms))
                p10_ms = int(np.percentile(race_times_ms, 10))
                p90_ms = int(np.percentile(race_times_ms, 90))

                # Safety car sensitivity calculation
                sc_runs_mask = np.any(sc_triggers > 0, axis=1)
                if np.any(sc_runs_mask) and np.any(~sc_runs_mask):
                    mean_sc = np.mean(race_times_ms[sc_runs_mask])
                    mean_no_sc = np.mean(race_times_ms[~sc_runs_mask])
                    sensitivity_delta = mean_sc - mean_no_sc
                    if sensitivity_delta > 90000.0:
                        sensitivity = "HIGH"
                    elif sensitivity_delta > 40000.0:
                        sensitivity = "MEDIUM"
                    else:
                        sensitivity = "LOW"
                else:
                    sensitivity = "LOW"

                # Probability of finishing (mechanical reliability model)
                prob_finish = round(((1.0 - 0.0002) ** total_laps) * 100.0, 2)

                # Strip out arrays from the user-facing result dictionary
                del res["race_times"]
                del res["simulated_laps"]

                res.update({
                    "expected_race_time_ms": expected_ms,
                    "median_ms": median_ms,
                    "p10_ms": p10_ms,
                    "p90_ms": p90_ms,
                    "probability_best_strategy_percent": round(prob_best, 2),
                    "probability_finish_percent": prob_finish,
                    "safety_car_sensitivity": sensitivity,
                    "simulation_count": num_sims,
                    "rng_seed": rng_seed_val
                })

        return results

    def _run_single_simulation(
        self,
        total_laps: int,
        pit_laps: list[int],
        compounds: list[str],
        track_profile: dict,
        num_sims: int,
        rng: np.random.Generator,
        sc_triggers: np.ndarray,
        vsc_triggers: np.ndarray,
        t_coef: np.ndarray,
        pace_variance: np.ndarray,
        sc_durations: np.ndarray
    ) -> dict:
        pit_set = set(pit_laps)

        # 1. Base predicted lap times
        base_lap_times = np.zeros(total_laps)
        lap_tyre_ages = []

        from ml.inference import predict_lap_time

        stint_idx = 0
        tyre_age = 0
        for lap_num in range(1, total_laps + 1):
            if lap_num - 1 in pit_set:
                stint_idx += 1
                tyre_age = 0
            tyre_age += 1

            cmp = compounds[stint_idx] if stint_idx < len(compounds) else "M"
            lap_tyre_ages.append(tyre_age)

            base_lap_times[lap_num - 1] = predict_lap_time(
                tyre_life=tyre_age,
                compound=cmp,
                lap_number=lap_num,
                stint_number=stint_idx + 1
            )

        lap_tyre_ages = np.array(lap_tyre_ages)
        deg_mult = track_profile.get("degradation_multiplier", 1.0)

        # 2. Simulated baseline times
        term = (lap_tyre_ages.reshape(1, -1) * 15.0) * (t_coef - 1.0)
        simulated_laps = base_lap_times.reshape(1, -1) + term * deg_mult

        # 3. Pit stop crew delays (Gamma distribution)
        num_pits = len(pit_laps)
        pit_loss_base = track_profile.get("pit_loss_base_ms", 25000.0)
        pit_loss_variance = track_profile.get("pit_loss_variance_ms", 2000.0)

        shape_k = 2.0
        scale_theta = np.sqrt(pit_loss_variance / shape_k)

        pit_delays = rng.gamma(shape_k, scale_theta, size=(num_sims, num_pits))
        total_pit_loss = pit_loss_base + pit_delays

        for p_idx, p_lap in enumerate(pit_laps):
            simulated_laps[:, p_lap - 1] += total_pit_loss[:, p_idx]

        # 4. Out-lap traffic & tyre warmup penalties
        traffic_lambda = track_profile.get("traffic_lambda", 1.2)
        for p_lap in pit_laps:
            if p_lap < total_laps:
                traffic_delays = rng.exponential(
                    1000.0 / traffic_lambda, size=num_sims
                )
                warmup_delays = 1500.0 + rng.normal(0, 200.0, size=num_sims)
                simulated_laps[:, p_lap] += traffic_delays + warmup_delays

        # 5. Safety Car / VSC delays
        active_sc_laps = np.zeros(num_sims, dtype=int)
        active_vsc_laps = np.zeros(num_sims, dtype=int)

        sc_delay_per_lap = 35000.0
        vsc_delay_per_lap = 18000.0

        for l_idx in range(total_laps):
            new_sc = (sc_triggers[:, l_idx] > 0) & (active_sc_laps == 0)
            if np.any(new_sc):
                active_sc_laps[new_sc] = sc_durations[new_sc, l_idx]

            new_vsc = (vsc_triggers[:, l_idx] > 0) & (
                active_sc_laps == 0
            ) & (active_vsc_laps == 0)
            if np.any(new_vsc):
                active_vsc_laps[new_vsc] = 1

            sc_mask = active_sc_laps > 0
            simulated_laps[sc_mask, l_idx] += sc_delay_per_lap

            vsc_mask = active_vsc_laps > 0
            simulated_laps[vsc_mask, l_idx] += vsc_delay_per_lap

            active_sc_laps = np.maximum(0, active_sc_laps - 1)
            active_vsc_laps = np.maximum(0, active_vsc_laps - 1)

        # 6. Pace variance
        simulated_laps += pace_variance
        simulated_laps = np.maximum(simulated_laps, 40000.0)

        return {
            "race_times": np.sum(simulated_laps, axis=1),
            "simulated_laps": simulated_laps
        }
