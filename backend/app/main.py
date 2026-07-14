"""
FastAPI application entrypoint.
Start the server:  uvicorn backend.app.main:app --reload
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.core.config import API_PREFIX
from backend.app.core.logging import setup_logging
from backend.app.api.v1 import sessions, drivers, laps, telemetry, predictions

# ── Logging ───────────────────────────────────────────────────────────────────
setup_logging("backend.log")

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="AI F1 Telemetry Platform",
    description=(
        "ML-driven race strategy simulator and live telemetry dashboard "
        "built on real F1 data via FastF1."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS ──────────────────────────────────────────────────────────────────────
# In production, replace "*" with the actual frontend domain.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(sessions.router, prefix=API_PREFIX)
app.include_router(drivers.router, prefix=API_PREFIX)
app.include_router(laps.router, prefix=API_PREFIX)
app.include_router(telemetry.router, prefix=API_PREFIX)
app.include_router(predictions.router, prefix=API_PREFIX)


# ── Health check ──────────────────────────────────────────────────────────────
@app.get("/health", tags=["Health"])
def health():
    return {"status": "ok", "version": "1.0.0"}
