"""Private file storage, validators, and signed-token access.

The private storage backend never exposes files via a public URL. Downloads go
through a signed token (Django signing) that encodes the user, the target
model, the object id, and an expiry (TTL from ``FILE_TOKEN_TTL_SECONDS``).
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from constance import config
from django.conf import settings
from django.core import signing
from django.core.exceptions import ValidationError
from django.core.files.storage import FileSystemStorage

from .context import current_request_id

if TYPE_CHECKING:
    from .models import AuditLog

FILE_TOKEN_SALT = "whitebird.private-file"


class PrivateMediaStorage(FileSystemStorage):
    """Stores uploads under the private media root with no public URL.

    Django replaces ``base_url=None`` with ``MEDIA_URL``; we keep the value
    but make :meth:`url` raise so no code path can accidentally produce a
    publicly accessible link. Downloads go through signed tokens.
    """

    def __init__(self) -> None:
        super().__init__(location=settings.PRIVATE_MEDIA_ROOT, base_url=None)

    def url(self, name: str | None) -> str:
        raise ValueError(
            "Private files have no public URL. Use a signed download token (apps.core.files.create_file_token)."
        )


def allowed_file_extensions() -> list[str]:
    """Return the whitelisted upload extensions (lowercase, no dot)."""
    configured = getattr(settings, "ALLOWED_UPLOAD_EXTENSIONS", None)
    return list(configured) if configured else ["pdf", "jpg", "jpeg", "png", "webp"]


def max_upload_bytes() -> int:
    """Maximum upload size in bytes, from runtime configuration."""
    mb = int(config.MAX_UPLOAD_MB or getattr(settings, "MAX_UPLOAD_MB", 10))
    return mb * 1024 * 1024


def validate_file_extension(value: Any) -> None:
    """Ensure an uploaded file's extension is whitelisted."""
    extension = Path(value.name).suffix.lower().lstrip(".")
    if extension not in allowed_file_extensions():
        raise ValidationError(
            f"File type .{extension or 'unknown'} is not allowed. Allowed: {', '.join(allowed_file_extensions())}.",
            code="invalid_extension",
        )


def validate_file_size(value: Any) -> None:
    """Ensure an uploaded file does not exceed the configured maximum."""
    if getattr(value, "size", 0) > max_upload_bytes():
        raise ValidationError(
            f"File exceeds the {config.MAX_UPLOAD_MB} MB upload limit.",
            code="file_too_large",
        )


def file_token_ttl_seconds() -> int:
    return int(config.FILE_TOKEN_TTL_SECONDS or getattr(settings, "FILE_TOKEN_TTL_SECONDS", 900))


def create_file_token(*, user_id: int, app_label: str, model_name: str, object_id: str | int) -> str:
    """Sign a short-lived download token for a private file."""
    payload = {
        "type": "file",
        "uid": user_id,
        "model": f"{app_label}.{model_name}",
        "oid": str(object_id),
    }
    return signing.dumps(payload, salt=FILE_TOKEN_SALT, compress=True)


def decode_file_token(token: str) -> dict[str, Any] | None:
    """Validate a file token's signature and expiry.

    Returns the payload when valid, otherwise ``None``.
    """
    try:
        payload = signing.loads(token, salt=FILE_TOKEN_SALT, max_age=file_token_ttl_seconds())
    except (signing.BadSignature, signing.SignatureExpired, ValueError, TypeError):
        return None
    if payload.get("type") != "file":
        return None
    return cast(dict[str, Any], payload)


def audit_file_download(
    *,
    user_id: int | None,
    app_label: str,
    model_name: str,
    object_id: str,
    object_repr: str,
    ip_address: str | None = None,
) -> AuditLog:
    """Record a file download in the audit trail."""
    # Lazy imports avoid the models <-> files circular dependency.
    from apps.accounts.models import User  # noqa: PLC0415

    from .models import AuditLog  # noqa: PLC0415
    from .services import record_audit  # noqa: PLC0415

    user = User.objects.filter(pk=user_id).first() if user_id else None
    return record_audit(
        action=AuditLog.Action.FILE_DOWNLOAD,
        user=user,
        model_name=f"{app_label}.{model_name}",
        object_id=object_id,
        object_repr=object_repr,
        ip_address=ip_address,
        request_id=current_request_id(),
        summary=f"Downloaded file for {app_label}.{model_name}:{object_id}",
    )
