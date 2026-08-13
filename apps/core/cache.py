"""Cache utilities.

All keys are namespaced under ``wbz_site`` so environments sharing a Redis
instance never collide. Keys are human-readable (no hashing) which makes them
debuggable and bulk-invalidatable via prefix scans.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar, cast

from django.core.cache import cache

T = TypeVar("T")

CACHE_NAMESPACE = "wbz_site"


def key(*parts: object) -> str:
    """Build a namespaced cache key from stable parts."""
    return ":".join([CACHE_NAMESPACE, *(str(part) for part in parts)])


def versioned(version: int | str, *parts: object) -> str:
    """Build a versioned key — bump ``version`` to invalidate an entire family."""
    return key(f"v{version}", *parts)


def cache_key(prefix: str, *parts: object) -> str:
    """Backwards-compatible namespaced key for a prefix + parts."""
    return key(prefix, *parts)


def cached_or[T](
    prefix: str,
    parts: tuple[object, ...],
    loader: Callable[[], T],
    timeout: int = 300,
) -> T:
    """Return the cached value for ``(prefix, parts)`` or compute and store it."""
    full_key = key(prefix, *parts)
    cached = cache.get(full_key)
    if cached is not None:
        return cast(T, cached)
    value = loader()
    cache.set(full_key, value, timeout)
    return value


def get_or_set[T](full_key: str, default_factory: Callable[[], T], timeout: int = 300) -> T:
    """Return the value at ``full_key`` or compute, store, and return it."""
    return cached_or(full_key, (), default_factory, timeout)


def invalidate(prefix: str, *parts: object) -> None:
    """Drop a single cached value identified by prefix+parts."""
    cache.delete(key(prefix, *parts))


def safe_delete(full_key: str) -> bool:
    """Delete a key, tolerating backends that raise on missing keys."""
    try:
        return bool(cache.delete(full_key))
    except Exception:
        return False


def invalidate_prefix(prefix: str) -> None:
    """Best-effort bulk invalidation using Redis ``SCAN``/``DEL``.

    Falls back to no-op on the local-memory cache used by tests, which is
    acceptable because write-path services also invalidate exact keys.
    """
    backend = cache
    try:
        client = backend.client.get_client()  # type: ignore[attr-defined]
        match = f"{CACHE_NAMESPACE}:{prefix}:*"
        keys = list(client.scan_iter(match=match))
        if keys:
            client.delete(*keys)
    except (AttributeError, NotImplementedError):
        pass
