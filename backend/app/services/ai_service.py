"""AI service abstraction layer — provider-agnostic interface.

Supports 'mock' (no API key) and 'gemini' providers.
The application never imports a specific provider directly;
it always goes through get_ai_service().
"""

import json
import time
from abc import ABC, abstractmethod
from typing import Generator

from backend.app.core.ai_config import (
    AI_PROVIDER, GEMINI_API_KEY, AI_MODEL_NAME,
    AI_TEMPERATURE, AI_MAX_TOKENS,
)
from backend.app.core.logging import get_logger

logger = get_logger(__name__)


# ── Abstract interface ────────────────────────────────────────────────


class AIService(ABC):
    """Provider-agnostic AI completion interface."""

    @abstractmethod
    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float | None = None,
    ) -> str:
        """Return a single text completion."""

    @abstractmethod
    def complete_json(
        self,
        system_prompt: str,
        user_prompt: str,
        schema: dict | None = None,
    ) -> dict:
        """Return a parsed JSON completion."""

    @abstractmethod
    def stream(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> Generator[str, None, None]:
        """Yield text chunks for streaming responses."""


# ── Mock provider ─────────────────────────────────────────────────────


class MockProvider(AIService):
    """Returns deterministic F1-themed responses.

    Works without any API key — ideal for dev, tests,
    and demos where the LLM is not the focus.
    """

    def complete(self, system_prompt, user_prompt, temperature=None):
        """Return a realistic mock analysis."""
        return (
            "Based on the telemetry data, the driver maintained "
            "competitive pace through the first stint on medium "
            "tires, averaging 1:32.4. Degradation increased "
            "significantly after lap 25, with sector 2 times "
            "dropping by approximately 0.3s per lap. The "
            "optimal pit window was laps 28-32, and the team "
            "executed the stop on lap 30, which was within the "
            "ideal range."
        )

    def complete_json(self, system_prompt, user_prompt, schema=None):
        """Return a structured mock tool-call response."""
        q = user_prompt.lower()

        # Simulate tool selection based on keywords
        tools = []
        if any(w in q for w in ("pace", "fast", "speed", "time")):
            tools.append({
                "tool": "get_driver_pace",
                "args": {"driver_code": "VER"},
            })
        if any(w in q for w in ("tire", "tyre", "degrad")):
            tools.append({
                "tool": "get_tire_degradation",
                "args": {"driver_code": "VER"},
            })
        if any(w in q for w in ("sector", "s1", "s2", "s3")):
            tools.append({
                "tool": "get_sector_performance",
                "args": {"driver_code": "VER"},
            })
        if any(w in q for w in ("compare", "vs", "versus")):
            tools.append({
                "tool": "compare_drivers",
                "args": {
                    "driver1_code": "VER",
                    "driver2_code": "HAM",
                },
            })
        if any(w in q for w in ("pit", "stop", "window")):
            tools.append({
                "tool": "get_pit_window",
                "args": {"driver_code": "VER", "current_lap": 20},
            })
        if any(w in q for w in ("strat", "plan")):
            tools.append({
                "tool": "get_strategy_comparison",
                "args": {"driver_code": "VER"},
            })
        if any(w in q for w in ("race", "summary", "overview")):
            tools.append({
                "tool": "get_race_summary",
                "args": {},
            })

        if not tools:
            tools.append({
                "tool": "get_race_summary",
                "args": {},
            })

        return {"tools": tools}

    def stream(self, system_prompt, user_prompt):
        """Yield mock streaming tokens."""
        text = self.complete(system_prompt, user_prompt)
        words = text.split(" ")
        for word in words:
            yield word + " "


# ── Gemini provider ───────────────────────────────────────────────────


class GeminiProvider(AIService):
    """Google Gemini API provider using the google-genai SDK."""

    _MAX_RETRIES = 3
    _RETRY_DELAYS = [5, 10, 20]  # seconds

    def __init__(self):
        """Configure the Gemini client."""
        try:
            from google import genai
            from google.genai import types
            self._client = genai.Client(
                api_key=GEMINI_API_KEY,
                http_options=types.HttpOptions(timeout=10_000)
            )
            self._model = AI_MODEL_NAME
            self._types = types
            logger.info(
                "GeminiProvider initialised (model=%s)",
                AI_MODEL_NAME,
            )
        except Exception as exc:
            logger.error("Failed to init Gemini: %s", exc)
            raise

    def _retry_call(self, fn):
        """Call fn() with retries on rate-limit (429) errors."""
        for attempt in range(self._MAX_RETRIES + 1):
            try:
                return fn()
            except Exception as exc:
                err_str = str(exc)
                if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                    if attempt < self._MAX_RETRIES:
                        delay = self._RETRY_DELAYS[attempt]
                        logger.warning(
                            "Gemini rate limited, retrying in %ds (attempt %d/%d)",
                            delay, attempt + 1, self._MAX_RETRIES,
                        )
                        time.sleep(delay)
                        continue
                raise

    def _execute_under_breaker(self, fn, api_method: str = "complete"):
        """Execute a function under the Gemini circuit breaker state controls."""
        from backend.app.core.circuit_breaker import gemini_circuit, CircuitOpenException
        from fastapi import HTTPException
        from backend.app.core.metrics import (
            GEMINI_REQUESTS_TOTAL,
            GEMINI_REQUEST_DURATION_SECONDS,
            GEMINI_ERRORS_TOTAL,
        )

        state = gemini_circuit.get_state_sync()
        if state == "OPEN":
            GEMINI_ERRORS_TOTAL.labels(
                model_name=self._model,
                error_type="circuit_open",
            ).inc()
            raise CircuitOpenException("Gemini API circuit is OPEN. Fast-failing query.")
        elif state == "HALF-OPEN":
            if not gemini_circuit.acquire_half_open_lock_sync():
                GEMINI_ERRORS_TOTAL.labels(
                    model_name=self._model,
                    error_type="circuit_half_open_lock_busy",
                ).inc()
                raise CircuitOpenException(
                    "Gemini API circuit is HALF-OPEN. Lock busy; fast-failing query."
                )

        start_time = time.perf_counter()
        try:
            result = fn()
            duration = time.perf_counter() - start_time
            GEMINI_REQUESTS_TOTAL.labels(
                model_name=self._model,
                api_method=api_method,
                status="success",
            ).inc()
            GEMINI_REQUEST_DURATION_SECONDS.labels(
                model_name=self._model,
                api_method=api_method,
            ).observe(duration)
            gemini_circuit.record_success_sync()
            return result
        except Exception as exc:
            duration = time.perf_counter() - start_time
            err_type = type(exc).__name__
            GEMINI_REQUESTS_TOTAL.labels(
                model_name=self._model,
                api_method=api_method,
                status="error",
            ).inc()
            GEMINI_ERRORS_TOTAL.labels(
                model_name=self._model,
                error_type=err_type,
            ).inc()
            # Do not count deliberate user-end 429 limits as backend circuit failures
            if isinstance(exc, HTTPException) and exc.status_code == 429:
                raise
            gemini_circuit.record_failure_sync()
            raise

    def complete(self, system_prompt, user_prompt, temperature=None):
        """Single-shot text generation with retry, concurrency semaphore, and circuit breaker."""
        from backend.app.core.request_context import get_request_id
        from backend.app.core.semaphore import gemini_semaphore
        from fastapi import HTTPException
        import uuid

        req_id = get_request_id() or str(uuid.uuid4())
        acquired = gemini_semaphore.acquire_sync(req_id)
        if not acquired:
            raise HTTPException(
                status_code=429,
                detail="Too many concurrent requests to AI engine. Please try again later."
            )

        try:
            temp = temperature or AI_TEMPERATURE

            def _call():
                resp = self._client.models.generate_content(
                    model=self._model,
                    contents=user_prompt,
                    config=self._types.GenerateContentConfig(
                        system_instruction=system_prompt,
                        temperature=temp,
                        max_output_tokens=AI_MAX_TOKENS,
                    ),
                )
                return resp.text
            return self._execute_under_breaker(
                lambda: self._retry_call(_call),
                api_method="complete",
            )
        finally:
            gemini_semaphore.release_sync(req_id)

    def complete_json(self, system_prompt, user_prompt, schema=None):
        """JSON-mode generation with retry, automatic parsing, concurrency, and circuit breaker."""
        from backend.app.core.request_context import get_request_id
        from backend.app.core.semaphore import gemini_semaphore
        from fastapi import HTTPException
        import uuid

        req_id = get_request_id() or str(uuid.uuid4())
        acquired = gemini_semaphore.acquire_sync(req_id)
        if not acquired:
            raise HTTPException(
                status_code=429,
                detail="Too many concurrent requests to AI engine. Please try again later."
            )

        try:

            def _call():
                config_args = {
                    "system_instruction": system_prompt,
                    "temperature": AI_TEMPERATURE,
                    "max_output_tokens": AI_MAX_TOKENS,
                    "response_mime_type": "application/json",
                }
                if schema is not None:
                    config_args["response_schema"] = schema

                resp = self._client.models.generate_content(
                    model=self._model,
                    contents=user_prompt,
                    config=self._types.GenerateContentConfig(**config_args),
                )
                try:
                    return json.loads(resp.text)
                except (json.JSONDecodeError, ValueError):
                    logger.warning(
                        "Gemini JSON parse failed, raw: %s",
                        resp.text[:200],
                    )
                    return {"raw": resp.text}
            return self._execute_under_breaker(
                lambda: self._retry_call(_call),
                api_method="complete_json",
            )
        finally:
            gemini_semaphore.release_sync(req_id)

    def stream(self, system_prompt, user_prompt):
        """Streaming text generation with retry, concurrency, and circuit breaker."""
        from backend.app.core.request_context import get_request_id
        from backend.app.core.semaphore import gemini_semaphore
        from fastapi import HTTPException
        import uuid

        req_id = get_request_id() or str(uuid.uuid4())
        acquired = gemini_semaphore.acquire_sync(req_id)
        if not acquired:
            raise HTTPException(
                status_code=429,
                detail="Too many concurrent requests to AI engine. Please try again later."
            )

        try:

            def _call():
                chunks = []
                for chunk in self._client.models.generate_content_stream(
                    model=self._model,
                    contents=user_prompt,
                    config=self._types.GenerateContentConfig(
                        system_instruction=system_prompt,
                        temperature=AI_TEMPERATURE,
                        max_output_tokens=AI_MAX_TOKENS,
                    ),
                ):
                    if chunk.text:
                        chunks.append(chunk.text)
                return chunks
            result = self._execute_under_breaker(
                lambda: self._retry_call(_call),
                api_method="stream",
            )
            for text in result:
                yield text
        finally:
            gemini_semaphore.release_sync(req_id)


# ── Factory ───────────────────────────────────────────────────────────


def get_ai_service() -> AIService:
    """Return the configured AI provider instance.

    Reads AI_PROVIDER from environment / ai_config.
    Falls back to MockProvider if anything goes wrong.
    """
    provider = AI_PROVIDER.lower().strip()
    if provider == "gemini":
        if not GEMINI_API_KEY:
            logger.warning(
                "GEMINI_API_KEY not set — falling back to mock"
            )
            return MockProvider()
        try:
            return GeminiProvider()
        except Exception:
            logger.warning("Gemini init failed — using mock")
            return MockProvider()

    logger.info("Using MockProvider (AI_PROVIDER=%s)", AI_PROVIDER)
    return MockProvider()
