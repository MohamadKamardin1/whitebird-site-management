"""Template context processors that expose runtime branding.

Brand values come from django-constance (``BRAND_*``) so the admin and future
frontend share one source of truth. Sensible fallbacks keep templates safe when
constance is unavailable (e.g. during migrations).
"""

from __future__ import annotations

from typing import Any

from django.conf import settings

_FALLBACK = {
    "name": "White Bird Zanzibar",
    "primary": "#A47C00",
    "accent": "#C9A227",
    "background": "#FBF7EF",
}


def brand(request: Any) -> dict[str, Any]:
    """Inject ``brand`` (name + palette) into every template context."""
    try:
        from constance import config

        name = config.BRAND_NAME or _FALLBACK["name"]
        primary = config.BRAND_PRIMARY_COLOR or _FALLBACK["primary"]
        accent = config.BRAND_ACCENT_COLOR or _FALLBACK["accent"]
        background = config.BRAND_BACKGROUND_COLOR or _FALLBACK["background"]
    except Exception:
        name, primary, accent, background = _FALLBACK.values()
    return {
        "brand": {
            "name": name,
            "primary_color": primary,
            "accent_color": accent,
            "background_color": background,
            "app_version": getattr(settings, "API_VERSION", "1.0.0"),
        }
    }
