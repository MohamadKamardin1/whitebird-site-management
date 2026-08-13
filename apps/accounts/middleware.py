"""Middleware for the accounts app."""

from __future__ import annotations

from collections.abc import Callable

from django.http import HttpRequest, HttpResponse
from django.utils import timezone


class UserTimezoneMiddleware:
    """Activate the authenticated user's timezone for the request.

    Falls back to UTC when the stored timezone is not resolvable, and always
    deactivates after the response so the value never leaks to other requests.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated:
            tz = getattr(user, "timezone", None)
            if tz:
                try:
                    timezone.activate(tz)
                except Exception:
                    timezone.activate("UTC")

        response = self.get_response(request)
        timezone.deactivate()
        return response
