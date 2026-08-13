"""Audit log read selector."""

from __future__ import annotations

from typing import Any

from .models import AuditLog


def list_audit_logs(
    *,
    limit: int = 50,
    entity_type: str | None = None,
    entity_id: str | None = None,
) -> list[dict[str, Any]]:
    """Recent audit entries shaped for API consumers."""
    qs = AuditLog.objects.select_related("actor")
    if entity_type:
        qs = qs.filter(entity_type=entity_type)
    if entity_id:
        qs = qs.filter(entity_id=entity_id)
    qs = qs[:limit]
    return [
        {
            "id": entry.pk,
            "actor": entry.actor.get_username() if entry.actor else None,
            "action": entry.action,
            "entity_type": entry.entity_type,
            "entity_id": entry.entity_id,
            "summary": entry.summary,
            "changes": entry.changes,
            "created_at": entry.created_at.isoformat(),
        }
        for entry in qs
    ]
