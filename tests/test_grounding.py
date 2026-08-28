"""Tests for numerical grounding validation.

Ensures that the ExplanationAgent's evidence field contains the exact numerical
values returned by the database/analytics tools, without the LLM fabricating
or hallucinating those metrics.
"""

from unittest.mock import MagicMock
from backend.app.agents.explanation_agent import ExplanationAgent


def test_explanation_agent_evidence_grounding():
    # Mock tool results from analytics tools
    tool_results = {
        "tools_used": ["get_driver_pace", "get_tire_degradation"],
        "results": {
            "get_driver_pace": {
                "driver": "VER",
                "avg_lap_time_ms": 94210.0,
                "avg_lap_time_str": "1:34.210",
                "valid_laps": 45
            },
            "get_tire_degradation": {
                "driver": "VER",
                "degradation_per_lap_ms": 78.4,
                "compound": "MEDIUM"
            }
        }
    }

    # Mock RAG results
    knowledge_results = {"chunks": [], "sources": []}

    # Mock AI response
    mock_ai = MagicMock()
    mock_ai.complete.return_value = (
        "Verstappen had strong pace averaging 1:34.210 with moderate degradation."
    )

    agent = ExplanationAgent(mock_ai)
    explanation = agent.explain(
        "Tell me about VER's pace",
        tool_results,
        knowledge_results,
    )

    evidence = explanation["evidence"]

    # Assertions: Verify evidence JSON EXACTLY matches raw tool results!
    assert evidence["avg_lap_time_ms"] == 94210.0
    assert evidence["degradation_per_lap_ms"] == 78.4
    assert evidence["compound"] == "MEDIUM"
    assert evidence["valid_laps"] == 45
    assert evidence["avg_lap_time_str"] == "1:34.210"


def test_explanation_agent_monte_carlo_grounding():
    # Mock nested tool results from Monte Carlo comparisons
    tool_results = {
        "tools_used": ["compare_strategies"],
        "results": {
            "compare_strategies": {
                "session_id": 1,
                "driver_id": 2,
                "results": [
                    {
                        "strategy_name": "Medium -> Hard",
                        "pit_laps": [18],
                        "compounds": ["MEDIUM", "HARD"],
                        "expected_race_time_ms": 5503200,
                        "median_ms": 5498000,
                        "p10_ms": 5431000,
                        "p90_ms": 5589000,
                        "probability_best_strategy_percent": 78.4,
                        "probability_finish_percent": 99.8,
                        "safety_car_sensitivity": "HIGH",
                        "simulation_count": 10000
                    }
                ]
            }
        }
    }

    # Mock RAG results
    knowledge_results = {"chunks": [], "sources": []}

    # Mock AI response
    mock_ai = MagicMock()
    mock_ai.complete.return_value = (
        "Grounding check response."
    )

    agent = ExplanationAgent(mock_ai)
    explanation = agent.explain(
        "Compare Max's strategy",
        tool_results,
        knowledge_results,
    )

    evidence = explanation["evidence"]

    # Assertions: Verify nested Monte Carlo metrics are correctly extracted!
    assert evidence["expected_race_time_ms"] == 5503200
    assert evidence["median_ms"] == 5498000
    assert evidence["p10_ms"] == 5431000
    assert evidence["p90_ms"] == 5589000
    assert evidence["probability_best_strategy_percent"] == 78.4
    assert evidence["probability_finish_percent"] == 99.8
    assert evidence["safety_car_sensitivity"] == "HIGH"
    assert evidence["simulation_count"] == 10000
