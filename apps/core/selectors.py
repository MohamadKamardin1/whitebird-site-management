"""Read-side access to core kernel data."""

from __future__ import annotations

from typing import Any

from .models import AuditLog, DomainEvent


def list_audit_logs(
    *,
    limit: int = 50,
    model_name: str | None = None,
    object_id: str | None = None,
    user_id: int | None = None,
) -> list[dict[str, Any]]:
    """Recent audit entries shaped for API consumers."""
    qs = AuditLog.objects.select_related("user")
    if model_name:
        qs = qs.filter(model_name=model_name)
    if object_id:
        qs = qs.filter(object_id=object_id)
    if user_id is not None:
        qs = qs.filter(user_id=user_id)
    qs = qs[:limit]
    return [
        {
            "id": entry.pk,
            "user": entry.user.get_username() if entry.user else None,
            "action": entry.action,
            "model_name": entry.model_name,
            "object_id": entry.object_id,
            "object_repr": entry.object_repr,
            "before_data": entry.before_data,
            "after_data": entry.after_data,
            "ip_address": entry.ip_address,
            "request_id": entry.request_id,
            "summary": entry.summary,
            "created_at": entry.created_at.isoformat(),
        }
        for entry in qs
    ]


def list_pending_domain_events(*, limit: int = 200) -> list[DomainEvent]:
    """Pending outbox events awaiting publication (for a future publisher)."""
    return list(DomainEvent.objects.filter(status=DomainEvent.Status.PENDING).order_by("occurred_at")[:limit])
