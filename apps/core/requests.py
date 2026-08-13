"""Typed HTTP request for authenticated API handlers.

Django Ninja attaches the authenticated user to ``request.auth``; this
subclass gives mypy the information Django's own ``HttpRequest`` lacks so
handlers can be strictly typed.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.http import HttpRequest

if TYPE_CHECKING:
    from apps.accounts.models import User


class AuthenticatedRequest(HttpRequest):
    auth: User
