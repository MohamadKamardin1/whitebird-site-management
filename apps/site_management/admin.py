"""Admin configuration for the site management module."""

from __future__ import annotations

from typing import Any

from django.contrib import admin
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone

from .models import (
    Asset,
    AssetCategory,
    AssistantGeneralSupervisorAssignment,
    Department,
    Notification,
    Site,
    SiteStatus,
    SiteSupervisorAssignment,
    SiteType,
    StaffAssignment,
    Zone,
    ZoneSupervisorAssignment,
)


@admin.register(Zone)
class ZoneAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ("name", "code", "site_count", "is_active", "created_at")
    list_filter = ("is_active", "created_at")
    search_fields = ("name", "code", "description")
    actions = ["activate_zones", "deactivate_zones"]
    readonly_fields = ("code", "created_at", "updated_at")

    @admin.display(description="Sites")
    def site_count(self, obj: Zone) -> int:
        return obj.sites.filter(is_active=True).count()

    @admin.action(description="Activate selected zones")
    def activate_zones(self, request: Any, queryset: Any) -> None:
        updated = queryset.update(is_active=True, updated_at=timezone.now())
        self.message_user(request, f"{updated} zone(s) activated.")

    @admin.action(description="Deactivate selected zones")
    def deactivate_zones(self, request: Any, queryset: Any) -> None:
        updated = queryset.update(is_active=False, updated_at=timezone.now())
        self.message_user(request, f"{updated} zone(s) deactivated.")

    def delete_model(self, request: Any, obj: Zone) -> None:
        if obj.sites.exists():
            raise DjangoValidationError(f"Cannot delete zone {obj.name}: it has sites. Deactivate it instead.")
        super().delete_model(request, obj)

    def delete_queryset(self, request: Any, queryset: Any) -> None:
        for obj in queryset:
            self.delete_model(request, obj)


class SiteSupervisorInline(admin.TabularInline):  # type: ignore[type-arg]
    model = SiteSupervisorAssignment
    extra = 0
    fk_name = "site"
    raw_id_fields = ("user",)
    fields = ("user", "assigned_from", "assigned_to", "is_primary", "is_active")
    show_change_link = True


@admin.register(Site)
class SiteAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = (
        "name",
        "code",
        "zone",
        "work_mode",
        "status",
        "building_name",
        "city",
        "region",
        "capacity",
        "is_active",
        "start_date",
    )
    list_filter = ("is_active", "status", "site_type", "zone", "work_mode", "region", "country")
    search_fields = ("name", "code", "building_name", "location", "city", "region", "contact_person")
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ("created_at", "updated_at")
    autocomplete_fields = ("site_type", "status", "zone")
    date_hierarchy = "start_date"
    inlines = [SiteSupervisorInline]
    actions = ["archive", "restore"]

    @admin.action(description="Archive selected sites")
    def archive(self, request: Any, queryset: Any) -> None:
        updated = queryset.update(is_active=False, updated_at=timezone.now())
        self.message_user(request, f"{updated} site(s) archived.")

    @admin.action(description="Restore selected sites")
    def restore(self, request: Any, queryset: Any) -> None:
        updated = queryset.update(is_active=True, updated_at=timezone.now())
        self.message_user(request, f"{updated} site(s) restored.")

    def delete_model(self, request: Any, obj: Site) -> None:
        if obj.has_operational_history:
            raise DjangoValidationError(
                f"Cannot delete site {obj.name}: it has operational history. Archive it instead."
            )
        super().delete_model(request, obj)

    def delete_queryset(self, request: Any, queryset: Any) -> None:
        for obj in queryset:
            self.delete_model(request, obj)

    def has_delete_permission(self, request: Any, obj: Site | None = None) -> bool:
        if obj is None:
            return True
        return not obj.has_operational_history


class _BaseAssignmentAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    actions = ["activate_assignments", "deactivate_assignments"]

    @admin.action(description="Activate selected assignments")
    def activate_assignments(self, request: Any, queryset: Any) -> None:
        updated = queryset.update(is_active=True, updated_at=timezone.now())
        self.message_user(request, f"{updated} assignment(s) activated.")

    @admin.action(description="Deactivate selected assignments")
    def deactivate_assignments(self, request: Any, queryset: Any) -> None:
        updated = queryset.update(is_active=False, updated_at=timezone.now())
        self.message_user(request, f"{updated} assignment(s) deactivated.")


@admin.register(SiteSupervisorAssignment)
class SiteSupervisorAssignmentAdmin(_BaseAssignmentAdmin):
    list_display = ("user", "site", "assigned_from", "assigned_to", "is_primary", "is_active", "created_at")
    list_filter = ("is_active", "is_primary", "assigned_from", "site")
    search_fields = ("user__email", "site__name")
    date_hierarchy = "assigned_from"
    raw_id_fields = ("user", "site")


@admin.register(ZoneSupervisorAssignment)
class ZoneSupervisorAssignmentAdmin(_BaseAssignmentAdmin):
    list_display = ("user", "zone", "assigned_from", "assigned_to", "is_active", "created_at")
    list_filter = ("is_active", "assigned_from", "zone")
    search_fields = ("user__email", "zone__name")
    date_hierarchy = "assigned_from"
    raw_id_fields = ("user", "zone")


@admin.register(AssistantGeneralSupervisorAssignment)
class AssistantGeneralSupervisorAssignmentAdmin(_BaseAssignmentAdmin):
    list_display = ("user", "all_zones", "zone", "assigned_from", "assigned_to", "is_active", "created_at")
    list_filter = ("is_active", "all_zones", "assigned_from")
    search_fields = ("user__email", "zone__name")
    date_hierarchy = "assigned_from"
    raw_id_fields = ("user", "zone")


@admin.register(SiteType)
class SiteTypeAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ("name", "slug", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(SiteStatus)
class SiteStatusAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ("name", "slug", "order", "color", "is_active", "created_at")
    list_editable = ("order", "color", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ("name", "site", "manager", "is_active", "created_at")
    list_filter = ("is_active", "site")
    search_fields = ("name", "site__name")
    autocomplete_fields = ("site", "manager")


@admin.register(AssetCategory)
class AssetCategoryAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ("name", "slug", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Asset)
class AssetAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ("name", "site", "category", "quantity", "condition", "is_active")
    list_filter = ("condition", "is_active", "category", "site")
    search_fields = ("name", "serial_number", "site__name")
    autocomplete_fields = ("site", "category")


@admin.register(StaffAssignment)
class StaffAssignmentAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ("user", "site", "role", "is_primary", "assigned_by", "created_at")
    list_filter = ("role", "is_primary", "site")
    search_fields = ("user__email", "site__name")
    autocomplete_fields = ("site", "user")


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ("recipient", "title", "is_read", "entity_type", "created_at")
    list_filter = ("is_read", "created_at")
    search_fields = ("recipient__email", "title")
    readonly_fields = ("recipient", "title", "body", "entity_type", "entity_id", "created_at")
