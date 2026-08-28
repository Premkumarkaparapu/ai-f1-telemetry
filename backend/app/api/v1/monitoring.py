import json
import sys
import time
from typing import Dict, Any

from fastapi import APIRouter, Depends
from prometheus_client import REGISTRY
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.app.api.v1.security import require_scope, AuthenticatedUser
from backend.app.core.config import APP_START_TIME, MODEL_PATH
from backend.app.core.circuit_breaker import gemini_circuit
from backend.app.core.redis import redis_manager
from backend.app.database.db import get_db

router = APIRouter(prefix="/monitoring", tags=["Monitoring"])


@router.get("/status", response_model=Dict[str, Any])
async def get_status(
    db: Session = Depends(get_db),
    user: AuthenticatedUser = Depends(require_scope("system:monitor"))
):
    """Returns overall platform component status pings and uptime."""
    # 1. Database connection check
    db_status = "connected"
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        db_status = "unavailable"

    # 2. Redis connection check
    redis_status = "connected"
    try:
        if redis_manager.client is None:
            redis_status = "unavailable"
        else:
            await redis_manager.client.ping()
    except Exception:
        redis_status = "unavailable"

    # 3. Gemini / AI availability check
    cb_state = await gemini_circuit.get_state()
    gemini_status = "available"
    if cb_state in ("OPEN", "HALF-OPEN"):
        gemini_status = "degraded"

    uptime_seconds = int(time.time() - APP_START_TIME)

    return {
        "api": "healthy",
        "database": db_status,
        "redis": redis_status,
        "gemini": gemini_status,
        "uptime_seconds": uptime_seconds,
    }


@router.get("/metrics", response_model=Dict[str, Any])
async def get_metrics(
    user: AuthenticatedUser = Depends(require_scope("system:monitor"))
):
    """Summarizes Prometheus metrics without HTTP calls."""
    req_count = 0
    err_count = 0
    duration_sum = 0.0
    duration_count = 0
    gemini_reqs = 0
    gemini_errs = 0
    rate_rejections = 0
    gemini_latency_sum = 0.0
    gemini_latency_count = 0

    # Aggregate in-process Prometheus metrics registry
    for metric in REGISTRY.collect():
        if metric.name == "http_requests_total":
            for s in metric.samples:
                req_count += int(s.value)
                status_code = s.labels.get("status_code", "")
                if status_code.startswith("5"):
                    err_count += int(s.value)
        elif metric.name == "http_request_duration_seconds_sum":
            for s in metric.samples:
                duration_sum += s.value
        elif metric.name == "http_request_duration_seconds_count":
            for s in metric.samples:
                duration_count += int(s.value)
        elif metric.name == "gemini_requests_total":
            for s in metric.samples:
                gemini_reqs += int(s.value)
        elif metric.name == "gemini_errors_total":
            for s in metric.samples:
                gemini_errs += int(s.value)
        elif metric.name == "rate_limit_rejections_total":
            for s in metric.samples:
                rate_rejections += int(s.value)
        elif metric.name == "gemini_request_duration_seconds_sum":
            for s in metric.samples:
                gemini_latency_sum += s.value
        elif metric.name == "gemini_request_duration_seconds_count":
            for s in metric.samples:
                gemini_latency_count += int(s.value)

    # Calculate pings and performance deltas
    avg_latency_ms = (
        (duration_sum / duration_count * 1000.0)
        if duration_count > 0 else 0.0
    )
    avg_gemini_latency_ms = (
        (gemini_latency_sum / gemini_latency_count * 1000.0)
        if gemini_latency_count > 0 else 0.0
    )

    redis_latency_ms = 0.0
    if redis_manager.client is not None:
        try:
            t0 = time.perf_counter()
            await redis_manager.client.ping()
            redis_latency_ms = (time.perf_counter() - t0) * 1000.0
        except Exception:
            pass

    return {
        "request_count": req_count,
        "request_latency": avg_latency_ms,
        "error_count": err_count,
        "gemini_requests": gemini_reqs,
        "gemini_errors": gemini_errs,
        "gemini_latency": avg_gemini_latency_ms,
        "redis_latency": redis_latency_ms,
        "rate_limit_rejections": rate_rejections,
    }


