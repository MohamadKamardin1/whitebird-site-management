"""Structured console log formatter.

Emits a single JSON object per line so log aggregators (CloudWatch, Loki,
Splunk) can parse application and request logs without custom grokking.
"""

from __future__ import annotations

import json
import logging
import traceback
from datetime import datetime


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
        }
        if record.exc_info:
            payload["exception"] = "".join(traceback.format_exception(*record.exc_info))
        if hasattr(record, "request_id"):
            payload["request_id"] = record.request_id
        return json.dumps(payload, default=str)
