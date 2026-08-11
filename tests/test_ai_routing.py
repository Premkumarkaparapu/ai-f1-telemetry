"""Tests for structured AI tool routing and fallback selections."""

from unittest.mock import MagicMock
from backend.app.agents.data_agent import DataAgent
from backend.app.services.ai_service import MockProvider


def test_keyword_fallback_routing_compare():
    ai = MockProvider()
    agent = DataAgent(ai, db=MagicMock())

    # "Compare VER vs HAM"
    selected = agent._select_tools_by_keywords("Compare VER vs HAM", driver_code=None)
    assert len(selected) > 0
    assert selected[0]["tool"] == "compare_drivers"
    assert selected[0]["args"]["driver1_code"] == "VER"
    assert selected[0]["args"]["driver2_code"] == "HAM"


def test_keyword_fallback_routing_pace():
    ai = MockProvider()
    agent = DataAgent(ai, db=MagicMock())

    # "Show Verstappen's pace"
    selected = agent._select_tools_by_keywords("Show VER's pace", driver_code=None)
    assert len(selected) > 0
    assert selected[0]["tool"] == "get_driver_pace"
    assert selected[0]["args"]["driver_code"] == "VER"


def test_llm_structured_routing_success():
    # Mock AI Service returning a pre-defined JSON schema match
    mock_ai = MagicMock()
    mock_ai.complete_json.return_value = {
        "tools": [
            {
                "tool_name": "get_driver_pace",
                "driver_code": "VER",
                "start_lap": 1,
                "end_lap": 10
            }
        ]
    }

    agent = DataAgent(mock_ai, db=MagicMock())
    selected = agent._select_tools_via_llm(
        "How was VER pace in the opening laps?",
        driver_code="VER",
    )

    assert len(selected) == 1
    assert selected[0]["tool"] == "get_driver_pace"
    assert selected[0]["args"]["driver_code"] == "VER"
    assert selected[0]["args"]["start_lap"] == 1
    assert selected[0]["args"]["end_lap"] == 10
