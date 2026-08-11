"""F1 Data Agent — selects and executes analytical tools.

Receives a user query + session context, selects the appropriate F1 tools
using structured AI routing, executes them against the database, and returns
the results. Falls back to keyword matching if structured routing fails.
"""

import re
from typing import Optional, Union, Literal
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.app.core.logging import get_logger
from backend.app.services.ai_service import AIService
from backend.app.tools.f1_tools import TOOL_REGISTRY

logger = get_logger(__name__)


# ── Structured AI Tool Routing Schemas ────────────────────────────────────────

class DriverPaceInput(BaseModel):
    tool_name: Literal["get_driver_pace"] = "get_driver_pace"
    driver_code: str = Field(..., description="3-letter driver code, e.g. VER, HAM, LEC")
    start_lap: Optional[int] = Field(None, description="Start lap number for pace filter")
    end_lap: Optional[int] = Field(None, description="End lap number for pace filter")


class CompareDriversInput(BaseModel):
    tool_name: Literal["compare_drivers"] = "compare_drivers"
    driver1_code: str = Field(..., description="First driver's 3-letter code, e.g. VER")
    driver2_code: str = Field(..., description="Second driver's 3-letter code, e.g. HAM")


class TireDegradationInput(BaseModel):
    tool_name: Literal["get_tire_degradation"] = "get_tire_degradation"
    driver_code: str = Field(..., description="Driver's 3-letter code to analyze tyre degradation")


class SectorPerformanceInput(BaseModel):
    tool_name: Literal["get_sector_performance"] = "get_sector_performance"
    driver_code: str = Field(..., description="Driver's 3-letter code to analyze sector times")


class PitWindowInput(BaseModel):
    tool_name: Literal["get_pit_window"] = "get_pit_window"
    driver_code: str = Field(..., description="Driver's 3-letter code to predict pit window")
    current_lap: int = Field(20, description="Current race lap number (defaults to 20)")


class StrategyComparisonInput(BaseModel):
    tool_name: Literal["get_strategy_comparison"] = "get_strategy_comparison"
    driver_code: str = Field(..., description="Driver's 3-letter code to simulate strategy alternatives")


class RaceSummaryInput(BaseModel):
    tool_name: Literal["get_race_summary"] = "get_race_summary"


class RoutingDecision(BaseModel):
    """Collection of F1 tools to execute to answer the user query."""
    tools: list[Union[
        DriverPaceInput,
        CompareDriversInput,
        TireDegradationInput,
        SectorPerformanceInput,
        PitWindowInput,
        StrategyComparisonInput,
        RaceSummaryInput
    ]] = Field(default_factory=list, description="F1 analytical tools to run")


# System prompt for structured routing
_ROUTING_SYSTEM_PROMPT = """You are an F1 Race Strategy & Telemetry routing agent.
Given a user query, identify which F1 analytics tools must be called to provide data for the answer.
Return the structured tools list. Be extremely conservative and only call tools directly relevant to the user query.
"""


