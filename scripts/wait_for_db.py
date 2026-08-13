"""Wait for the configured PostgreSQL database to accept connections.

Used by the container entrypoint so migrations never race the database boot.
"""

from __future__ import annotations

import os
import sys
import time

import psycopg


def _database_url() -> str:
    return os.environ.get(
        "DATABASE_URL",
        "postgres://postgres:postgres@127.0.0.1:5432/whitebird",
    )


def wait(timeout: int = 60, interval: float = 1.0) -> None:
    deadline = time.monotonic() + timeout
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            with psycopg.connect(_database_url(), connect_timeout=2):
                return
        except psycopg.Error as exc:  # pragma: no cover - environment helper
            last_error = exc
            time.sleep(interval)
    raise SystemExit(f"database did not become ready within {timeout}s: {last_error}")


if __name__ == "__main__":
    wait(timeout=int(os.environ.get("DB_WAIT_TIMEOUT", "60")))
    sys.exit(0)
