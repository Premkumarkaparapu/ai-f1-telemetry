"""FastAPI application entrypoint.

Start the server:  uvicorn backend.app.main:app --reload
"""

from contextlib import asynccontextmanager
from pathlib import Path
import re
import uuid

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Request, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from backend.app.core.audit_middleware import DurableAuditMiddleware
import httpx
from sqlalchemy import text
from sqlalchemy.orm import Session

# Load .env before any config imports
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

from fastapi import Response  # noqa: E402
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST  # noqa: E402
import time  # noqa: E402

from backend.app.api.v1 import ai as ai_router  # noqa: E402
from backend.app.api.v1 import auth as auth_router  # noqa: E402
from backend.app.api.v1 import (  # noqa: E402
    drivers, laps, predictions, sessions, telemetry, monitoring, admin
)
from backend.app.core.ai_config import AI_PROVIDER  # noqa: E402
from backend.app.core.config import API_PREFIX, CORS_ORIGINS, RAW_DIR  # noqa: E402
from backend.app.core.logging import setup_logging  # noqa: E402
from backend.app.core.metrics import (  # noqa: E402
    HTTP_REQUESTS_TOTAL,
    HTTP_REQUEST_DURATION_SECONDS,
    REDIS_CONNECTION_STATUS,
    DB_POOL_ACTIVE,
)
from backend.app.core.redis import redis_manager  # noqa: E402
from backend.app.core.request_context import set_request_id  # noqa: E402
from backend.app.database.db import get_db, engine  # noqa: E402

# ── Logging ───────────────────────────────────────────────────────────────────
setup_logging("backend.log")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Create database tables, connect to Redis, and create shared HTTP client
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
    title="F1 Telemetry & AI Strategy Platform",
    description=(
        "Enterprise-hardened real-time telemetry analysis and strategy tool."
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

app.add_middleware(DurableAuditMiddleware)


# ── Request ID middleware ─────────────────────────────────────────────────────

UUID_REGEX = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)


@app.middleware("http")
async def prometheus_metrics_middleware(request: Request, call_next):
    # Exclude /metrics itself to avoid scraping latency cluttering
    if request.url.path == "/metrics":
        return await call_next(request)

    start_time = time.perf_counter()
    response = await call_next(request)
    duration = time.perf_counter() - start_time

    # Resolve route path template (low cardinality)
    route = request.scope.get("route")
    if route:
        endpoint = route.path
    else:
        path = request.url.path
        if path.startswith("/api/v1/sessions/"):
            endpoint = "/api/v1/sessions/{session_id}"
        elif path.startswith("/api/v1/drivers/"):
            endpoint = "/api/v1/drivers/{driver_id_or_code}"
        elif path.startswith("/api/v1/laps/"):
            endpoint = "/api/v1/laps/{lap_id}"
        elif path.startswith("/api/v1/telemetry/"):
            endpoint = "/api/v1/telemetry/{telemetry_id}"
        else:
            endpoint = path

    method = request.method
    status_code = str(response.status_code)

    HTTP_REQUESTS_TOTAL.labels(
        method=method,
        endpoint=endpoint,
        status_code=status_code,
    ).inc()
    HTTP_REQUEST_DURATION_SECONDS.labels(
        method=method,
        endpoint=endpoint,
    ).observe(duration)

    # Update status gauges
    if redis_manager:
        REDIS_CONNECTION_STATUS.set(1 if redis_manager.client is not None else 0)
    if engine and hasattr(engine, "pool") and hasattr(engine.pool, "checkedout"):
        DB_POOL_ACTIVE.set(engine.pool.checkedout())

    return response


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
app.include_router(monitoring.router,     prefix=API_PREFIX)
app.include_router(admin.router,          prefix=API_PREFIX)


import ipaddress  # noqa: E402


def restrict_to_internal_network(request: Request):
    """Bypasses auth but restricts metrics endpoint access to internal subnets / localhost."""
    client_ip = request.headers.get("x-forwarded-for") or request.client.host
    try:
        ip = ipaddress.ip_address(client_ip)
        if ip.is_loopback or ip.is_private or ip.is_link_local:
            return
    except ValueError:
        pass
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Access denied: metrics are restricted to internal network"
    )


@app.get("/metrics", tags=["Metrics"], dependencies=[Depends(restrict_to_internal_network)])
def get_metrics():
    """Unauthenticated /metrics endpoint restricted to the monitoring network."""
    try:
        from backend.app.database.db import engine
        if hasattr(engine, "pool"):
            from backend.app.core.metrics import DB_POOL_ACTIVE
            # Set active checked-out connection count if using connection pooling
            if hasattr(engine.pool, "checkedout"):
                DB_POOL_ACTIVE.set(engine.pool.checkedout())
    except Exception:
        pass
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


# ── Health check ──────────────────────────────────────────────────────────────

@app.get("/health", tags=["Health"])
def health():
    from backend.app.core.metrics import APP_HEALTH_STATUS
    APP_HEALTH_STATUS.set(1.0)
    return {"status": "ok", "version": "1.0.0"}


@app.get("/health/live", tags=["Health"])
def health_live():
    """Cheap liveness probe to verify the application process is running."""
    from backend.app.core.metrics import APP_HEALTH_STATUS
    APP_HEALTH_STATUS.set(1.0)
    return {"status": "alive"}


@app.get("/health/ready", tags=["Health"])
async def health_ready(db: Session = Depends(get_db)):
    """Readiness probe to verify backing services are connected and ready."""
    from backend.app.core.metrics import APP_READINESS_STATUS, REDIS_CONNECTION_STATUS
    checks = {}

    # 1. Database check
    try:
        db.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:
        checks["database"] = f"failed: {exc}"

    # 2. Redis check
    try:
        from backend.app.core.redis import redis_manager
        if redis_manager.client is None:
            checks["redis"] = "degraded: client is offline"
        else:
            await redis_manager.client.ping()
            checks["redis"] = "ok"
    except Exception as exc:
        checks["redis"] = f"degraded: {exc}"

    # 3. Storage write/access check
    try:
        RAW_DIR.mkdir(parents=True, exist_ok=True)
        test_file = RAW_DIR / ".ready_check"
        test_file.touch()
        test_file.unlink()
        checks["storage"] = "ok"
    except Exception as exc:
        checks["storage"] = f"failed: {exc}"

    # 4. AI provider check
    try:
        checks["ai_provider"] = "configured" if AI_PROVIDER else "missing"
    except Exception:
        checks["ai_provider"] = "failed"

    # Degraded logic calculation
    db_ok = checks.get("database") == "ok"
    storage_ok = checks.get("storage") == "ok"
    redis_ok = checks.get("redis", "ok") == "ok"

    if not db_ok or not storage_ok:
        status_str = "unhealthy"
        status_code = 503
        APP_READINESS_STATUS.set(0.0)
    elif not redis_ok:
        status_str = "degraded"
        status_code = 200
        APP_READINESS_STATUS.set(1.0)
    else:
        status_str = "ready"
        status_code = 200
        APP_READINESS_STATUS.set(1.0)

    # Set Redis connection status metric gauge
    REDIS_CONNECTION_STATUS.set(1.0 if redis_ok else 0.0)

    return JSONResponse(
        content={"status": status_str, "checks": checks},
        status_code=status_code
    )
