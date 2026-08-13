"""Thin, well-named caching helpers over Django's cache framework."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from typing import cast

from django.core.cache import cache


def cache_key(prefix: str, *parts: object) -> str:
    """Deterministic cache key from a prefix and stable parts."""
    fingerprint = hashlib.sha256(json.dumps([str(p) for p in parts], sort_keys=True).encode("utf-8")).hexdigest()[:16]
    return f"{prefix}:{fingerprint}"


def cached_or[T](
    prefix: str,
    parts: tuple[object, ...],
    loader: Callable[[], T],
    timeout: int = 300,
) -> T:
    """Return the cached value for ``(prefix, parts)`` or compute and store it."""
    key = cache_key(prefix, *parts)
    cached = cache.get(key)
    if cached is not None:
        return cast(T, cached)
    value = loader()
    cache.set(key, value, timeout)
    return value


def invalidate(prefix: str, *parts: object) -> None:
    """Drop a single cached value identified by prefix+parts."""
    cache.delete(cache_key(prefix, *parts))


def invalidate_prefix(prefix: str) -> None:
    """Best-effort bulk invalidation using Redis ``SCAN``/``DEL``.

    Falls back to no-op on the local-memory cache used by tests, which is
    acceptable because write-path services also invalidate exact keys.
    """
    backend = cache
    try:
        client = backend.client.get_client()  # type: ignore[attr-defined]
        keys = list(client.scan_iter(match=f"{backend.key_prefix}:{prefix}:*"))
        if keys:
            client.delete(*keys)
    except (AttributeError, NotImplementedError):
        pass
