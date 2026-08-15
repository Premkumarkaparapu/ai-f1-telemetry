"""Request context storage.

Uses Python's thread-safe and async-safe contextvars to store request-scoped
variables like Request IDs for logging and tracing.
"""

import contextvars

# Thread-safe/async-safe request ID context variable
request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="")


def get_request_id() -> str:
    """Retrieve the request ID for the current execution context."""
    return request_id_var.get()


def set_request_id(request_id: str) -> None:
    """Store the request ID in the current execution context."""
    request_id_var.set(request_id)
