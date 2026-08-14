"""Admin configuration for the site management module."""

from __future__ import annotations

from typing import Any

from django.contrib import admin
from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import FileResponse, Http404, HttpResponseForbidden
from django.utils import timezone
from django.utils.safestring import mark_safe

from .models import (
    Asset,
    AssetCategory,
    AssistantGeneralSupervisorAssignment,
    Cleaner,
    CleanerDocument,
    CleanerDocumentStatus,
    Department,
    Notification,
    OperationalRole,
    Site,
    SiteArea,
    SiteShift,
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


class SiteShiftInline(admin.TabularInline):  # type: ignore[type-arg]
    model = SiteShift
    extra = 0
    fk_name = "site"
    fields = ("shift_name", "shift_code", "start_time", "end_time", "effective_days", "sequence", "is_active")
    show_change_link = True


class SiteAreaInline(admin.TabularInline):  # type: ignore[type-arg]
    model = SiteArea
    extra = 0
    fk_name = "site"
    fields = ("area_name", "area_code", "floor", "is_active")
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
    inlines = [SiteSupervisorInline, SiteShiftInline, SiteAreaInline]
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


@admin.register(OperationalRole)
class OperationalRoleAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ("name", "code", "description", "status_badge", "is_active", "created_at")
    list_filter = ("is_active", "created_at")
    search_fields = ("name", "code", "description")
    readonly_fields = ("created_at", "updated_at")
    actions = ["activate_roles", "deactivate_roles"]

    @admin.display(description="Status")
    def status_badge(self, obj: OperationalRole) -> str:
        return "Active" if obj.is_active else "Inactive"

    @admin.action(description="Activate selected roles")
    def activate_roles(self, request: Any, queryset: Any) -> None:
        updated = queryset.update(is_active=True, updated_at=timezone.now())
        self.message_user(request, f"{updated} role(s) activated.")

    @admin.action(description="Deactivate selected roles")
    def deactivate_roles(self, request: Any, queryset: Any) -> None:
        updated = queryset.update(is_active=False, updated_at=timezone.now())
        self.message_user(request, f"{updated} role(s) deactivated.")

    def delete_model(self, request: Any, obj: OperationalRole) -> None:
        if obj.has_operational_usage:
            raise DjangoValidationError(
                f"Cannot delete operational role {obj.name}: it is in use. Deactivate it instead."
            )
        super().delete_model(request, obj)

    def delete_queryset(self, request: Any, queryset: Any) -> None:
        for obj in queryset:
            self.delete_model(request, obj)

    def has_delete_permission(self, request: Any, obj: OperationalRole | None = None) -> bool:
        if obj is None:
            return True
        return not obj.has_operational_usage


class CleanerDocumentInline(admin.TabularInline):  # type: ignore[type-arg]
    model = CleanerDocument
    extra = 0
    fk_name = "cleaner"
    fields = ("document_type", "status", "is_primary_id", "created_at")
    readonly_fields = ("created_at",)
    show_change_link = True


@admin.register(Cleaner)
class CleanerAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ("full_name", "status_badge", "id_type", "masked_id", "gender", "registration_date")
    list_filter = ("status", "id_type", "gender", "registration_date")
    search_fields = ("first_name", "last_name", "id_number")
    date_hierarchy = "registration_date"
    readonly_fields = ("created_at", "updated_at")
    inlines = [CleanerDocumentInline]
    actions = ["activate_cleaners", "deactivate_cleaners"]

    @admin.display(description="Name")
    def full_name(self, obj: Cleaner) -> str:
        return obj.full_name

    @admin.display(description="Status")
    def status_badge(self, obj: Cleaner) -> str:
        return obj.status

    @admin.display(description="ID number")
    def masked_id(self, obj: Cleaner) -> str:
        from .cleaner_selectors import mask_value  # noqa: PLC0415

        return mask_value(obj.id_number)

    @admin.action(description="Activate selected cleaners")
    def activate_cleaners(self, request: Any, queryset: Any) -> None:
        from apps.site_management.cleaner_services import activate_cleaner_if_eligible  # noqa: PLC0415

        activated = 0
        for cleaner in queryset:
            try:
                activate_cleaner_if_eligible(cleaner=cleaner, actor=request.user)
                activated += 1
            except Exception:
                continue
        self.message_user(request, f"{activated} cleaner(s) activated.")

    @admin.action(description="Deactivate selected cleaners")
    def deactivate_cleaners(self, request: Any, queryset: Any) -> None:
        from apps.site_management.cleaner_services import deactivate_cleaner  # noqa: PLC0415

        updated = 0
        for cleaner in queryset:
            deactivate_cleaner(cleaner=cleaner, actor=request.user)
            updated += 1
        self.message_user(request, f"{updated} cleaner(s) deactivated.")

    def delete_model(self, request: Any, obj: Cleaner) -> None:
        if obj.has_operational_history:
            raise DjangoValidationError(
                f"Cannot delete cleaner {obj.full_name}: documents/history exist. Deactivate instead."
            )
        super().delete_model(request, obj)

    def delete_queryset(self, request: Any, queryset: Any) -> None:
        for obj in queryset:
            self.delete_model(request, obj)

    def has_delete_permission(self, request: Any, obj: Cleaner | None = None) -> bool:
        if obj is None:
            return True
        return not obj.has_operational_history


@admin.register(CleanerDocument)
class CleanerDocumentAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = (
        "cleaner",
        "document_type",
        "status_badge",
        "preview",
        "is_primary_id",
        "verified_at",
        "created_at",
    )
    list_filter = ("status", "document_type", "created_at")
    search_fields = ("cleaner__first_name", "cleaner__last_name", "document_number")
    readonly_fields = ("file_hash", "original_filename", "content_type", "size_bytes", "created_at", "updated_at")
    actions = ["verify_documents", "reject_documents"]

    @admin.display(description="Status")
    def status_badge(self, obj: CleanerDocument) -> str:
        return obj.status

    @admin.display(description="Preview")
    def preview(self, obj: CleanerDocument) -> str:
        if obj.content_type.startswith("image/"):
            return mark_safe(f'<a href="{obj.pk}/preview/">View</a>')
        return obj.content_type or "file"

    @admin.action(description="Verify selected documents")
    def verify_documents(self, request: Any, queryset: Any) -> None:
        from apps.site_management.cleaner_services import verify_cleaner_document  # noqa: PLC0415

        updated = 0
        for document in queryset:
            verify_cleaner_document(document=document, actor=request.user)
            updated += 1
        self.message_user(request, f"{updated} document(s) verified.")

    @admin.action(description="Reject selected documents")
    def reject_documents(self, request: Any, queryset: Any) -> None:
        from apps.site_management.cleaner_services import reject_cleaner_document  # noqa: PLC0415

        updated = 0
        for document in queryset:
            reject_cleaner_document(document=document, actor=request.user, reason="Rejected from admin")
            updated += 1
        self.message_user(request, f"{updated} document(s) rejected.")

    def delete_model(self, request: Any, obj: CleanerDocument) -> None:
        if obj.status == CleanerDocumentStatus.VERIFIED:
            raise DjangoValidationError("Verified documents cannot be deleted. Unverify or override with an audit.")
        super().delete_model(request, obj)

    def has_delete_permission(self, request: Any, obj: CleanerDocument | None = None) -> bool:
        if obj is None:
            return True
        return obj.status != CleanerDocumentStatus.VERIFIED

    def get_urls(self) -> list[Any]:
        from django.urls import path  # noqa: PLC0415

        urls = super().get_urls()
        custom = [
            path(
                "<int:document_id>/preview/",
                self.admin_site.admin_view(self.preview_view),
                name="cleaner_document_preview",
            )
        ]
        return custom + urls

    def preview_view(self, request: Any, document_id: int) -> Any:
        """Stream a private image to staff users only (admin session auth)."""
        if not (request.user.is_staff and request.user.has_perm("accounts.view_sensitive_cleaner_documents")):
            return HttpResponseForbidden("Not permitted.")
        document = CleanerDocument.objects.filter(pk=document_id).first()
        if document is None or not document.file.name:
            raise Http404("Document not found.")
        try:
            stream = document.file.storage.open(document.file.name)
        except FileNotFoundError:
            raise Http404("File missing.") from None
        response = FileResponse(stream, content_type=document.content_type or "application/octet-stream")
        response["X-Content-Type-Options"] = "nosniff"
        return response
