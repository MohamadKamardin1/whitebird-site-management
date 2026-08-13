"""Admin for the core kernel."""

from __future__ import annotations

from typing import Any

from django.contrib import admin

from .models import AuditLog, DomainEvent


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = (
        "created_at",
        "user",
        "action",
        "model_name",
        "object_id",
        "object_repr",
        "ip_address",
        "request_id",
    )
    list_filter = ("action", "model_name", "created_at")
    search_fields = ("object_repr", "object_id", "request_id")
    readonly_fields = (
        "user",
        "action",
        "model_name",
        "object_id",
        "object_repr",
        "before_data",
        "after_data",
        "ip_address",
        "request_id",
        "summary",
        "created_at",
    )
    date_hierarchy = "created_at"

    def has_add_permission(self, request: Any) -> bool:
        return False

    def has_change_permission(self, request: Any, obj: Any = None) -> bool:
        return False

    def has_delete_permission(self, request: Any, obj: Any = None) -> bool:
        return False


@admin.register(DomainEvent)
class DomainEventAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = (
        "occurred_at",
        "event_type",
        "aggregate_type",
        "aggregate_id",
        "status",
        "published_at",
    )
    list_filter = ("status", "event_type", "occurred_at")
    search_fields = ("event_id", "aggregate_type", "aggregate_id", "event_type")
    readonly_fields = (
        "event_id",
        "event_type",
        "aggregate_type",
        "aggregate_id",
        "payload",
        "schema_version",
        "status",
        "occurred_at",
        "published_at",
        "created_by",
    )

    def has_add_permission(self, request: Any) -> bool:
        return False

    def has_change_permission(self, request: Any, obj: Any = None) -> bool:
        return False

    def has_delete_permission(self, request: Any, obj: Any = None) -> bool:
        return False
