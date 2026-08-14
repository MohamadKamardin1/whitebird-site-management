"""HTTP middleware for the core kernel."""

from __future__ import annotations

import uuid
from collections.abc import Callable

from django.conf import settings
from django.http import HttpRequest, HttpResponse

from .context import request_id_var


class RequestIdMiddleware:
    """Correlate every request with a ``request_id``.

    Uses ``X-Request-ID`` when the caller provides one, otherwise generates a
    UUID. The id is attached to the request, echoed back on the response
    header, and stored in a contextvar so log filters and audit records can
    include it.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response
        self.header = getattr(settings, "REQUEST_ID_HEADER", "HTTP_X_REQUEST_ID")

    def __call__(self, request: HttpRequest) -> HttpResponse:
        request_id = request.META.get(self.header, "").strip() or uuid.uuid4().hex
        request.request_id = request_id  # type: ignore[attr-defined]
        token = request_id_var.set(request_id)
        try:
            response = self.get_response(request)
        finally:
            request_id_var.reset(token)
        response["X-Request-ID"] = request_id
        return response


class SecurityHeadersMiddleware:
    """Add a configurable Content-Security-Policy header to every response.

    The policy is read from ``settings.CSP_DEFAULT_SRC`` / ``CSP_SCRIPT_SRC`` /
    ``CSP_STYLE_SRC`` / ``CSP_IMG_SRC`` (list of origins) with a safe default
    that allows same-origin assets plus the Chart.js CDN used by dashboards.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def _policy(self) -> str:
        default = list(getattr(settings, "CSP_DEFAULT_SRC", ["'self'"]))
        script = list(getattr(settings, "CSP_SCRIPT_SRC", ["'self'", "https://cdn.jsdelivr.net"]))
        style = list(getattr(settings, "CSP_STYLE_SRC", ["'self'", "'unsafe-inline'"]))
        img = list(getattr(settings, "CSP_IMG_SRC", ["'self'", "data:"]))
        return "; ".join(
            [
                "default-src " + " ".join(default),
                "script-src " + " ".join(script),
                "style-src " + " ".join(style),
                "img-src " + " ".join(img),
                "frame-ancestors 'none'",
            ]
        )

    def __call__(self, request: HttpRequest) -> HttpResponse:
        response = self.get_response(request)
        if getattr(settings, "CSP_ENABLED", False):
            response["Content-Security-Policy"] = self._policy()
        return response