@router.get("/health", response_model=Dict[str, Any])
async def get_health(
    db: Session = Depends(get_db),
    user: AuthenticatedUser = Depends(require_scope("system:monitor"))
):
    """Evaluates backing service health state machine logic:

    API + DB + Redis + Gemini healthy -> healthy
    DB unavailable                   -> unavailable
    Redis unavailable                -> degraded
    Gemini circuit OPEN              -> degraded
    """
    db_healthy = True
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        db_healthy = False

    redis_healthy = True
    try:
        if redis_manager.client is None:
            redis_healthy = False
        else:
            await redis_manager.client.ping()
    except Exception:
        redis_healthy = False

    cb_state = await gemini_circuit.get_state()
    gemini_healthy = (cb_state == "CLOSED")

    # Define overall health state hierarchy
    if not db_healthy:
        overall_status = "unavailable"
    elif (
        not redis_healthy
        or not gemini_healthy
        or cb_state in ("OPEN", "HALF-OPEN")
    ):
        overall_status = "degraded"
    else:
        overall_status = "healthy"

    return {
        "status": overall_status,
        "components": {
            "database": "healthy" if db_healthy else "unavailable",
            "redis": "healthy" if redis_healthy else "unavailable",
            "gemini": "healthy" if gemini_healthy else "degraded",
            "application": "healthy",
        }
    }


@router.get("/diagnostics", response_model=Dict[str, Any])
async def get_diagnostics(
    db: Session = Depends(get_db),
    user: AuthenticatedUser = Depends(require_scope("system:monitor"))
):
    """Executes safe read-only diagnostics and file validations."""
    db_ok = True
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        db_ok = False

    redis_ok = True
    try:
        if redis_manager.client is not None:
            await redis_manager.client.ping()
        else:
            redis_ok = False
    except Exception:
        redis_ok = False

    # Check ML models (Lightweight checks avoiding memory loads)
    models_status = {}

    # 1. XGBoost Model
    xgb_path = MODEL_PATH / "laptime_predictor.pkl"
    xgb_exists = xgb_path.exists()
    xgb_status = (
        "Loaded" if ("ml.inference" in sys.modules and xgb_exists)
        else ("Available" if xgb_exists else "Missing")
    )
    models_status["xgboost"] = {
        "status": xgb_status,
        "file_exists": xgb_exists,
        "file_size_bytes": xgb_path.stat().st_size if xgb_exists else 0,
    }

    # 2. Ridge Model
    ridge_compounds = ["SOFT", "MEDIUM", "HARD"]
    ridge_status = []
    all_ridge_exists = True
    total_ridge_size = 0
    for c in ridge_compounds:
        r_path = MODEL_PATH / f"tire_degradation_ridge_{c}.pkl"
        exists = r_path.exists()
        if not exists:
            all_ridge_exists = False
        else:
            total_ridge_size += r_path.stat().st_size
        ridge_status.append({"compound": c, "exists": exists})

    ridge_lbl = (
        "Loaded" if ("ml.inference" in sys.modules and all_ridge_exists)
        else ("Available" if all_ridge_exists else "Degraded")
    )
    models_status["ridge"] = {
        "status": ridge_lbl,
        "all_compounds_exist": all_ridge_exists,
        "compounds": ridge_status,
        "total_file_size_bytes": total_ridge_size,
    }

    prep_path = MODEL_PATH / "preprocessing_pipeline.pkl"
    prep_exists = prep_path.exists()
    prep_status = (
        "Loaded" if ("ml.inference" in sys.modules and prep_exists)
        else ("Available" if prep_exists else "Missing")
    )
    models_status["preprocessing"] = {
        "status": prep_status,
        "file_exists": prep_exists,
        "file_size_bytes": prep_path.stat().st_size if prep_exists else 0,
    }

    # 4. Model Version
    model_version = "v2.x"
    eval_path = MODEL_PATH / "evaluation_report.json"
    if eval_path.exists():
        try:
            with open(eval_path, "r", encoding="utf-8") as f:
                eval_data = json.load(f)
                model_version = eval_data.get("model_version", "v2.7")
        except Exception:
            pass

    cb_state = await gemini_circuit.get_state()

    ai_active = (
        sys.modules.get("backend.app.core.ai_config") or
        sys.modules.get("backend.app.services.ai_service")
    )
    return {
        "database_connected": db_ok,
        "redis_connected": redis_ok,
        "gemini_api_configured": bool(ai_active),
        "circuit_breaker_state": cb_state,
        "ml_models": models_status,
        "model_version": model_version,
    }
