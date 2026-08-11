"""
FastAPI application entrypoint.
Start the server:  uvicorn backend.app.main:app --reload
"""

from pathlib import Path
from dotenv import load_dotenv

# Load .env before any config imports
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from backend.app.core.config import API_PREFIX, CORS_ORIGINS
from backend.app.core.logging import setup_logging
from backend.app.api.v1 import sessions, drivers, laps, telemetry, predictions
from backend.app.api.v1 import auth as auth_router
from backend.app.api.v1 import ai as ai_router

# ── Logging ───────────────────────────────────────────────────────────────────
setup_logging("backend.log")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Create database tables, connect to Redis, and create shared HTTP client
    import httpx
    from backend.app.database.db import engine
    from backend.app.database.models import Base
    from sqlalchemy.exc import ProgrammingError
    from backend.app.core.redis import redis_manager

    for table in Base.metadata.sorted_tables:
        try:
            table.create(bind=engine, checkfirst=True)
        except ProgrammingError as e:
            if "already exists" in str(e):
                pass
            else:
                raise

    await redis_manager.connect()
    app.state.http_client = httpx.AsyncClient(timeout=10.0)
    yield
    # Shutdown: Dispose engine connections, close Redis, and close HTTP client
    from backend.app.database.db import engine
    engine.dispose()
    await redis_manager.close()
    await app.state.http_client.aclose()

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
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS if CORS_ORIGINS != ["*"] else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Request ID middleware ─────────────────────────────────────────────────────
import uuid
import re
from fastapi import Request
from backend.app.core.request_context import set_request_id

UUID_REGEX = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")

@app.middleware("http")
async def add_request_id_header(request: Request, call_next):
    raw_id = request.headers.get("X-Request-ID")
    if raw_id and UUID_REGEX.match(raw_id.lower()):
        request_id = raw_id.lower()
    else:
        request_id = str(uuid.uuid4())
    
    set_request_id(request_id)
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(sessions.router,       prefix=API_PREFIX)
app.include_router(drivers.router,        prefix=API_PREFIX)
app.include_router(laps.router,           prefix=API_PREFIX)
app.include_router(telemetry.router,      prefix=API_PREFIX)
app.include_router(predictions.router,    prefix=API_PREFIX)
app.include_router(auth_router.router,    prefix=API_PREFIX)
app.include_router(ai_router.router,      prefix=API_PREFIX)



# ── Health check ──────────────────────────────────────────────────────────────
from fastapi.responses import JSONResponse
from backend.app.database.db import get_db
from sqlalchemy.orm import Session
from fastapi import Depends

@app.get("/health", tags=["Health"])
def health():
    return {"status": "ok", "version": "1.0.0"}


@app.get("/health/live", tags=["Health"])
def health_live():
    """Cheap liveness probe to verify the application process is running."""
    return {"status": "alive"}


@app.get("/health/ready", tags=["Health"])
def health_ready(db: Session = Depends(get_db)):
    """Readiness probe to verify all backing services are connected and ready."""
    checks = {}

    # 1. Database check
    try:
        from sqlalchemy import text
        db.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:
        checks["database"] = f"failed: {exc}"

    # 2. Storage write/access check
    try:
        from backend.app.core.config import RAW_DIR
        RAW_DIR.mkdir(parents=True, exist_ok=True)
        test_file = RAW_DIR / ".ready_check"
        test_file.touch()
        test_file.unlink()
        checks["storage"] = "ok"
    except Exception as exc:
        checks["storage"] = f"failed: {exc}"

    # 3. AI provider check (avoids expensive outbound Gemini calls)
    try:
        from backend.app.core.ai_config import AI_PROVIDER
        checks["ai_provider"] = "configured" if AI_PROVIDER else "missing"
    except Exception:
        checks["ai_provider"] = "failed"

    # Overall status
    all_ok = all(v == "ok" or v == "configured" for v in checks.values())
    status_code = 200 if all_ok else 503

    return JSONResponse(
        content={"status": "ready" if all_ok else "unready", "checks": checks},
        status_code=status_code
    )
