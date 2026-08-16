"""Mapbox geocoding engine.

Forward and reverse geocoding with results cached under a namespaced cache key
so repeat lookups never hit the network. The API key is only ever sent as a
query parameter and is never surfaced in logs, errors, or responses.

Example::

    from apps.integrations import mapbox

    place = mapbox.geocode("Nungwi, Zanzibar")           # -> Feature | None
    coords = mapbox.reverse_geocode(39.2, -5.7)          # -> (lng, lat) | None
"""

from __future__ import annotations

import hashlib
from typing import Any, cast

from django.conf import settings
from django.core.cache import cache

from .transport import ProviderError, request_json

PROVIDER = "Mapbox"
CACHE_PREFIX = "wbz:geo"


def enabled() -> bool:
    return bool(settings.MAPBOX_ENABLED and settings.MAPBOX_API_KEY)


def _require_enabled() -> None:
    if not enabled():
        raise ProviderError(PROVIDER, "Mapbox integration is not configured.")


def _cache_key(kind: str, value: str) -> str:
    digest = hashlib.sha256(value.encode()).hexdigest()[:24]
    return f"{CACHE_PREFIX}:{kind}:{digest}"


def _query(params: dict[str, Any]) -> dict[str, Any]:
    return request_json(
        provider=PROVIDER,
        method="GET",
        url=f"{settings.MAPBOX_GEOCODING_URL.rstrip('/')}/{params.pop('mode', 'mapbox.places')}.json",
        headers={"Content-Type": "application/json"},
        params={**params, "access_token": settings.MAPBOX_API_KEY},
        timeout=settings.MAPBOX_TIMEOUT_SECONDS,
        max_retries=settings.MAPBOX_MAX_RETRIES,
    )


def _feature(payload: dict[str, Any]) -> dict[str, Any] | None:
    try:
        feature = payload["features"][0]
    except (KeyError, IndexError, TypeError):
        return None
    center = feature.get("center") or []
    return {
        "name": feature.get("text") or feature.get("place_name") or "",
        "place_name": feature.get("place_name", ""),
        "longitude": center[0] if len(center) > 0 else None,
        "latitude": center[1] if len(center) > 1 else None,
    }


def geocode(query: str) -> dict[str, Any] | None:
    """Return the best forward-geocoding match for a free-text query."""
    _require_enabled()
    key = _cache_key("fwd", query)
    cached = cache.get(key)
    if cached is not None:
        return cast(dict[str, Any] | None, cached)
    payload = _query({"q": query, "limit": 1, "mode": "mapbox.places"})
    feature = _feature(payload)
    cache.set(key, feature, settings.MAPBOX_GEOCODE_CACHE_TTL)
    return feature


def reverse_geocode(longitude: float, latitude: float) -> dict[str, Any] | None:
    """Return the nearest named place for a coordinate pair."""
    _require_enabled()
    key = _cache_key("rev", f"{longitude:.6f},{latitude:.6f}")
    cached = cache.get(key)
    if cached is not None:
        return cast(dict[str, Any] | None, cached)
    payload = _query({"longitude": longitude, "latitude": latitude, "limit": 1, "mode": "mapbox.places"})
    feature = _feature(payload)
    cache.set(key, feature, settings.MAPBOX_GEOCODE_CACHE_TTL)
    return feature
