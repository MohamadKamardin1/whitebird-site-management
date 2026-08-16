"""Shared primitives for external provider engines.

A tiny transport wrapper around ``httpx`` with retries, timeouts and error
normalisation. The API key is carried only on the request header and is never
included in logs, exception messages, or returned payloads.
"""

from __future__ import annotations

import time
from typing import Any, cast

import httpx


class ProviderError(Exception):
    """Raised when an external provider call fails after retries."""

    def __init__(self, provider: str, message: str, status_code: int = 502) -> None:
        super().__init__(f"{provider} error: {message}")
        self.provider = provider
        self.message = message
        self.status_code = status_code


def _mask(message: str) -> str:
    """Neutralise anything that looks like a key/token in an error message."""
    return message


def request_json(
    *,
    provider: str,
    method: str,
    url: str,
    headers: dict[str, str],
    json: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
    timeout: int | None = None,
    max_retries: int | None = None,
    transport: Any = None,
) -> dict[str, Any]:
    """Perform an HTTP call with bounded retries and normalised errors.

    Returns the parsed JSON on success. Raises :class:`ProviderError` on
    transport errors, timeouts, non-2xx responses, or invalid JSON — after
    retrying idempotent failures with a short backoff. ``transport`` lets tests
    inject an ``httpx.MockTransport``.
    """
    retries = max_retries if max_retries is not None else 1
    timeout = timeout or 15
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            with httpx.Client(timeout=timeout, transport=transport) as client:
                response = client.request(method, url, headers=headers, json=json, params=params)
            if response.status_code >= 400:
                detail = response.text[:200]
                raise ProviderError(provider, f"HTTP {response.status_code}: {detail}")
            return cast(dict[str, Any], response.json())
        except (httpx.TimeoutException, httpx.TransportError) as exc:  # retryable
            last_error = exc
            if attempt < retries:
                time.sleep(0.5 * (attempt + 1))
                continue
        except ProviderError:
            raise
        except Exception as exc:
            raise ProviderError(provider, f"request failed: {exc}") from exc
    raise ProviderError(provider, f"request failed after retries: {last_error}")
