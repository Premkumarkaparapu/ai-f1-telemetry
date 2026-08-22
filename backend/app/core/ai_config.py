"""
AI-specific configuration — provider selection, API keys, model names.

All settings are read from environment variables with sensible defaults.
Default provider is 'mock' so the app works without any API keys.
"""

import os
from pathlib import Path

from backend.app.core.config import ROOT_DIR


# ── Provider ──────────────────────────────────────────────────────────
AI_PROVIDER: str = os.getenv("AI_PROVIDER", "mock")

# ── Gemini ────────────────────────────────────────────────────────────
GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
AI_MODEL_NAME: str = os.getenv(
    "AI_MODEL_NAME", "gemini-1.5-flash"
)
AI_TEMPERATURE: float = float(os.getenv("AI_TEMPERATURE", "0.3"))
AI_MAX_TOKENS: int = int(os.getenv("AI_MAX_TOKENS", "2048"))

# ── Security ──────────────────────────────────────────────────────────
API_KEY: str = os.getenv("API_KEY", "")

# ── Knowledge / RAG ──────────────────────────────────────────────────
KNOWLEDGE_DIR: Path = Path(
    os.getenv("KNOWLEDGE_DIR", str(ROOT_DIR / "knowledge"))
)
