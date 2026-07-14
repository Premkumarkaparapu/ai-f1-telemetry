"""Smoke test for all ML inference functions."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from ml.inference import (
    predict_lap_time,
    predict_tire_degradation,
    simulate_race_strategy,
    predict_pit_window,
    get_compound_means,
)

print("=== ML Inference Smoke Test ===\n")

# 1. Compound means
means = get_compound_means()
print(f"[1] Compound means: {means}")

# 2. Lap time prediction
for compound in ["SOFT", "MEDIUM", "HARD"]:
    t = predict_lap_time(tyre_life=5, compound=compound, lap_number=10, stint_number=1)
    print(f"[2] predict_lap_time(tyre_life=5, {compound}) = {t/1000:.3f}s")

# 3. Degradation curve (10 laps)
curve = predict_tire_degradation("MEDIUM", list(range(1, 11)))
print(f"[3] Degradation MEDIUM laps 1-10: {[round(t/1000, 2) for t in curve]}")

# 4. Strategy simulation
sim = simulate_race_strategy(
    total_laps=10,
    pit_laps=[5],
    compounds=["SOFT", "MEDIUM"],
    actual_laps={},
    pit_time_loss_ms=25000,
)
total_s = sim["total_race_time_ms"] / 1000
print(f"[4] Strategy sim: {total_s:.1f}s total, {sim['pit_stops']} stop(s)")

# 5. Pit window
pw = predict_pit_window(
    current_lap=20,
    total_laps=57,
    current_compound="SOFT",
    current_tyre_life=18,
)
print(f"[5] Pit window: earliest={pw['earliest_lap']} optimal={pw['optimal_lap']} latest={pw['latest_lap']}")
print(f"    Reasoning: {pw['reasoning'][:80]}...")

print("\n✅ All ML functions OK")
