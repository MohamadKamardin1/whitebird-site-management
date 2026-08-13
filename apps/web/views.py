"""Host-facing views: liveness, readiness, and the landing redirect.

These endpoints power container orchestration and operators. The root URL
currently redirects to the Django admin until a dashboard ships.
"""

from __future__ import annotations

from django.core.cache import cache
from django.db import connection
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.shortcuts import redirect


def healthz(request: HttpRequest) -> HttpResponse:
    """Liveness probe — the process is up.

    Deliberately does not touch the database or cache so orchestrators can
    distinguish "process alive" from "dependencies degraded".
    """
    return HttpResponse("OK", content_type="text/plain")


def readyz(request: HttpRequest) -> HttpResponse:
    """Readiness probe — dependencies are reachable.

    Returns HTTP 503 when the database or cache cannot be reached.
    """
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        db_ok = True
    except Exception:
        db_ok = False

    try:
        cache.set("readyz:probe", "ok", timeout=5)
        cache_ok = cache.get("readyz:probe") == "ok"
    except Exception:
        cache_ok = False

    if not (db_ok and cache_ok):
        return HttpResponse("NOT READY", content_type="text/plain", status=503)
    return HttpResponse("OK", content_type="text/plain")


def landing(request: HttpRequest) -> HttpResponseRedirect:
    """Point the platform root at the admin/dashboard for now."""
    return redirect("admin:index")
