"""AI Race Engineer — the main entry point for AI queries.

Orchestrates the full pipeline:
    User query
        → Orchestrator (intent classification)
        → Data Agent (tool execution) + Knowledge Agent (RAG)
        → Explanation Agent (grounded narrative)
        → Structured response
"""

import json
import time

from sqlalchemy.orm import Session

from backend.app.core.logging import get_logger
from backend.app.core.request_context import get_request_id
from backend.app.services.ai_service import (
    AIService, get_ai_service,
)
from backend.app.agents.orchestrator import Orchestrator
from backend.app.agents.data_agent import DataAgent
from backend.app.agents.knowledge_agent import KnowledgeAgent
from backend.app.agents.explanation_agent import ExplanationAgent

logger = get_logger(__name__)


class AIRaceEngineer:
    """Main AI Race Engineer coordinating all agents.

    Usage:
        engineer = AIRaceEngineer(db_session)
        result = engineer.ask(
            "How was Verstappen's pace on mediums?",
            session_id=42,
            driver_code="VER",
        )
    """

    def __init__(
        self,
        db: Session,
        ai_service: AIService | None = None,
    ):
        self.db = db
        self.ai = ai_service or get_ai_service()
        self.orchestrator = Orchestrator()
        self.data_agent = DataAgent(self.ai, db)
        self.knowledge_agent = KnowledgeAgent()
        self.explanation_agent = ExplanationAgent(self.ai)

    def ask(
        self,
        question: str,
        session_id: int,
        driver_code: str | None = None,
    ) -> dict:
        """Process a question through the full pipeline.

        Returns:
            {
                "answer": str,
                "evidence": dict,
                "tools_used": list[str],
                "intent": str,
                "sources": list[str],
                "latency_ms": int,
            }
        """
        import uuid
        start = time.time()

        # 1. Classify intent
        routing = self.orchestrator.route(question)
        intent = routing["intent"]
        agents = routing["agents"]

        # 2. Execute agents
        data_results = {"tools_used": [], "results": {}}
        knowledge_results = {
            "knowledge_found": False,
            "chunks": [],
            "sources": [],
        }

        # Track latencies
        tool_start = time.time()
        if "data_agent" in agents:
            data_results = self.data_agent.execute(
                question, session_id, driver_code,
            )
        tool_latency = int((time.time() - tool_start) * 1000)

        rag_start = time.time()
        if "knowledge_agent" in agents:
            knowledge_results = self.knowledge_agent.execute(
                question,
            )
        rag_latency = int((time.time() - rag_start) * 1000)

        # 3. Generate explanation
        llm_start = time.time()
        explanation = self.explanation_agent.explain(
            question, data_results, knowledge_results,
        )
        llm_latency = int((time.time() - llm_start) * 1000)

        latency = int((time.time() - start) * 1000)

        # Structured JSON logging for observability
        status = "success"
        if "temporarily offline" in explanation["answer"] or "having trouble connecting" in explanation["answer"]:
            status = "fallback"

        log_data = {
            "request_id": get_request_id() or str(uuid.uuid4()),
            "intent": intent,
            "tools_called": data_results["tools_used"],
            "tool_latency_ms": tool_latency,
            "rag_latency_ms": rag_latency,
            "llm_latency_ms": llm_latency,
            "total_latency_ms": latency,
            "status": status,
        }
        logger.info("AI_OBSERVABILITY_LOG: %s", json.dumps(log_data))

        return {
            "answer": explanation["answer"],
            "evidence": explanation["evidence"],
            "tools_used": data_results["tools_used"],
            "intent": intent,
            "sources": explanation["sources"],
            "latency_ms": latency,
        }

    def stream_ask(
        self,
        question: str,
        session_id: int,
        driver_code: str | None = None,
    ):
        """Stream the answer token by token.

        First executes tools (not streamed), then streams
        the explanation.

        Yields SSE-formatted strings: "data: {json}\n\n"
        """
        # 1. Classify and execute tools (non-streaming)
        routing = self.orchestrator.route(question)
        intent = routing["intent"]
        agents = routing["agents"]

        data_results = {"tools_used": [], "results": {}}
        knowledge_results = {
            "knowledge_found": False,
            "chunks": [],
            "sources": [],
        }

        if "data_agent" in agents:
            data_results = self.data_agent.execute(
                question, session_id, driver_code,
            )

        if "knowledge_agent" in agents:
            knowledge_results = self.knowledge_agent.execute(
                question,
            )

        # 2. Send metadata event
        meta = {
            "type": "metadata",
            "intent": intent,
            "tools_used": data_results["tools_used"],
        }
        yield f"data: {json.dumps(meta)}\n\n"

        # 3. Stream explanation
        for token in self.explanation_agent.stream_explain(
            question, data_results, knowledge_results,
        ):
            event = {"type": "token", "content": token}
            yield f"data: {json.dumps(event)}\n\n"

        # 4. Send evidence event
        evidence = self.explanation_agent._extract_evidence(
            data_results.get("results", {}),
        )
        end_event = {
            "type": "done",
            "evidence": evidence,
            "sources": knowledge_results.get("sources", []),
        }
        yield f"data: {json.dumps(end_event)}\n\n"
