"""
FastAPI application entrypoint.
Start the server:  uvicorn backend.app.main:app --reload
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.core.config import API_PREFIX, CORS_ORIGINS
from backend.app.core.logging import setup_logging
from backend.app.api.v1 import sessions, drivers, laps, telemetry, predictions
from backend.app.api.v1 import auth as auth_router

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
# In production CORS_ORIGINS is set via env var to the Vercel frontend URL.
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS if CORS_ORIGINS != ["*"] else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(sessions.router,       prefix=API_PREFIX)
app.include_router(drivers.router,        prefix=API_PREFIX)
app.include_router(laps.router,           prefix=API_PREFIX)
app.include_router(telemetry.router,      prefix=API_PREFIX)
app.include_router(predictions.router,    prefix=API_PREFIX)
app.include_router(auth_router.router,    prefix=API_PREFIX)


# ── DB: auto-create users table on startup ────────────────────────────────────
@app.on_event("startup")
def on_startup():
    from backend.app.database.db import engine
    from backend.app.database.models import Base
    Base.metadata.create_all(bind=engine, checkfirst=True)


# ── Health check ──────────────────────────────────────────────────────────────
@app.get("/health", tags=["Health"])
def health():
    return {"status": "ok", "version": "1.0.0"}
