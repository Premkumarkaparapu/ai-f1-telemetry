"""Audit service — handles synchronous and batched audit logging."""

import hashlib
import logging
import os
import queue
import threading
import time
from typing import Optional

from backend.app.database.db import SessionLocal
from backend.app.database.models import AuditEvent

logger = logging.getLogger(__name__)

# Enforce AUDIT_IP_SALT check
AUDIT_IP_SALT = os.getenv("AUDIT_IP_SALT")
if not AUDIT_IP_SALT:
    class ConfigurationError(Exception):
        pass
    raise ConfigurationError(
        "AUDIT_IP_SALT environment variable is required but not set."
    )


class AuditService:
    def __init__(self):
        self.queue = queue.Queue()
        self._stop_event = threading.Event()
        self.worker_thread = threading.Thread(
            target=self._worker, daemon=True
        )
        self.worker_thread.start()

    def hash_ip(self, ip_address: str) -> str:
        """Salt and SHA-256 hash the client's IP address."""
        if not ip_address:
            ip_address = "127.0.0.1"
        salted = f"{ip_address}{AUDIT_IP_SALT}".encode("utf-8")
        return hashlib.sha256(salted).hexdigest()

    def log_event(
        self,
        event_type: str,
        user_id: Optional[str],
        request_id: str,
        ip_address: str,
        action_details: Optional[str],
        status: str
    ):
        """Routes audit event to write policy (sync vs batched)."""
        ip_hash = self.hash_ip(ip_address)

        # Enforce write policies
        is_sync = event_type.startswith("AUTH_") or event_type in (
            "ADMIN_ACTION", "STRATEGY_SIMULATION", "AI_QUERY"
        )

        event = AuditEvent(
            event_type=event_type,
            user_id=user_id,
            request_id=request_id,
            ip_hash=ip_hash,
            action_details=action_details,
            status=status
        )

        if is_sync:
            self._write_sync(event)
        else:
            self._write_batch(event)

    def _write_sync(self, event: AuditEvent):
        """Synchronously writes audit event, raising exceptions on failure."""
        db = SessionLocal()
        try:
            db.add(event)
            db.commit()
        except Exception as e:
            db.rollback()
            logger.error(
                "Critical audit log write failed for event_type %s: %s",
                event.event_type, e
            )
            # Re-raise to trigger operation rejection
            raise e
        finally:
            db.close()

    def _write_batch(self, event: AuditEvent):
        """Asynchronously queues the audit event for batch writing."""
        self.queue.put(event)

    def _worker(self):
        while not self._stop_event.is_set():
            time.sleep(1.0)
            self.flush()

    def flush(self):
        """Flushes all queued events to the database in a single batch."""
        events = []
        while not self.queue.empty():
            try:
                events.append(self.queue.get_nowait())
            except queue.Empty:
                break

        if not events:
            return

        db = SessionLocal()
        try:
            db.bulk_save_objects(events)
            db.commit()
            for _ in events:
                self.queue.task_done()
        except Exception as e:
            db.rollback()
            logger.error("Failed to save batched audit logs: %s", e)
        finally:
            db.close()

    def shutdown(self):
        """Gracefully flushes final events and stops worker thread."""
        self._stop_event.set()
        self.flush()


# Global single instance of AuditService
audit_service = AuditService()
