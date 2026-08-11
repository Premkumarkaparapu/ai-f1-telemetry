"""Tests for the AI service layer — MockProvider and factory."""


from backend.app.services.ai_service import (
    AIService,
    MockProvider,
    get_ai_service,
)


class TestMockProvider:
    """Verify MockProvider works without any API keys."""

    def setup_method(self):
        self.provider = MockProvider()

    def test_complete_returns_string(self):
        result = self.provider.complete(
            "You are an F1 engineer",
            "How was VER's pace?",
        )
        assert isinstance(result, str)
        assert len(result) > 10

    def test_complete_json_returns_dict(self):
        result = self.provider.complete_json(
            "Select tools",
            "What was the race pace?",
        )
        assert isinstance(result, dict)
        assert "tools" in result

    def test_complete_json_tool_selection_pace(self):
        result = self.provider.complete_json(
            "Select tools",
            "What was Verstappen's pace?",
        )
        tools = result.get("tools", [])
        assert len(tools) > 0
        tool_names = [t["tool"] for t in tools]
        assert "get_driver_pace" in tool_names

    def test_complete_json_tool_selection_tires(self):
        result = self.provider.complete_json(
            "Select tools",
            "How was tire degradation?",
        )
        tools = result.get("tools", [])
        tool_names = [t["tool"] for t in tools]
        assert "get_tire_degradation" in tool_names

    def test_complete_json_tool_selection_compare(self):
        result = self.provider.complete_json(
            "Select tools",
            "Compare VER vs HAM",
        )
        tools = result.get("tools", [])
        tool_names = [t["tool"] for t in tools]
        assert "compare_drivers" in tool_names

    def test_stream_yields_tokens(self):
        tokens = list(self.provider.stream(
            "You are an F1 engineer",
            "How was the race?",
        ))
        assert len(tokens) > 0
        full = "".join(tokens)
        assert len(full) > 10


class TestGetAIService:
    """Verify the factory function works."""

    def test_returns_ai_service(self):
        service = get_ai_service()
        assert isinstance(service, AIService)

    def test_default_is_mock(self):
        service = get_ai_service()
        assert isinstance(service, MockProvider)
