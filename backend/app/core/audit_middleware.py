"""Audit logging middleware — intercepts requests to enforce audit policies."""

import logging
import uuid
import jwt
from typing import Optional
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from backend.app.services.audit_service import audit_service

logger = logging.getLogger(__name__)


class DurableAuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # 1. Resolve request ID
        request_id = request.headers.get("X-Request-ID")
        if not request_id:
            request_id = str(uuid.uuid4())

        # 2. Resolve client IP
        client_ip = (
            request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
            or (request.client.host if request.client else "127.0.0.1")
        )

        # 3. Resolve user identity if token is present
        user_id = self._resolve_user_id(request)

        # 4. Classify event type by request path
        path = request.url.path
        event_type = self._classify_event_type(path)

        if not event_type:
            return await call_next(request)

        # 5. Handle request execution and status resolution
        status = "SUCCESS"
        response = None
        try:
            response = await call_next(request)
            if response.status_code >= 400:
                status = f"FAILED ({response.status_code})"
        except Exception as e:
            status = "FAILED"
            # Write audit log before bubbling up exception
            self._write_audit(
                event_type, user_id, request_id, client_ip, path, status
            )
            raise e

        # 6. Write audit log according to policy
        try:
            self._write_audit(
                event_type, user_id, request_id, client_ip, path, status
            )
        except Exception as e:
            # If synchronous policy fails, we must abort/reject the operation
            is_sync = event_type.startswith("AUTH_") or event_type in (
                "ADMIN_ACTION", "STRATEGY_SIMULATION", "AI_QUERY"
            )
            if is_sync:
                logger.error(
                    "Sync audit write failed. Aborting request. Error: %s", e
                )
                return JSONResponse(
                    status_code=500,
                    content={
                        "detail": (
                            "Critical audit logging failure. Action aborted."
                        )
                    }
                )

        return response

    def _resolve_user_id(self, request: Request) -> Optional[str]:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            try:
                token = auth_header.split(" ")[1]
                payload = jwt.decode(
                    token, options={"verify_signature": False}
                )
                return payload.get("sub")
            except Exception:
                pass
        return None

    def _classify_event_type(self, path: str) -> Optional[str]:
        if path.startswith("/api/v1/auth/"):
            return "AUTH_ACTION"
        elif path.startswith("/api/v1/admin/"):
            return "ADMIN_ACTION"
        elif (
            "strategy/compare" in path
            or path.startswith("/api/v1/predict/strategy")
        ):
            return "STRATEGY_SIMULATION"
        elif path.startswith("/api/v1/predict/"):
            return "MODEL_PREDICTION"
        elif (
            path.startswith("/api/v1/query/")
            or path.startswith("/api/v1/chat/")
            or path.startswith("/api/v1/ai/")
        ):
            return "AI_QUERY"
        elif path.startswith("/api/v1/telemetry/"):
            return "TELEMETRY_ACCESS"
        return None

    def _write_audit(
        self,
        event_type: str,
        user_id: Optional[str],
        request_id: str,
        client_ip: str,
        path: str,
        status: str
    ):
        audit_service.log_event(
            event_type=event_type,
            user_id=user_id,
            request_id=request_id,
            ip_address=client_ip,
            action_details=path,
            status=status
        )
