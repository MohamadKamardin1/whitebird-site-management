"""API rate limiting middleware.

Applies fixed-window per-identity throttling to the versioned API using the
default cache backend. Callers presenting a bearer token are limited by
``API_THROTTLE_AUTH_RATE``; anonymous callers by ``API_THROTTLE_ANON_RATE``
(both ``"N/min"`` or ``"N/sec"`` strings). Exceeding the limit returns HTTP 429
with the standard error envelope. Disabled entirely when
``API_THROTTLE_ENABLED`` is false.
"""

from __future__ import annotations

import hashlib
import time
from typing import Any

from django.conf import settings
from django.core.cache import cache
from django.http import JsonResponse

from apps.accounts.tokens import decode_access_token
from apps.core.handlers import error_payload

CACHE_PREFIX = "wbz:throttle"


def _parse_rate(rate: str) -> int | None:
    """Return the allowed requests per 60-second window, or None to skip."""
    try:
        amount, unit = rate.strip().lower().split("/")
        per_minute = int(amount) * (1 if unit.startswith("min") else 60 if unit.startswith("sec") else 1)
        return max(per_minute, 1)
    except (ValueError, AttributeError):
        return None


def _identity(request: Any) -> tuple[str, bool]:
    """Return ``(identity_key, authenticated)`` for the request.

    The Ninja auth layer runs inside the view, so identity is resolved from the
    Authorization header directly (access tokens are decoded statelessly; API
    token keys are hashed for a stable identity).
    """
    header = request.META.get("HTTP_AUTHORIZATION", "")
    if header.startswith("Bearer "):
        token = header[len("Bearer ") :].strip()
        user_id = decode_access_token(token)
        if user_id is not None:
            return f"user:{user_id}", True
        digest = hashlib.sha256(token.encode()).hexdigest()[:16]
        return f"token:{digest}", True
    ip = request.META.get("REMOTE_ADDR", "unknown")
    return f"anon:{ip}", False


class ApiThrottleMiddleware:
    """Fixed-window rate limiter scoped to the versioned API paths."""

    def __init__(self, get_response: Any) -> None:
        self.get_response = get_response

    def __call__(self, request: Any) -> Any:
        if not getattr(settings, "API_THROTTLE_ENABLED", True):
            return self.get_response(request)

        path = request.path_info
        api_prefix = getattr(settings, "API_V1_PREFIX", "api/site-management/v1")
        if not path.startswith(f"/{api_prefix}/"):
            return self.get_response(request)

        identity, authenticated = _identity(request)
        rate = getattr(settings, "API_THROTTLE_AUTH_RATE" if authenticated else "API_THROTTLE_ANON_RATE", "300/min")
        limit = _parse_rate(rate)
        if limit is None:
            return self.get_response(request)

        bucket = int(time.time() // 60)
        key = f"{CACHE_PREFIX}:{identity}:{bucket}"
        count = cache.get(key, 0)
        if count >= limit:
            return JsonResponse(
                error_payload(
                    "rate_limited",
                    "Too many requests. Please retry later.",
                    {},
                ),
                status=429,
            )
        cache.set(key, count + 1, 65)
        return self.get_response(request)
