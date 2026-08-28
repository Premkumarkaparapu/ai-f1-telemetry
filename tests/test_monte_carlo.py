"""Unit and integration tests for the Monte Carlo strategy engine."""

import time
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from backend.app.api.v1.security import AuthenticatedUser
from backend.app.database.models import (
    Session as SessionModel, Driver, Lap, TrackProfile
)
from backend.app.main import app
from backend.app.repositories.track_profile_repository import (
    TrackProfileRepository
)
from backend.app.services.monte_carlo_service import MonteCarloService
from tests.conftest import TestingSessionLocal

client = TestClient(app)


@pytest.fixture
def client_fixture():
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def setup_teardown_db():
    db = TestingSessionLocal()
    try:
        db.query(Lap).delete()
        db.query(Driver).delete()
        db.query(SessionModel).delete()
        db.query(TrackProfile).delete()
        db.commit()
    finally:
        db.close()
    yield


def _seed_db_with_track(track_name: str = "Monaco"):
    db = TestingSessionLocal()
    try:
        session = SessionModel(
            year=2023, event_name=f"{track_name} Grand Prix",
            session_type="R", track=track_name, country=track_name,
            total_laps=50
        )
        db.add(session)
        db.flush()

        driver = Driver(
            session_id=session.session_id, code="VER",
            full_name="Max Verstappen", team="Red Bull"
        )
        db.add(driver)
        db.flush()

        lap = Lap(
            driver_id=driver.driver_id, lap_number=1, lap_time_ms=80_000,
            compound="MEDIUM", tyre_life=1
        )
        db.add(lap)

        # Track profile
        profile = TrackProfile(
            track=track_name,
            safety_car_lambda=0.015,
            vsc_lambda=0.02,
            pit_loss_base_ms=25000.0,
            pit_loss_variance_ms=2500.0,
            degradation_multiplier=1.2,
            traffic_lambda=1.5
        )
        db.add(profile)
        db.commit()
        return session.session_id, driver.driver_id
    finally:
        db.close()


def test_monte_carlo_benchmarks_and_stats(client_fixture):
    session_id, driver_id = _seed_db_with_track()
    db = TestingSessionLocal()
    repo = TrackProfileRepository(db)
    service = MonteCarloService(repo)
    db.close()

    strategies = [
        {
            "strategy_name": "Medium -> Hard",
            "pit_laps": [18],
            "compounds": ["MEDIUM", "HARD"]
        }
    ]

    # Warm up caches to exclude initial disk I/O and joblib load from benchmark
    from ml.inference import load_model, _load_meta
    try:
        load_model("laptime_predictor")
    except Exception:
        pass
    try:
        _load_meta()
    except Exception:
        pass

    # Benchmark: Time execution
    start_time = time.perf_counter()
    results = service.simulate_strategies(
        total_laps=50,
        strategies=strategies,
        track_name="Monaco",
        seed=42,
        is_test=True
    )
    end_time = time.perf_counter()
    duration_ms = (end_time - start_time) * 1000.0

    # Ensure latency is under 300ms ceiling (typically ~20-50ms)
    assert duration_ms < 300.0, f"Monte Carlo took: {duration_ms:.2f}ms"

    assert len(results) == 1
    strat = results[0]

    # Exactly 10,000 simulations check
    assert strat["simulation_count"] == 10000

    # P10 < P50 < P90 check
    p10 = strat["p10_ms"]
    median = strat["median_ms"]
    p90 = strat["p90_ms"]
    expected = strat["expected_race_time_ms"]
    assert p10 < median < p90
    assert p10 < expected < p90

    # Non-negative check
    assert expected > 0
    assert median > 0

    # Check that deterministic seed returns reproducible outputs
    results_2 = service.simulate_strategies(
        total_laps=50,
        strategies=strategies,
        track_name="Monaco",
        seed=42,
        is_test=True
    )
    assert results_2[0]["expected_race_time_ms"] == expected
    assert results_2[0]["p10_ms"] == p10
    assert results_2[0]["p90_ms"] == p90


def test_monte_carlo_production_seed_blocked(client_fixture):
    session_id, driver_id = _seed_db_with_track()
    db = TestingSessionLocal()
    repo = TrackProfileRepository(db)
    service = MonteCarloService(repo)
    db.close()

    strategies = [
        {
            "strategy_name": "Medium -> Hard",
            "pit_laps": [18],
            "compounds": ["MEDIUM", "HARD"]
        }
    ]

    # In production, seeds are ignored (rng_seed = None)
    results = service.simulate_strategies(
        total_laps=50,
        strategies=strategies,
        track_name="Monaco",
        seed=42,
        is_test=False
    )
    assert results[0]["rng_seed"] is None

    # Two runs should generate different expected values (independent seeds)
    results_run_1 = service.simulate_strategies(
        total_laps=50,
        strategies=strategies,
        track_name="Monaco",
        seed=None,
        is_test=False
    )
    results_run_2 = service.simulate_strategies(
        total_laps=50,
        strategies=strategies,
        track_name="Monaco",
        seed=None,
        is_test=False
    )
    # They should not be identical
    assert (
        results_run_1[0]["expected_race_time_ms"] !=
        results_run_2[0]["expected_race_time_ms"]
    )


def test_cross_strategy_scenario_alignment(client_fixture):
    # Tests that identical stochastic scenarios are used to compare strategies
    session_id, driver_id = _seed_db_with_track()
    db = TestingSessionLocal()
    repo = TrackProfileRepository(db)
    service = MonteCarloService(repo)
    db.close()

    strategies = [
        {
            "strategy_name": "Strategy A (1-Stop)",
            "pit_laps": [18],
            "compounds": ["MEDIUM", "HARD"]
        },
        {
            "strategy_name": "Strategy B (2-Stop)",
            "pit_laps": [15, 32],
            "compounds": ["MEDIUM", "SOFT", "HARD"]
        }
    ]

    results = service.simulate_strategies(
        total_laps=50,
        strategies=strategies,
        track_name="Monaco",
        seed=42,
        is_test=True
    )
    assert len(results) == 2
    prob_a = results[0]["probability_best_strategy_percent"]
    prob_b = results[1]["probability_best_strategy_percent"]

    # Sum of probabilities must equal 100%
    assert abs(prob_a + prob_b - 100.0) < 0.01


def test_api_endpoint_strategy_compare(client_fixture):
    session_id, driver_id = _seed_db_with_track()
    mock_user = AuthenticatedUser(sub="user", scopes=["strategy:run"])

    req_payload = {
        "session_id": session_id,
        "driver_id": driver_id,
        "strategies": [
            {
                "strategy_name": "Medium -> Hard",
                "pit_laps": [18],
                "compounds": ["MEDIUM", "HARD"]
            },
            {
                "strategy_name": "Soft -> Hard",
                "pit_laps": [12],
                "compounds": ["SOFT", "HARD"]
            }
        ],
        "seed": 42
    }

    with patch(
        "backend.app.api.v1.predictions.require_scope"
    ) as mock_scope:
        # Bypass router-level scopes if any
        mock_scope.return_value = lambda user: mock_user

        response = client_fixture.post(
            "/api/v1/predict/strategy/compare",
            json=req_payload,
            headers={"Authorization": "Bearer mock_token"}
        )

        assert response.status_code == 201
        data = response.json()
        assert data["session_id"] == session_id
        assert data["driver_id"] == driver_id
        assert len(data["results"]) == 2

        # Check results contents
        r1 = data["results"][0]
        assert "expected_race_time_ms" in r1
        assert "probability_best_strategy_percent" in r1
        assert r1["rng_seed"] == 42
