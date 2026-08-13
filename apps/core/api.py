"""Common API router: health checks and audit log access."""

from __future__ import annotations

from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.db import connection
from ninja import Router

from apps.accounts.permissions import management_required
from apps.core.requests import AuthenticatedRequest
from apps.core.selectors import list_audit_logs

router = Router()


@router.get("/health", auth=None, summary="Liveness and dependency checks")
def health(request: AuthenticatedRequest) -> dict[str, object]:
    """Report connectivity to the database and cache backend.

    Returns HTTP 200 when dependencies are reachable and 503 otherwise, which
    lets load balancers and orchestrators drive routing decisions.
    """
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        db_ok = True
    except Exception:
        db_ok = False

    try:
        cache.set("health:probe", "ok", timeout=5)
        cache_ok = cache.get("health:probe") == "ok"
    except Exception:
        cache_ok = False

    return {
        "status": "ok" if (db_ok and cache_ok) else "degraded",
        "database": db_ok,
        "cache": cache_ok,
    }


@router.get("/audit-logs", response=list[dict[str, object]], summary="Recent audit entries")
def audit_logs(request: AuthenticatedRequest, limit: int = 50) -> list[dict[str, object]]:
    if not management_required(request.auth):
        raise PermissionDenied("Audit log access requires admin or manager role.")
    return list_audit_logs(limit=limit)