class DataAgent:
    """Executes F1 analytical tools based on user queries."""

    def __init__(self, ai_service: AIService, db: Session):
        self.ai = ai_service
        self.db = db

    def _extract_driver_codes(self, query: str) -> list[str]:
        """Extract 3-letter driver codes from query."""
        codes = re.findall(r"\b([A-Z]{3})\b", query.upper())
        known = {
            "VER", "HAM", "LEC", "NOR", "PIA", "SAI",
            "RUS", "PER", "ALO", "STR", "GAS", "OCO",
            "TSU", "RIC", "HUL", "MAG", "ALB", "SAR",
            "BOT", "ZHO", "LAW", "HAD", "BEA", "DOO",
            "ANT", "BOR", "COL", "DRU", "ISA", "KIM",
        }
        return [c for c in codes if c in known]

    def _select_tools_by_keywords(self, query: str, driver_code: str | None) -> list[dict]:
        """Select tools based on keyword matching — fallback router."""
        q = query.lower()
        tools = []
        codes = self._extract_driver_codes(query)
        code = driver_code or (codes[0] if codes else None)

        if any(w in q for w in ("compare", "vs", "versus", "against", "better")):
            code2 = codes[1] if len(codes) > 1 else "HAM"
            tools.append({"tool": "compare_drivers", "args": {
                "driver1_code": code or "VER", "driver2_code": code2,
            }})
        if any(w in q for w in ("pace", "fast", "speed", "time", "lap time", "average")):
            tools.append({"tool": "get_driver_pace", "args": {
                "driver_code": code or "VER",
            }})
        if any(w in q for w in ("tire", "tyre", "degrad", "wear", "compound")):
            tools.append({"tool": "get_tire_degradation", "args": {
                "driver_code": code or "VER",
            }})
        if any(w in q for w in ("sector", "s1", "s2", "s3", "mini")):
            tools.append({"tool": "get_sector_performance", "args": {
                "driver_code": code or "VER",
            }})
        if any(w in q for w in ("pit", "stop", "window", "undercut", "overcut")):
            tools.append({"tool": "get_pit_window", "args": {
                "driver_code": code or "VER", "current_lap": 20,
            }})
        if any(w in q for w in ("strat", "plan", "one stop", "two stop")):
            tools.append({"tool": "get_strategy_comparison", "args": {
                "driver_code": code or "VER",
            }})
        if not tools:
            tools.append({"tool": "get_race_summary", "args": {}})

        return tools

    def _select_tools_via_llm(self, query: str, driver_code: str | None) -> list[dict]:
        """Query Gemini using structured Pydantic tool routing."""
        user_msg = f"Query: {query}"
        if driver_code:
            user_msg += f"\nActive context driver: {driver_code}"

        try:
            logger.info("DataAgent: invoking structured tool routing decision")
            res = self.ai.complete_json(
                system_prompt=_ROUTING_SYSTEM_PROMPT,
                user_prompt=user_msg,
                schema=RoutingDecision
            )
            # Reformat decision list to match the execution list format
            tools = []
            for t in res.get("tools", []):
                name = t.get("tool_name")
                if not name:
                    continue
                args = {k: v for k, v in t.items() if k != "tool_name"}
                tools.append({"tool": name, "args": args})
            return tools
        except Exception as exc:
            logger.warning("Structured tool routing failed, using keywords fallback: %s", exc)
            return []

    def execute(
        self,
        query: str,
        session_id: int,
        driver_code: str | None = None,
    ) -> dict:
        """Select and execute tools for the given query.

        Returns:
            {
                "tools_used": ["tool_name", ...],
                "results": {tool_name: result_dict, ...},
            }
        """
        # 1. Dual Router Strategy: Try Structured routing, fall back to Keyword routing
        selected = []
        if type(self.ai).__name__ == "GeminiProvider":
            selected = self._select_tools_via_llm(query, driver_code)

        if not selected:
            logger.info("DataAgent: using keyword-based tool selection fallback")
            selected = self._select_tools_by_keywords(query, driver_code)

        # 2. Execute each tool
        results = {}
        tools_used = []

        for tool_call in selected[:3]:  # max 3 tools
            name = tool_call.get("tool", "")
            args = tool_call.get("args", {})

            if name not in TOOL_REGISTRY:
                logger.warning("Unknown tool: %s", name)
                continue

            func = TOOL_REGISTRY[name]["func"]
            # Inject session_id
            args["session_id"] = session_id
            
            # Map parameters correctly if missing but context exists
            if "driver_code" in args and driver_code and not args["driver_code"]:
                args["driver_code"] = driver_code
            elif (
                "driver_code" in TOOL_REGISTRY[name].get("required_args", [])
                and driver_code
                and "driver_code" not in args
            ):
                args["driver_code"] = driver_code

            try:
                result = func(self.db, **args)
                results[name] = result
                tools_used.append(name)
                logger.info("DataAgent executed tool: %s", name)
            except Exception as exc:
                logger.error("DataAgent tool %s failed: %s", name, exc)
                results[name] = {"error": str(exc)}
                tools_used.append(name)

        return {
            "tools_used": tools_used,
            "results": results,
        }
