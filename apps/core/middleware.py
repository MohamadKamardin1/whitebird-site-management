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
