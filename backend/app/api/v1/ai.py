"""AI Race Engineer API endpoints.

Routes:
    POST /ai/ask               — Synchronous Q&A
    POST /ai/stream             — SSE streaming Q&A
    GET  /ai/suggested-questions — Context-aware suggestions
    GET  /ai/health             — AI subsystem health check
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.app.database.db import get_db
from backend.app.services.ai_race_engineer import AIRaceEngineer
from backend.app.services.ai_service import get_ai_service
from backend.app.core.ai_config import AI_PROVIDER
from backend.app.core.rate_limit import rate_limit
from backend.app.api.v1.security import require_scope

router = APIRouter(prefix="/ai", tags=["AI Race Engineer"])


# ── Request / Response schemas ────────────────────────────────────


class AskRequest(BaseModel):
    """Request body for /ai/ask and /ai/stream."""
    question: str = Field(
        ..., min_length=1, max_length=500,
        description="The F1 question to ask",
    )
    session_id: int = Field(
        ..., description="DB session_id for context",
    )
    driver_code: Optional[str] = Field(
        None, max_length=3,
        description="3-letter driver code (e.g. VER)",
    )


class AskResponse(BaseModel):
    """Response from /ai/ask."""
    answer: str
    evidence: dict
    tools_used: list[str]
    intent: str
    sources: list[str]
    latency_ms: int


# ── Endpoints ─────────────────────────────────────────────────────


@router.post("/ask", response_model=AskResponse, dependencies=[Depends(rate_limit), Depends(require_scope("ai:ask"))])
def ask_question(
    request: AskRequest,
    db: Session = Depends(get_db),
):
    """Ask the AI Race Engineer a question.

    Returns a structured response with answer, evidence,
    tools used, intent classification, and sources.
    """
    engineer = AIRaceEngineer(db)
    result = engineer.ask(
        question=request.question,
        session_id=request.session_id,
        driver_code=request.driver_code,
    )
    return result


@router.post("/stream", dependencies=[Depends(rate_limit), Depends(require_scope("ai:ask"))])
def stream_question(
    request: AskRequest,
    db: Session = Depends(get_db),
):
    """Stream the AI Race Engineer's answer via SSE.

    Events:
        {type: "metadata", intent, tools_used}
        {type: "token", content: "..."}
        {type: "done", evidence, sources}
    """
    engineer = AIRaceEngineer(db)

    def generate():
        yield from engineer.stream_ask(
            question=request.question,
            session_id=request.session_id,
            driver_code=request.driver_code,
        )

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/suggested-questions")
def get_suggested_questions(
    session_id: Optional[int] = Query(None),
    driver_code: Optional[str] = Query(None),
):
    """Return context-aware question suggestions.

    Suggestions change based on whether a session or
    driver is selected.
    """
    base = [
        "Give me a race summary",
        "Which driver had the fastest pace?",
        "What tire compounds were most effective?",
    ]

    if driver_code:
        base = [
            f"How was {driver_code}'s pace?",
            f"Analyze {driver_code}'s tire degradation",
            f"What was {driver_code}'s optimal pit window?",
            f"Show {driver_code}'s sector performance",
            f"Compare {driver_code}'s strategy alternatives",
        ]
    elif session_id:
        base = [
            "Give me a race summary",
            "Who had the best pace on mediums?",
            "Compare VER vs HAM",
            "What was the optimal pit strategy?",
            "Which sector separated the top drivers?",
        ]

    return {"questions": base}


@router.get("/health")
def ai_health():
    """Health check for the AI subsystem."""
    ai = get_ai_service()
    return {
        "status": "healthy",
        "provider": AI_PROVIDER,
        "provider_class": type(ai).__name__,
    }
