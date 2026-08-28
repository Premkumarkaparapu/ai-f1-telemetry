from typing import Dict, Any
from fastapi import APIRouter, Depends

from backend.app.api.v1.security import require_scope, AuthenticatedUser

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.get("/logs", response_model=Dict[str, Any])
async def get_logs(
    user: AuthenticatedUser = Depends(require_scope("system:admin"))
):
    """Returns safe mock log entries for L3 scope validation tests."""
    return {
        "status": "authorized",
        "logs": "MOCK LOG ENTRY: Application is executing normally. All components healthy."
    }


@router.post("/db/sync-sequence", response_model=Dict[str, Any])
async def sync_sequence(
    user: AuthenticatedUser = Depends(require_scope("system:admin"))
):
    """Returns safe mock response for primary key serial sequence alignment."""
    return {
        "status": "authorized",
        "message": (
            "MOCK SEQUENCE SYNC: Database sequences checked and "
            "aligned with max primary keys."
        )
    }


@router.post("/backup/trigger", response_model=Dict[str, Any])
async def trigger_backup(
    user: AuthenticatedUser = Depends(require_scope("system:admin"))
):
    """Returns safe mock response for backup triggers."""
    return {
        "status": "authorized",
        "message": (
            "MOCK BACKUP: Compressed PostgreSQL database snapshot "
            "triggered successfully."
        )
    }
