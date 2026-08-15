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
