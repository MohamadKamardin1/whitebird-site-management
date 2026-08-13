"""Core service helpers: audit recording and domain-event outbox."""

from __future__ import annotations

from datetime import date, datetime, time
from typing import TYPE_CHECKING, Any
from uuid import UUID

from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User

from .context import current_request_id
from .models import AuditLog, DomainEvent

if TYPE_CHECKING:
    from django.db.models import Model

_JSON_PRIMITIVES = (str, int, float, bool, type(None))


def model_data(instance: Model) -> dict[str, Any]:
    """JSON-safe snapshot of a model instance for audit before/after data."""
    payload: dict[str, Any] = {}
    for field in instance._meta.concrete_fields:
        value = getattr(instance, field.attname, None)
        if value is None:
            payload[field.name] = None
            continue
        if isinstance(value, UUID):
            payload[field.name] = str(value)
        elif isinstance(value, (datetime, date, time)):
            payload[field.name] = value.isoformat()
        elif isinstance(value, _JSON_PRIMITIVES):
            payload[field.name] = value
        else:
            payload[field.name] = str(value)
    return payload


def _resolve_entity(
    *,
    entity: Model | None,
    model_name: str | None,
    object_id: str | int | None,
    object_repr: str,
) -> tuple[str, str, str]:
    if entity is not None:
        resolved_name = entity._meta.label_lower
        resolved_id = str(entity.pk)
        resolved_repr = object_repr or str(entity)
        return resolved_name, resolved_id, resolved_repr
    if not model_name or object_id is None:
        raise ValueError("record_audit requires an entity or model_name/object_id")
    return model_name, str(object_id), object_repr


def record_audit(
    *,
    action: str | AuditLog.Action,
    user: User | None = None,
    actor: User | None = None,
    entity: Model | None = None,
    model_name: str | None = None,
    object_id: str | int | None = None,
    object_repr: str = "",
    before_data: dict[str, Any] | None = None,
    after_data: dict[str, Any] | None = None,
    changes: dict[str, Any] | None = None,
    ip_address: str | None = None,
    request_id: str | None = None,
    summary: str = "",
) -> AuditLog:
    """Persist a single audit entry.

    Prefer passing ``entity`` plus ``before_data``/``after_data`` snapshots
    (see :func:`model_data`). ``actor`` and ``changes`` are accepted as
    backward-compatible aliases for ``user`` and ``after_data`` respectively.
    ``request_id`` falls back to the current request context.
    """
    resolved_name, resolved_id, resolved_repr = _resolve_entity(
        entity=entity,
        model_name=model_name,
        object_id=object_id,
        object_repr=object_repr,
    )
    action_value = action.value if isinstance(action, AuditLog.Action) else action
    request_id = request_id or current_request_id()

    return AuditLog.objects.create(
        user=user if user is not None else actor,
        action=action_value,
        model_name=resolved_name,
        object_id=resolved_id,
        object_repr=resolved_repr,
        before_data=before_data or {},
        after_data=after_data if after_data is not None else (changes or {}),
        ip_address=ip_address,
        request_id=request_id,
        summary=summary,
        created_at=timezone.now(),
    )


def publish_domain_event(
    *,
    event_type: str,
    aggregate_type: str,
    aggregate_id: str | int | UUID,
    payload: dict[str, Any] | None = None,
    schema_version: int = 1,
    created_by: User | None = None,
) -> None:
    """Register a domain event to be persisted once the transaction commits.

    The event is only written if the surrounding transaction commits; rolled
    back transactions never emit an event. A future publisher worker consumes
    pending events from the outbox.
    """

    def _create() -> DomainEvent:
        return DomainEvent.objects.create(
            event_type=event_type,
            aggregate_type=aggregate_type,
            aggregate_id=str(aggregate_id),
            payload=payload or {},
            schema_version=schema_version,
            created_by=created_by,
        )

    transaction.on_commit(_create)
