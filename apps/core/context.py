"""Request-scoped context values shared across the request lifecycle."""

from __future__ import annotations

from contextvars import ContextVar

request_id_var: ContextVar[str] = ContextVar("request_id", default="")


def current_request_id() -> str:
    """Return the request id for the current context ('' outside a request)."""
    return request_id_var.get()
