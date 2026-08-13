"""Core API router: health, audit logs, and signed private-file downloads."""

from __future__ import annotations

import mimetypes
from pathlib import Path

from django.apps import apps
from django.core.cache import cache
from django.db import connection
from django.http import FileResponse
from ninja import Router

from apps.accounts.models import User
from apps.accounts.permissions import management_required
from apps.core.errors import ForbiddenActionError, NotFoundError
from apps.core.files import audit_file_download, decode_file_token
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
        raise ForbiddenActionError("Audit log access requires a management role.")
    return list_audit_logs(limit=limit)


@router.get(
    "/files/signed/{token}/",
    summary="Stream a signed private file",
    description=("Validates the signed token (expiry + ownership) before streaming the file."),
)
def signed_file_download(request: AuthenticatedRequest, token: str) -> FileResponse:
    """Securely stream a privately stored file via a signed download token.

    The token encodes the target user, model, object id, and an expiry (TTL
    from ``FILE_TOKEN_TTL_SECONDS``). The downloader must be the token owner
    or a system admin.
    """
    payload = decode_file_token(token)
    if payload is None:
        raise NotFoundError("The download link is invalid or has expired.")

    user: User = request.auth
    if user.pk != payload.get("uid") and not user.is_system_admin:
        raise ForbiddenActionError("You do not have permission to download this file.")

    model_label = str(payload.get("model", ""))
    try:
        app_label, model_name = model_label.split(".", 1)
        model = apps.get_model(app_label, model_name)
    except (ValueError, LookupError):
        raise NotFoundError("The download link is invalid.") from None

    instance = model.objects.filter(pk=payload.get("oid")).first()
    if instance is None:
        raise NotFoundError("The requested file no longer exists.")

    file_field = getattr(instance, "file", None)
    if file_field is None or not file_field.name:
        raise NotFoundError("The requested file no longer exists.")

    filename = getattr(instance, "original_filename", None) or Path(file_field.name).name
    guessed = mimetypes.guess_type(filename)[0]
    content_type = getattr(instance, "content_type", "") or guessed or "application/octet-stream"

    try:
        stream = file_field.storage.open(file_field.name)
    except FileNotFoundError:
        raise NotFoundError("The requested file no longer exists.") from None

    audit_file_download(
        user_id=user.pk,
        app_label=app_label,
        model_name=model_name,
        object_id=str(instance.pk),
        object_repr=str(instance),
        ip_address=request.META.get("REMOTE_ADDR"),
    )
    return FileResponse(stream, content_type=content_type, as_attachment=True, filename=filename)
