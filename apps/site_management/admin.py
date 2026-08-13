"""Admin configuration for the site management module."""

from typing import Any

from django.contrib import admin

from .models import (
    Asset,
    AssetCategory,
    Department,
    Notification,
    Site,
    SiteStatus,
    SiteType,
    StaffAssignment,
)


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


@admin.register(Site)
class SiteAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = (
        "name",
        "code",
        "site_type",
        "status",
        "city",
        "region",
        "capacity",
        "is_active",
        "created_at",
    )
    list_filter = ("is_active", "status", "site_type", "region", "country")
    search_fields = ("name", "code", "city", "region")
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ("created_at", "updated_at")
    autocomplete_fields = ("site_type", "status")
    actions = ["archive", "restore"]

    @admin.action(description="Archive selected sites")
    def archive(self, request: Any, queryset: Any) -> None:
        queryset.update(is_active=False)

    @admin.action(description="Restore selected sites")
    def restore(self, request: Any, queryset: Any) -> None:
        queryset.update(is_active=True)


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
    search_fields = ("recipient__username", "title")
    readonly_fields = ("recipient", "title", "body", "entity_type", "entity_id", "created_at")
