"""Tests for the F1 analytical tools and orchestrator."""


from backend.app.agents.orchestrator import (
    Orchestrator,
    IntentType,
)
from backend.app.tools.f1_tools import TOOL_REGISTRY
from backend.app.services.rag_service import RAGService


class TestToolRegistry:
    """Verify tool registry is complete and well-formed."""

    def test_registry_has_all_tools(self):
        expected = {
            "get_driver_pace",
            "get_tire_degradation",
            "get_sector_performance",
            "compare_drivers",
            "get_pit_window",
            "get_strategy_comparison",
            "get_race_summary",
        }
        assert set(TOOL_REGISTRY.keys()) == expected

    def test_each_tool_has_func(self):
        for name, meta in TOOL_REGISTRY.items():
            assert "func" in meta, f"{name} missing func"
            assert callable(meta["func"])

    def test_each_tool_has_description(self):
        for name, meta in TOOL_REGISTRY.items():
            assert "description" in meta, (
                f"{name} missing description"
            )
            assert len(meta["description"]) > 10

    def test_each_tool_has_required_args(self):
        for name, meta in TOOL_REGISTRY.items():
            assert "required_args" in meta
            assert "session_id" in meta["required_args"]


class TestOrchestrator:
    """Verify intent classification works."""

    def setup_method(self):
        self.orch = Orchestrator()

    def test_data_intent(self):
        result = self.orch.classify_intent(
            "What was Hamilton's lap pace?"
        )
        assert result in (
            IntentType.DATA_ANALYSIS,
            IntentType.HYBRID,
        )

    def test_knowledge_intent(self):
        result = self.orch.classify_intent(
            "What are the DRS regulations?"
        )
        assert result in (
            IntentType.KNOWLEDGE_QUERY,
            IntentType.HYBRID,
        )

    def test_hybrid_intent(self):
        result = self.orch.classify_intent(
            "Why was the lap time penalty applied?"
        )
        # This has both "lap time" (data) and "penalty" (knowledge)
        assert result == IntentType.HYBRID

    def test_route_returns_agents(self):
        result = self.orch.route("Show me VER's pace data")
        assert "intent" in result
        assert "agents" in result
        assert len(result["agents"]) > 0

    def test_route_data_includes_data_agent(self):
        result = self.orch.route("What is the lap time?")
        assert "data_agent" in result["agents"]

    def test_route_knowledge_includes_knowledge_agent(self):
        result = self.orch.route(
            "Explain the safety car regulations"
        )
        assert "knowledge_agent" in result["agents"]


class TestRAGService:
    """Verify RAG service loads and searches knowledge."""

    def setup_method(self):
        self.rag = RAGService()

    def test_loads_documents(self):
        # Force loading
        self.rag._load_knowledge()
        assert self.rag._loaded is True

    def test_search_returns_list(self):
        results = self.rag.search("tire degradation")
        assert isinstance(results, list)

    def test_search_results_have_metadata(self):
        results = self.rag.search("DRS regulations")
        for r in results:
            assert "content" in r
            assert "source" in r
            assert "category" in r
            assert "score" in r

    def test_categories_exist(self):
        cats = self.rag.get_categories()
        assert isinstance(cats, list)
