"""Explanation Agent — generates intelligent F1 responses using real AI.

Receives tool results + knowledge chunks + original question,
then uses Gemini to produce a natural, knowledgeable F1 response.
Can answer ANY F1 question — general knowledge, strategy, history, rules, etc.
"""

import json

from backend.app.core.logging import get_logger
from backend.app.services.ai_service import AIService

logger = get_logger(__name__)

_EXPLANATION_SYSTEM_PROMPT = """You are an expert F1 Race Engineer AI assistant.
You possess deep knowledge of:
- Formula 1 racing strategy, tire management, pit stops, undercuts/overcuts
- All F1 drivers, teams, championships, and history (past and present)
- Technical regulations, DRS, fuel loads, aero, power units
- Circuit characteristics, weather effects, safety cars
- Telemetry analysis, sector times, lap time interpretation
- Race craft, overtaking, defending, tire degradation patterns

INSTRUCTIONS:
1. Answer the user's question naturally and conversationally.
2. If analytical data is provided below, USE it to ground your answer with real numbers.
3. If no data is provided, use your F1 knowledge to give a helpful, accurate answer.
4. Be specific — cite lap times, sector splits, tire compounds when available.
5. Keep responses concise (2-4 paragraphs) but informative.
6. Use proper F1 terminology naturally.
7. If asked about something outside F1, politely redirect to F1 topics.
8. When data shows something interesting (fastest lap, degradation trend,
   strategy gap), highlight it.

{data_section}
"""

_DATA_SECTION_TEMPLATE = """
ANALYTICAL DATA FROM THIS SESSION:
{tool_results}

KNOWLEDGE BASE CONTEXT:
{knowledge_context}
"""

_NO_DATA_SECTION = """
Note: No specific session data was queried for this question. Answer from your F1 expertise.
"""


class ExplanationAgent:
    """Generates intelligent F1 responses using real AI."""

    def __init__(self, ai_service: AIService):
        self.ai = ai_service

    def explain(
        self,
        query: str,
        tool_results: dict,
        knowledge_results: dict,
    ) -> dict:
        """Generate an AI-powered explanation.

        Returns:
            {
                "answer": str,
                "evidence": [...],
                "sources": [...],
            }
        """
        system = self._build_system_prompt(tool_results, knowledge_results)

        try:
            answer = self.ai.complete(system, query)
        except Exception as exc:
            logger.error("ExplanationAgent failed: %s", exc)
            answer = self._fallback_explanation(query, tool_results)

        evidence = self._extract_evidence(
            tool_results.get("results", {}),
        )
        sources = knowledge_results.get("sources", [])

        return {
            "answer": answer,
            "evidence": evidence,
            "sources": sources,
        }

    def stream_explain(
        self,
        query: str,
        tool_results: dict,
        knowledge_results: dict,
    ):
        """Stream the explanation token by token."""
        system = self._build_system_prompt(tool_results, knowledge_results)

        try:
            for token in self.ai.stream(system, query):
                yield token
        except Exception as exc:
            logger.error("Stream explain failed: %s", exc)
            yield self._fallback_explanation(query, tool_results)

    def _build_system_prompt(self, tool_results: dict, knowledge_results: dict) -> str:
        """Build the system prompt with or without data context."""
        has_tool_data = bool(tool_results.get("results", {}))
        has_knowledge = bool(knowledge_results.get("chunks", []))

        if has_tool_data or has_knowledge:
            tool_text = json.dumps(
                tool_results.get("results", {}),
                indent=2,
                default=str,
            )[:4000]

            chunks = knowledge_results.get("chunks", [])
            knowledge_text = "\n\n".join(
                f"[{c['source']} - {c['section']}]\n{c['content']}"
                for c in chunks[:3]
            ) or "No relevant knowledge found."

            data_section = _DATA_SECTION_TEMPLATE.format(
                tool_results=tool_text,
                knowledge_context=knowledge_text[:2000],
            )
        else:
            data_section = _NO_DATA_SECTION

        return _EXPLANATION_SYSTEM_PROMPT.format(data_section=data_section)

    def _extract_evidence(self, results: dict) -> dict:
        """Pull key metrics from tool results into a flat key-value dictionary."""
        evidence = {}
        for tool_name, data in results.items():
            if isinstance(data, dict) and "error" not in data:
                metrics = self._pick_metrics(data)
                evidence.update(metrics)
        return evidence

    def _pick_metrics(self, data: dict) -> dict:
        """Select the most important metrics from a result."""
        keys_of_interest = {
            "avg_lap_time_ms", "avg_lap_time_str",
            "fastest_lap_ms", "fastest_lap_str",
            "median_lap_time_ms", "valid_laps",
            "delta_ms", "faster_driver",
            "degradation_per_lap_ms", "compound",
            "earliest_lap", "optimal_lap", "latest_lap",
            "total_race_time_ms", "num_stops",
            "lap_times_count", "drivers_count",
        }
        metrics = {}
        for key, val in data.items():
            if key in keys_of_interest:
                metrics[key] = val
            elif isinstance(val, list) and val:
                if isinstance(val[0], dict):
                    metrics[key + "_count"] = len(val)
        return metrics

    def _fallback_explanation(self, query: str, tool_results: dict) -> str:
        """Generate a helpful fallback when LLM is unavailable."""
        results = tool_results.get("results", {})
        parts = []
        for tool_name, data in results.items():
            if isinstance(data, dict) and "error" not in data:
                if "avg_lap_time_str" in data:
                    parts.append(
                        f"{data.get('driver', 'Driver')}: "
                        f"avg {data['avg_lap_time_str']}"
                    )
                if "faster_driver" in data:
                    parts.append(
                        f"{data['faster_driver']} was faster "
                        f"by {data.get('delta_ms', 'N/A')}ms"
                    )

        if parts:
            return "Analysis: " + ". ".join(parts) + "."
        return (
            "I'm having trouble connecting to the AI service right now. "
            "Please try again in a moment, or ask a specific data question "
            "like 'What was VER's pace?' which I can answer from the database directly."
        )
