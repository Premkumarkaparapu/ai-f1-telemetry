"""Orchestrator agent — classifies intent and routes to agents.

Intent types:
  DATA_ANALYSIS   → F1 Data Agent (tools + DB queries)
  KNOWLEDGE_QUERY → Knowledge Agent (RAG search)
  HYBRID          → Both agents, merged results
"""

import re

from backend.app.core.logging import get_logger

logger = get_logger(__name__)

# Keywords that strongly signal each intent type
_DATA_KEYWORDS = {
    "pace", "lap", "time", "fastest", "sector", "speed",
    "degrad", "tire", "tyre", "pit", "stop", "stint",
    "strat", "compare", "vs", "versus", "gap", "delta",
    "overtake", "position", "standing", "race summary",
    "telemetry", "throttle", "brake", "drs", "rpm",
}

_KNOWLEDGE_KEYWORDS = {
    "rule", "regulation", "flag", "penalty", "drs zone",
    "safety car", "vsc", "red flag", "track limit",
    "compound", "c1", "c2", "c3", "c4", "c5",
    "undercut", "overcut", "graining", "blistering",
    "circuit", "monza", "silverstone", "monaco",
    "bahrain", "suzuka", "what is", "explain", "how does",
    "why do", "what are",
}


class IntentType:
    """Enum-like container for intent types."""
    DATA_ANALYSIS = "DATA_ANALYSIS"
    KNOWLEDGE_QUERY = "KNOWLEDGE_QUERY"
    HYBRID = "HYBRID"


class Orchestrator:
    """Routes user queries to the appropriate agent(s).

    Classification is purely keyword-based (no LLM call)
    to keep the orchestrator fast and deterministic.
    """

    def classify_intent(self, query: str) -> str:
        """Classify query as DATA, KNOWLEDGE, or HYBRID."""
        q = query.lower()
        words = set(re.findall(r"\w+", q))

        data_score = sum(
            1 for kw in _DATA_KEYWORDS
            if kw in q or kw in words
        )
        knowledge_score = sum(
            1 for kw in _KNOWLEDGE_KEYWORDS
            if kw in q or kw in words
        )

        if data_score > 0 and knowledge_score > 0:
            return IntentType.HYBRID
        if data_score > 0:
            return IntentType.DATA_ANALYSIS
        if knowledge_score > 0:
            return IntentType.KNOWLEDGE_QUERY

        # Default: treat as data analysis if we have a session
        return IntentType.HYBRID

    def route(self, query: str) -> dict:
        """Return routing decision with intent metadata."""
        intent = self.classify_intent(query)

        agents = []
        if intent in (
            IntentType.DATA_ANALYSIS, IntentType.HYBRID,
        ):
            agents.append("data_agent")
        if intent in (
            IntentType.KNOWLEDGE_QUERY, IntentType.HYBRID,
        ):
            agents.append("knowledge_agent")

        logger.info(
            "Orchestrator: intent=%s, agents=%s",
            intent, agents,
        )

        return {
            "intent": intent,
            "agents": agents,
            "query": query,
        }
