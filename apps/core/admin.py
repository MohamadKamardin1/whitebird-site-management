"""Admin for the common app."""

from typing import Any

from django.contrib import admin

from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ("created_at", "actor", "action", "entity_type", "entity_id", "summary")
    list_filter = ("action", "entity_type", "created_at")
    search_fields = ("entity_id", "summary")
    readonly_fields = (
        "actor",
        "action",
        "entity_type",
        "entity_id",
        "summary",
        "changes",
        "created_at",
    )
    date_hierarchy = "created_at"

    def has_add_permission(self, request: Any) -> bool:
        return False

    def has_change_permission(self, request: Any, obj: Any = None) -> bool:
        return False

    def has_delete_permission(self, request: Any, obj: Any = None) -> bool:
        return False
