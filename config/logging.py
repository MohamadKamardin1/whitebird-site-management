"""Structured console logging and request-id correlation.

Log lines are single JSON objects per event. When a request is in flight, its
``request_id`` (set by ``apps.core.middleware.RequestIdMiddleware`` via a
contextvar) is included in every log record so operators can trace a request
through the stack.
"""

from __future__ import annotations

import json
import logging
import traceback
from datetime import datetime

from apps.core.context import current_request_id


class RequestIdFilter(logging.Filter):
    """Attach the current request id to every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = current_request_id()
        return True


class StructuredFormatter(logging.Formatter):
    """Convert a log record into one JSON line per event."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "process": record.process,
            "thread": record.thread,
            "request_id": getattr(record, "request_id", current_request_id()),
        }
        if record.exc_info:
            payload["exception"] = "".join(traceback.format_exception(*record.exc_info))
        return json.dumps(payload, default=str)
