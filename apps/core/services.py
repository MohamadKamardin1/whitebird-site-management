"""Audit log service functions."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.utils import timezone

from apps.accounts.models import User

from .models import AuditLog

if TYPE_CHECKING:
    from django.db.models import Model


def _entity_key(instance: Model) -> tuple[str, str]:
    return instance._meta.label_lower, str(instance.pk)


def record_audit(
    *,
    action: AuditLog.Action,
    actor: User | None,
    entity: Model | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    summary: str = "",
    changes: dict[str, object] | None = None,
) -> AuditLog:
    """Persist a single audit entry.

    Prefer passing ``entity``; the ``entity_type``/``entity_id`` pair is
    provided for events that do not map to a model instance.
    """
    if entity is not None:
        entity_type, entity_id = _entity_key(entity)
    if not entity_type or entity_id is None:
        raise ValueError("record_audit requires an entity or entity_type/entity_id")

    return AuditLog.objects.create(
        actor=actor,
        action=action.value if isinstance(action, AuditLog.Action) else action,
        entity_type=entity_type,
        entity_id=str(entity_id),
        summary=summary or "",
        changes=changes or {},
        created_at=timezone.now(),
    )
