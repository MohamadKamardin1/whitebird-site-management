"""Admin configuration for the site management module."""

from __future__ import annotations

from typing import Any

from django.conf import settings
from django.contrib import admin
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Avg, Q
from django.http import FileResponse, Http404, HttpResponseForbidden
from django.utils import timezone
from django.utils.safestring import mark_safe

from apps.accounts.models import RoleCode
from apps.core.files import create_file_token

from .models import (
    Asset,
    AssetCategory,
    AssistantGeneralSummaryReport,
    AssistantGeneralSupervisorAssignment,
    AssistantReportStatus,
    AttendanceRecord,
    AttendanceReviewStatus,
    Cleaner,
    CleanerAreaSchedule,
    CleanerDocument,
    CleanerDocumentStatus,
    CleanerShiftAssignment,
    CleanerSiteAssignment,
    DailySiteReport,
    Department,
    GeneralManagementReport,
    GeneralReportStatus,
    Inspection,
    InspectionResult,
    InspectionTemplate,
    InspectionTemplateItem,
    InspectionWorkflowStatus,
    Issue,
    IssueStatus,
    Job,
    JobStatus,
    Notification,
    OperationalRole,
    Site,
    SiteArea,
    SiteReportStatus,
    SiteShift,
    SiteStatus,
    SiteStore,
    SiteSupervisorAssignment,
    SiteType,
    StaffAssignment,
    StockMovement,
    StockRequest,
    StockRequestItem,
    StockRequestStatus,
    StoreItem,
    TraineeEvaluation,
    TraineeProgram,
    TraineeProgramStatus,
    Zone,
    ZoneReportStatus,
    ZoneSummaryReport,
    ZoneSupervisorAssignment,
)


class ScopedAdminMixin:
    """Role-scoped admin hardening.

    * ``get_queryset`` restricts non-superuser admins to their visible sites
      (Site/Zone/General supervisors) — out-of-scope rows never appear.
    * MANAGEMENT_VIEWER can view (scoped) but never add/change/delete.
    * Subclasses may override ``scope_queryset`` for zone-based or nested-site
      scoping (e.g. StoreItem via ``store__site``).
    """

    def scope_queryset(self, request: Any, qs: Any) -> Any:
        from apps.site_management.scoping import visible_sites

        return qs.filter(site__in=visible_sites(request.user))

    def get_queryset(self, request: Any) -> Any:
        qs = super().get_queryset(request)  # type: ignore[misc]
        user = request.user
        if user.is_superuser or user.is_system_admin or user.role in {RoleCode.GENERAL_SUPERVISOR}:
            return qs
        if user.role == RoleCode.MANAGEMENT_VIEWER:
            return qs
        return self.scope_queryset(request, qs)

    def has_add_permission(self, request: Any) -> bool:
        if request.user.role == RoleCode.MANAGEMENT_VIEWER:
            return False
        return bool(super().has_add_permission(request))  # type: ignore[misc]

    def has_change_permission(self, request: Any, obj: Any = None) -> bool:
        if request.user.role == RoleCode.MANAGEMENT_VIEWER:
            return False
        return bool(super().has_change_permission(request, obj))  # type: ignore[misc]

    def has_delete_permission(self, request: Any, obj: Any = None) -> bool:
        if request.user.role == RoleCode.MANAGEMENT_VIEWER:
            return False
        return bool(super().has_delete_permission(request, obj))  # type: ignore[misc]


@admin.register(Zone)
class ZoneAdmin(ScopedAdminMixin, admin.ModelAdmin):  # type: ignore[type-arg]
    def scope_queryset(self, request: Any, qs: Any) -> Any:
        from apps.site_management.scoping import visible_zones

        return qs.filter(pk__in=visible_zones(request.user))

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
class SiteAdmin(ScopedAdminMixin, admin.ModelAdmin):  # type: ignore[type-arg]
    def scope_queryset(self, request: Any, qs: Any) -> Any:
        from apps.site_management.scoping import visible_sites

        return qs.filter(pk__in=visible_sites(request.user))

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
class CleanerAdmin(ScopedAdminMixin, admin.ModelAdmin):  # type: ignore[type-arg]
    def scope_queryset(self, request: Any, qs: Any) -> Any:
        from apps.site_management.scoping import visible_sites

        return qs.filter(site_assignments__site__in=visible_sites(request.user)).distinct()

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
class CleanerDocumentAdmin(ScopedAdminMixin, admin.ModelAdmin):  # type: ignore[type-arg]
    def scope_queryset(self, request: Any, qs: Any) -> Any:
        from apps.site_management.scoping import visible_sites

        return qs.filter(cleaner__site_assignments__site__in=visible_sites(request.user)).distinct()

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


class CleanerShiftAssignmentInline(admin.TabularInline):  # type: ignore[type-arg]
    model = CleanerShiftAssignment
    extra = 0
    fk_name = "assignment"
    fields = ("shift", "effective_from", "effective_to", "is_active")


class CleanerAreaScheduleInline(admin.TabularInline):  # type: ignore[type-arg]
    model = CleanerAreaSchedule
    extra = 0
    fk_name = "assignment"
    fields = ("site_area", "operational_role", "date", "start_time", "end_time", "is_active")
    show_change_link = True


@admin.register(CleanerSiteAssignment)
class CleanerSiteAssignmentAdmin(ScopedAdminMixin, admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = (
        "cleaner",
        "site",
        "assignment_type",
        "status_badge",
        "start_date",
        "end_date",
        "created_at",
    )
    list_filter = ("status", "assignment_type", "site", "start_date")
    search_fields = ("cleaner__first_name", "cleaner__last_name", "site__name")
    date_hierarchy = "start_date"
    readonly_fields = ("created_at", "updated_at")
    raw_id_fields = ("cleaner", "site", "assigned_by")
    inlines = [CleanerShiftAssignmentInline, CleanerAreaScheduleInline]
    actions = ["activate_assignments", "suspend_assignments", "end_assignments"]

    @admin.display(description="Status")
    def status_badge(self, obj: CleanerSiteAssignment) -> str:
        return obj.status

    @admin.action(description="Activate selected assignments")
    def activate_assignments(self, request: Any, queryset: Any) -> None:
        from apps.site_management.assignment_services import activate_assignment  # noqa: PLC0415

        updated = 0
        for assignment in queryset:
            try:
                activate_assignment(assignment=assignment, actor=request.user)
                updated += 1
            except Exception:
                continue
        self.message_user(request, f"{updated} assignment(s) activated.")

    @admin.action(description="Suspend selected assignments")
    def suspend_assignments(self, request: Any, queryset: Any) -> None:
        from apps.site_management.assignment_services import suspend_assignment  # noqa: PLC0415

        updated = queryset.count()
        for assignment in queryset:
            suspend_assignment(assignment=assignment, actor=request.user)
        self.message_user(request, f"{updated} assignment(s) suspended.")

    @admin.action(description="End selected assignments")
    def end_assignments(self, request: Any, queryset: Any) -> None:
        from apps.site_management.assignment_services import end_assignment  # noqa: PLC0415

        updated = queryset.count()
        for assignment in queryset:
            end_assignment(assignment=assignment, actor=request.user)
        self.message_user(request, f"{updated} assignment(s) ended.")

    def delete_model(self, request: Any, obj: CleanerSiteAssignment) -> None:
        if obj.has_operational_history:
            raise DjangoValidationError("Assignments with shift/schedule history cannot be deleted. End them instead.")
        super().delete_model(request, obj)

    def delete_queryset(self, request: Any, queryset: Any) -> None:
        for obj in queryset:
            self.delete_model(request, obj)

    def has_delete_permission(self, request: Any, obj: CleanerSiteAssignment | None = None) -> bool:
        if obj is None:
            return True
        return not obj.has_operational_history


@admin.register(CleanerShiftAssignment)
class CleanerShiftAssignmentAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ("assignment", "shift", "effective_from", "effective_to", "is_active")
    list_filter = ("is_active", "effective_from")
    search_fields = ("assignment__cleaner__first_name", "assignment__cleaner__last_name", "shift__shift_name")
    raw_id_fields = ("assignment", "shift")


@admin.register(CleanerAreaSchedule)
class CleanerAreaScheduleAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = (
        "assignment",
        "date",
        "site_area",
        "operational_role",
        "start_time",
        "end_time",
        "is_active",
    )
    list_filter = ("is_active", "date")
    search_fields = ("assignment__cleaner__first_name", "assignment__cleaner__last_name", "site_area__area_name")
    raw_id_fields = ("assignment", "site_area", "operational_role", "shift")


@admin.register(AttendanceRecord)
class AttendanceRecordAdmin(ScopedAdminMixin, admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = (
        "attendance_date",
        "site",
        "cleaner",
        "shift",
        "status_badge",
        "review_status_badge",
        "check_in_time",
        "check_out_time",
        "recorded_by",
    )
    list_filter = ("review_status", "status", "site", "attendance_date", "shift")
    search_fields = ("cleaner__first_name", "cleaner__last_name", "site__name", "notes")
    date_hierarchy = "attendance_date"
    raw_id_fields = ("cleaner", "site", "shift", "recorded_by", "created_by", "updated_by")
    actions = ["submit_records", "return_records", "review_records"]

    @admin.display(description="Status")
    def status_badge(self, obj: AttendanceRecord) -> str:
        return obj.status

    @admin.display(description="Review")
    def review_status_badge(self, obj: AttendanceRecord) -> str:
        return obj.review_status

    def get_readonly_fields(self, request: Any, obj: AttendanceRecord | None = None) -> tuple[Any, ...]:
        readonly: tuple[Any, ...] = ("created_at", "updated_at")
        if obj is not None and not obj.is_editable:
            readonly += (
                "cleaner",
                "site",
                "shift",
                "attendance_date",
                "status",
                "check_in_time",
                "check_out_time",
                "notes",
            )
        return readonly

    def has_delete_permission(self, request: Any, obj: AttendanceRecord | None = None) -> bool:
        if obj is None:
            return True
        return obj.review_status in ("draft", "returned")

    @admin.action(description="Submit selected records")
    def submit_records(self, request: Any, queryset: Any) -> None:
        from django.utils import timezone as dj_tz  # noqa: PLC0415

        updated = queryset.exclude(review_status__in=["submitted", "reviewed", "locked"]).update(
            review_status=AttendanceReviewStatus.SUBMITTED,
            submitted_at=dj_tz.now(),
            recorded_by=request.user,
        )
        self.message_user(request, f"{updated} record(s) submitted.")

    @admin.action(description="Return selected records")
    def return_records(self, request: Any, queryset: Any) -> None:
        updated = queryset.exclude(review_status=AttendanceReviewStatus.LOCKED).update(
            review_status=AttendanceReviewStatus.RETURNED,
            return_reason="Returned from admin",
            updated_by=request.user,
        )
        self.message_user(request, f"{updated} record(s) returned.")

    @admin.action(description="Review selected records")
    def review_records(self, request: Any, queryset: Any) -> None:
        updated = queryset.filter(review_status=AttendanceReviewStatus.SUBMITTED).update(
            review_status=AttendanceReviewStatus.REVIEWED,
            updated_by=request.user,
        )
        self.message_user(request, f"{updated} record(s) reviewed.")


class TraineeEvaluationInline(admin.TabularInline):  # type: ignore[type-arg]
    model = TraineeEvaluation
    extra = 0
    fk_name = "trainee_program"
    fields = (
        "evaluation_date",
        "attendance_score",
        "performance_score",
        "behavior_score",
        "skill_score",
        "total_score",
        "is_final",
        "comments",
    )
    readonly_fields = ("total_score",)
    show_change_link = True


@admin.register(TraineeProgram)
class TraineeProgramAdmin(ScopedAdminMixin, admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = (
        "cleaner",
        "site",
        "status_badge",
        "start_date",
        "expected_end_date",
        "actual_end_date",
        "avg_score",
        "assigned_site_supervisor",
    )
    list_filter = ("status", "site", "start_date")
    search_fields = ("cleaner__first_name", "cleaner__last_name", "site__name")
    date_hierarchy = "start_date"
    raw_id_fields = ("cleaner", "site", "assigned_site_supervisor", "created_by", "updated_by")
    inlines = [TraineeEvaluationInline]
    actions = ["extend_programs", "pass_programs", "fail_programs", "drop_programs"]

    @admin.display(description="Status")
    def status_badge(self, obj: TraineeProgram) -> str:
        return obj.status

    @admin.display(description="Avg score")
    def avg_score(self, obj: TraineeProgram) -> str:
        total = obj.evaluations.aggregate(avg=Avg("total_score"))["avg"]
        return f"{total:.1f}" if total is not None else "—"

    def get_readonly_fields(self, request: Any, obj: TraineeProgram | None = None) -> tuple[Any, ...]:
        readonly: tuple[Any, ...] = ("created_at", "updated_at")
        if obj is not None and not obj.is_active_program:
            readonly += ("cleaner", "site", "start_date", "expected_end_date", "actual_end_date", "status")
        return readonly

    def has_delete_permission(self, request: Any, obj: TraineeProgram | None = None) -> bool:
        if obj is None:
            return True
        return obj.is_active_program

    @admin.action(description="Extend selected programs")
    def extend_programs(self, request: Any, queryset: Any) -> None:
        from datetime import date, timedelta  # noqa: PLC0415

        updated = 0
        for program in queryset.filter(status__in=["in_training", "extended"]):
            program.expected_end_date = date.today() + timedelta(days=30)
            program.status = TraineeProgramStatus.EXTENDED
            program.notes = (program.notes + "\n" if program.notes else "") + "Extended: admin batch action"
            program.updated_by = request.user
            program.save()
            updated += 1
        self.message_user(request, f"{updated} program(s) extended by 30 days.")

    @admin.action(description="Pass selected programs")
    def pass_programs(self, request: Any, queryset: Any) -> None:
        from apps.site_management.trainee_services import pass_trainee  # noqa: PLC0415

        updated = 0
        for program in queryset.filter(status__in=["in_training", "extended"]):
            try:
                pass_trainee(program=program, actor=request.user, reason="Passed via admin")
                updated += 1
            except Exception:
                continue
        self.message_user(request, f"{updated} program(s) passed.")

    @admin.action(description="Fail selected programs")
    def fail_programs(self, request: Any, queryset: Any) -> None:
        from apps.site_management.trainee_services import fail_trainee  # noqa: PLC0415

        updated = 0
        for program in queryset.filter(status__in=["in_training", "extended"]):
            fail_trainee(program=program, actor=request.user, reason="Failed via admin")
            updated += 1
        self.message_user(request, f"{updated} program(s) failed.")

    @admin.action(description="Drop selected programs")
    def drop_programs(self, request: Any, queryset: Any) -> None:
        from apps.site_management.trainee_services import drop_trainee  # noqa: PLC0415

        updated = 0
        for program in queryset.filter(status__in=["in_training", "extended"]):
            drop_trainee(program=program, actor=request.user, reason="Dropped via admin")
            updated += 1
        self.message_user(request, f"{updated} program(s) dropped.")


class StoreItemInline(admin.TabularInline):  # type: ignore[type-arg]
    model = StoreItem
    extra = 0
    fk_name = "store"
    fields = (
        "item_name",
        "item_code",
        "unit",
        "category",
        "current_stock",
        "minimum_stock_level",
        "low_stock_badge",
        "is_active",
    )
    readonly_fields = ("current_stock", "low_stock_badge")
    show_change_link = True

    @admin.display(description="Low stock")
    def low_stock_badge(self, obj: StoreItem) -> str:
        return "YES" if obj.low_stock else ""


@admin.register(SiteStore)
class SiteStoreAdmin(ScopedAdminMixin, admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ("store_name", "site", "location", "managed_by", "item_count", "low_stock_badge", "is_active")
    list_filter = ("is_active", "site")
    search_fields = ("store_name", "location", "site__name")
    raw_id_fields = ("site", "managed_by", "created_by", "updated_by")
    inlines = [StoreItemInline]
    actions = ["activate_stores", "deactivate_stores"]

    @admin.display(description="Items")
    def item_count(self, obj: SiteStore) -> int:
        return obj.items.count()

    @admin.display(description="Low stock")
    def low_stock_badge(self, obj: SiteStore) -> str:
        return f"{obj.low_stock_count} item(s)"

    @admin.action(description="Activate selected stores")
    def activate_stores(self, request: Any, queryset: Any) -> None:
        updated = queryset.update(is_active=True, updated_at=timezone.now())
        self.message_user(request, f"{updated} store(s) activated.")

    @admin.action(description="Deactivate selected stores")
    def deactivate_stores(self, request: Any, queryset: Any) -> None:
        updated = queryset.update(is_active=False, updated_at=timezone.now())
        self.message_user(request, f"{updated} store(s) deactivated.")

    def delete_model(self, request: Any, obj: SiteStore) -> None:
        if obj.items.exists():
            raise DjangoValidationError(f"Cannot delete store {obj.store_name}: it has items. Deactivate it instead.")
        super().delete_model(request, obj)

    def delete_queryset(self, request: Any, queryset: Any) -> None:
        for obj in queryset:
            self.delete_model(request, obj)


@admin.register(StoreItem)
class StoreItemAdmin(ScopedAdminMixin, admin.ModelAdmin):  # type: ignore[type-arg]
    def scope_queryset(self, request: Any, qs: Any) -> Any:
        from apps.site_management.scoping import visible_sites

        return qs.filter(store__site__in=visible_sites(request.user))

    list_display = (
        "item_name",
        "store",
        "category",
        "unit",
        "current_stock",
        "minimum_stock_level",
        "low_stock_badge",
        "is_active",
    )
    list_filter = ("is_active", "category", "store__site")
    search_fields = ("item_name", "item_code", "store__store_name")
    raw_id_fields = ("store", "created_by", "updated_by")

    @admin.display(description="Low stock")
    def low_stock_badge(self, obj: StoreItem) -> str:
        return "YES" if obj.low_stock else ""


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = (
        "movement_date",
        "store_item",
        "movement_type",
        "quantity",
        "cleaner",
        "area",
        "recorded_by",
    )
    list_filter = ("movement_type", "movement_date", "store_item__store__site")
    search_fields = ("store_item__item_name", "notes")
    date_hierarchy = "movement_date"
    raw_id_fields = ("store_item", "cleaner", "area", "recorded_by", "created_by", "updated_by")
    readonly_fields = (
        "store_item",
        "movement_type",
        "quantity",
        "movement_date",
        "cleaner",
        "area",
        "notes",
        "recorded_by",
        "created_by",
        "updated_by",
        "created_at",
        "updated_at",
    )

    def has_add_permission(self, request: Any) -> bool:
        return False

    def has_change_permission(self, request: Any, obj: StockMovement | None = None) -> bool:
        return False

    def has_delete_permission(self, request: Any, obj: StockMovement | None = None) -> bool:
        return False


class StockRequestItemInline(admin.TabularInline):  # type: ignore[type-arg]
    model = StockRequestItem
    extra = 0
    fk_name = "request"
    fields = ("store_item", "requested_quantity", "approved_quantity", "notes")
    raw_id_fields = ("store_item",)
    show_change_link = True


@admin.register(StockRequest)
class StockRequestAdmin(ScopedAdminMixin, admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ("id", "store", "site", "request_date", "status_badge", "requested_by", "reviewed_by", "reviewed_at")
    list_filter = ("status", "site", "request_date", "store")
    search_fields = ("store__store_name", "site__name", "notes")
    date_hierarchy = "request_date"
    raw_id_fields = ("site", "store", "requested_by", "reviewed_by", "created_by", "updated_by")
    inlines = [StockRequestItemInline]
    actions = ["submit_requests", "review_requests", "reject_requests", "complete_requests"]
    readonly_fields = ("status", "reviewed_by", "reviewed_at")

    @admin.display(description="Status")
    def status_badge(self, obj: StockRequest) -> str:
        return obj.status

    def get_readonly_fields(self, request: Any, obj: StockRequest | None = None) -> tuple[Any, ...]:
        readonly: tuple[Any, ...] = ("created_at", "updated_at", "reviewed_by", "reviewed_at")
        if obj is not None and obj.status != StockRequestStatus.DRAFT:
            readonly += ("site", "store", "request_date", "status", "notes")
        return readonly

    @admin.action(description="Submit selected requests")
    def submit_requests(self, request: Any, queryset: Any) -> None:
        from apps.site_management.store_services import submit_stock_request  # noqa: PLC0415

        updated = 0
        for stock_request in queryset.filter(status=StockRequestStatus.DRAFT):
            try:
                submit_stock_request(request=stock_request, actor=request.user)
                updated += 1
            except Exception:
                continue
        self.message_user(request, f"{updated} request(s) submitted.")

    @admin.action(description="Review selected requests")
    def review_requests(self, request: Any, queryset: Any) -> None:
        from apps.site_management.store_services import review_stock_request  # noqa: PLC0415

        updated = 0
        for stock_request in queryset.filter(status=StockRequestStatus.SUBMITTED):
            approved = [
                {"item_id": item.pk, "approved_quantity": item.requested_quantity} for item in stock_request.items.all()
            ]
            try:
                review_stock_request(request=stock_request, actor=request.user, approved=approved)
                updated += 1
            except Exception:
                continue
        self.message_user(request, f"{updated} request(s) reviewed.")

    @admin.action(description="Reject selected requests")
    def reject_requests(self, request: Any, queryset: Any) -> None:
        from apps.site_management.store_services import reject_stock_request  # noqa: PLC0415

        updated = 0
        for stock_request in queryset.filter(
            status__in=[StockRequestStatus.SUBMITTED, StockRequestStatus.ZONE_REVIEWED]
        ):
            try:
                reject_stock_request(request=stock_request, actor=request.user, reason="Rejected via admin")
                updated += 1
            except Exception:
                continue
        self.message_user(request, f"{updated} request(s) rejected.")

    @admin.action(description="Complete selected requests")
    def complete_requests(self, request: Any, queryset: Any) -> None:
        from apps.site_management.store_services import complete_stock_request  # noqa: PLC0415

        updated = 0
        for stock_request in queryset.filter(status=StockRequestStatus.ZONE_REVIEWED):
            try:
                complete_stock_request(request=stock_request, actor=request.user)
                updated += 1
            except Exception:
                continue
        self.message_user(request, f"{updated} request(s) completed.")


class InspectionTemplateItemInline(admin.TabularInline):  # type: ignore[type-arg]
    model = InspectionTemplateItem
    extra = 0
    fk_name = "template"
    fields = ("item_label", "item_type", "required", "sequence", "help_text")
    ordering = ("sequence",)


@admin.register(InspectionTemplate)
class InspectionTemplateAdmin(ScopedAdminMixin, admin.ModelAdmin):  # type: ignore[type-arg]
    def scope_queryset(self, request: Any, qs: Any) -> Any:
        from apps.site_management.scoping import visible_sites

        return qs.filter(Q(site__isnull=True) | Q(site__in=visible_sites(request.user)))

    list_display = ("template_name", "site", "frequency", "item_count", "is_active")
    list_filter = ("frequency", "is_active", "site")
    search_fields = ("template_name", "description")
    raw_id_fields = ("site", "area", "created_by", "updated_by")
    inlines = [InspectionTemplateItemInline]
    actions = ["activate_templates", "deactivate_templates"]

    @admin.display(description="Items")
    def item_count(self, obj: InspectionTemplate) -> int:
        return obj.items.count()

    @admin.action(description="Activate selected templates")
    def activate_templates(self, request: Any, queryset: Any) -> None:
        updated = queryset.update(is_active=True, updated_at=timezone.now())
        self.message_user(request, f"{updated} template(s) activated.")

    @admin.action(description="Deactivate selected templates")
    def deactivate_templates(self, request: Any, queryset: Any) -> None:
        from apps.site_management.inspection_services import deactivate_template  # noqa: PLC0415

        updated = 0
        for template in queryset:
            deactivate_template(template=template, actor=request.user)
            updated += 1
        self.message_user(request, f"{updated} template(s) deactivated.")

    def delete_model(self, request: Any, obj: InspectionTemplate) -> None:
        if obj.has_operational_history:
            raise DjangoValidationError(
                f"Cannot delete template {obj.template_name}: inspections exist. Deactivate it instead."
            )
        super().delete_model(request, obj)

    def delete_queryset(self, request: Any, queryset: Any) -> None:
        for obj in queryset:
            self.delete_model(request, obj)


class InspectionResultInline(admin.TabularInline):  # type: ignore[type-arg]
    model = InspectionResult
    extra = 0
    fk_name = "inspection"
    fields = ("template_item", "item_type", "passed", "value_text", "value_number", "value_boolean", "photo_preview")
    readonly_fields = ("template_item", "item_type", "photo_preview")
    raw_id_fields = ("template_item", "uploaded_by")
    can_delete = False

    def get_formset(self, request: Any, obj: Inspection | None = None, **kwargs: Any) -> Any:
        self._request = request
        return super().get_formset(request, obj, **kwargs)

    @admin.display(description="Item type")
    def item_type(self, obj: InspectionResult) -> str:
        return obj.template_item.item_type

    @admin.display(description="Photo")
    def photo_preview(self, obj: InspectionResult) -> str:
        request = getattr(self, "_request", None)
        if not obj.file or request is None:
            return "—"
        token = create_file_token(
            user_id=request.user.pk,
            app_label="site_management",
            model_name="inspectionresult",
            object_id=obj.pk,
        )
        url = f"/{settings.API_V1_PREFIX}/files/signed/{token}/"
        return mark_safe(
            f'<a href="{url}" target="_blank"><img src="{url}" width="48" height="48" '
            'style="object-fit:cover;border-radius:4px" alt="photo"/></a>'
        )


@admin.register(Inspection)
class InspectionAdmin(ScopedAdminMixin, admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = (
        "inspection_date",
        "site",
        "area",
        "template",
        "status_badge",
        "overall_badge",
        "score",
        "inspected_by",
        "submitted_at",
    )
    list_filter = ("status", "overall_status", "site", "inspection_date")
    search_fields = ("site__name", "area__area_name", "template__template_name", "notes")
    date_hierarchy = "inspection_date"
    raw_id_fields = ("site", "area", "template", "shift", "inspected_by", "created_by", "updated_by")
    inlines = [InspectionResultInline]
    actions = ["submit_inspections", "return_inspections", "review_inspections"]

    @admin.display(description="Status")
    def status_badge(self, obj: Inspection) -> str:
        return obj.status

    @admin.display(description="Overall")
    def overall_badge(self, obj: Inspection) -> str:
        return obj.overall_status or "—"

    def get_readonly_fields(self, request: Any, obj: Inspection | None = None) -> tuple[Any, ...]:
        readonly: tuple[Any, ...] = ("created_at", "updated_at")
        if obj is not None and not obj.is_editable:
            readonly += (
                "site",
                "area",
                "template",
                "inspection_date",
                "shift",
                "inspected_by",
                "overall_status",
                "score",
                "status",
                "submitted_at",
            )
        return readonly

    def has_delete_permission(self, request: Any, obj: Inspection | None = None) -> bool:
        if obj is None:
            return True
        return obj.is_editable

    @admin.action(description="Submit selected inspections")
    def submit_inspections(self, request: Any, queryset: Any) -> None:
        from apps.site_management.inspection_services import submit_inspection  # noqa: PLC0415

        updated = 0
        for inspection in queryset.filter(status=InspectionWorkflowStatus.DRAFT):
            try:
                submit_inspection(inspection=inspection, actor=request.user)
                updated += 1
            except Exception:
                continue
        self.message_user(request, f"{updated} inspection(s) submitted.")

    @admin.action(description="Return selected inspections")
    def return_inspections(self, request: Any, queryset: Any) -> None:
        from apps.site_management.inspection_services import return_inspection  # noqa: PLC0415

        updated = 0
        for inspection in queryset.filter(
            status__in=[InspectionWorkflowStatus.SUBMITTED, InspectionWorkflowStatus.REVIEWED]
        ):
            try:
                return_inspection(inspection=inspection, actor=request.user, reason="Returned via admin")
                updated += 1
            except Exception:
                continue
        self.message_user(request, f"{updated} inspection(s) returned.")

    @admin.action(description="Review selected inspections")
    def review_inspections(self, request: Any, queryset: Any) -> None:
        from apps.site_management.inspection_services import review_inspection  # noqa: PLC0415

        updated = 0
        for inspection in queryset.filter(status=InspectionWorkflowStatus.SUBMITTED):
            try:
                review_inspection(inspection=inspection, actor=request.user)
                updated += 1
            except Exception:
                continue
        self.message_user(request, f"{updated} inspection(s) reviewed.")


class JobInline(admin.TabularInline):  # type: ignore[type-arg]
    model = Job
    extra = 0
    fk_name = "issue"
    fields = ("job_title", "priority", "status", "assigned_to_user", "assigned_to_cleaner", "due_date")
    raw_id_fields = ("assigned_to_user", "assigned_to_cleaner", "assigned_by")
    readonly_fields = ("status",)
    show_change_link = True


@admin.register(Issue)
class IssueAdmin(ScopedAdminMixin, admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = (
        "title",
        "site",
        "priority_badge",
        "category_badge",
        "status_badge",
        "source",
        "is_escalated",
        "escalation_level",
        "due_date",
        "assigned_to",
        "raised_by",
    )
    list_filter = ("status", "priority", "issue_category", "source", "site", "is_escalated")
    search_fields = ("title", "description", "site__name")
    date_hierarchy = "created_at"
    raw_id_fields = ("site", "area", "cleaner", "inspection", "raised_by", "assigned_to", "created_by", "updated_by")
    inlines = [JobInline]
    actions = ["escalate_issues", "assign_issues", "verify_issues", "reopen_jobs"]

    @admin.display(description="Priority")
    def priority_badge(self, obj: Issue) -> str:
        return obj.priority

    @admin.display(description="Category")
    def category_badge(self, obj: Issue) -> str:
        return obj.issue_category

    @admin.display(description="Status")
    def status_badge(self, obj: Issue) -> str:
        return obj.status

    def get_readonly_fields(self, request: Any, obj: Issue | None = None) -> tuple[Any, ...]:
        readonly: tuple[Any, ...] = ("created_at", "updated_at")
        if obj is not None and obj.is_terminal:
            readonly += ("title", "site", "source", "status", "priority", "issue_category")
        return readonly

    def has_delete_permission(self, request: Any, obj: Issue | None = None) -> bool:
        if obj is None:
            return True
        return not obj.is_terminal

    @admin.action(description="Escalate selected issues")
    def escalate_issues(self, request: Any, queryset: Any) -> None:
        from apps.site_management.issues_services import escalate_issue  # noqa: PLC0415

        updated = 0
        for issue in queryset.exclude(status=IssueStatus.CLOSED):
            try:
                escalate_issue(issue=issue, actor=request.user, reason="Escalated via admin")
                updated += 1
            except Exception:
                continue
        self.message_user(request, f"{updated} issue(s) escalated.")

    @admin.action(description="Assign selected issues")
    def assign_issues(self, request: Any, queryset: Any) -> None:
        from apps.site_management.issues_services import assign_job_from_issue  # noqa: PLC0415

        updated = 0
        for issue in queryset.filter(status__in=[IssueStatus.OPEN, IssueStatus.UNDER_REVIEW, IssueStatus.REOPENED]):
            assign_job_from_issue(issue=issue, actor=request.user, assigned_to_user=request.user)
            updated += 1
        self.message_user(request, f"{updated} issue(s) assigned.")

    @admin.action(description="Verify jobs for selected issues")
    def verify_issues(self, request: Any, queryset: Any) -> None:
        from apps.site_management.issues_services import verify_job  # noqa: PLC0415

        updated = 0
        for issue in queryset:
            for job in issue.jobs.filter(status=JobStatus.COMPLETED):
                try:
                    verify_job(job=job, actor=request.user)
                    updated += 1
                except Exception:
                    continue
        self.message_user(request, f"{updated} job(s) verified.")

    @admin.action(description="Reopen jobs of selected issues")
    def reopen_jobs(self, request: Any, queryset: Any) -> None:
        from apps.site_management.issues_services import reopen_job  # noqa: PLC0415

        updated = 0
        for issue in queryset:
            for job in issue.jobs.filter(status__in=[JobStatus.CLOSED, JobStatus.COMPLETED, JobStatus.VERIFIED]):
                try:
                    reopen_job(job=job, actor=request.user, reason="Reopened via admin")
                    updated += 1
                except Exception:
                    continue
        self.message_user(request, f"{updated} job(s) reopened.")


@admin.register(Job)
class JobAdmin(ScopedAdminMixin, admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = (
        "job_title",
        "site",
        "issue",
        "priority_badge",
        "status_badge",
        "assigned_to_user",
        "assigned_to_cleaner",
        "due_date",
        "completed_at",
        "verified_at",
    )
    list_filter = ("status", "priority", "site", "due_date")
    search_fields = ("job_title", "description", "site__name")
    date_hierarchy = "due_date"
    raw_id_fields = (
        "issue",
        "site",
        "assigned_to_user",
        "assigned_to_cleaner",
        "assigned_by",
        "verified_by",
        "created_by",
        "updated_by",
    )
    readonly_fields = (
        "status",
        "file",
        "original_filename",
        "content_type",
        "size_bytes",
        "completed_at",
        "verified_at",
        "closed_at",
    )

    @admin.display(description="Priority")
    def priority_badge(self, obj: Job) -> str:
        return obj.priority

    @admin.display(description="Status")
    def status_badge(self, obj: Job) -> str:
        return obj.status

    def has_delete_permission(self, request: Any, obj: Job | None = None) -> bool:
        if obj is None:
            return True
        return not obj.is_terminal


class DailySiteReportAdmin(ScopedAdminMixin, admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ("report_date", "site", "status_badge", "submitted_at", "returned_reason")
    list_filter = ("status", "report_date", "site")
    search_fields = ("site__name", "general_comments")
    date_hierarchy = "report_date"
    raw_id_fields = ("site", "created_by", "updated_by")
    readonly_fields = (
        "attendance_summary",
        "store_summary",
        "inspection_summary",
        "trainee_summary",
        "issues_summary",
        "snapshot",
        "submitted_at",
        "status",
    )
    actions = ["submit_reports", "return_reports"]

    @admin.display(description="Status")
    def status_badge(self, obj: DailySiteReport) -> str:
        return obj.status

    def get_readonly_fields(self, request: Any, obj: DailySiteReport | None = None) -> tuple[Any, ...]:
        readonly: tuple[Any, ...] = (
            "status",
            "submitted_at",
            "attendance_summary",
            "store_summary",
            "inspection_summary",
            "trainee_summary",
            "issues_summary",
            "snapshot",
        )
        if obj is not None and obj.status != SiteReportStatus.DRAFT:
            readonly += ("site", "report_date", "general_comments", "returned_reason")
        return readonly

    def has_delete_permission(self, request: Any, obj: DailySiteReport | None = None) -> bool:
        if obj is None:
            return True
        return obj.status == SiteReportStatus.DRAFT

    @admin.action(description="Submit selected reports")
    def submit_reports(self, request: Any, queryset: Any) -> None:
        from apps.site_management.reporting_services import submit_site_report  # noqa: PLC0415

        updated = 0
        for report in queryset.filter(status=SiteReportStatus.DRAFT):
            try:
                submit_site_report(report=report, user=request.user)
                updated += 1
            except Exception:
                continue
        self.message_user(request, f"{updated} report(s) submitted.")

    @admin.action(description="Return selected reports")
    def return_reports(self, request: Any, queryset: Any) -> None:
        from apps.site_management.reporting_services import return_site_report  # noqa: PLC0415

        updated = 0
        for report in queryset.filter(status__in=[SiteReportStatus.SUBMITTED, SiteReportStatus.ZONE_REVIEWED]):
            try:
                return_site_report(report=report, user=request.user, reason="Returned via admin")
                updated += 1
            except Exception:
                continue
        self.message_user(request, f"{updated} report(s) returned.")


class ZoneSummaryReportAdmin(ScopedAdminMixin, admin.ModelAdmin):  # type: ignore[type-arg]
    def scope_queryset(self, request: Any, qs: Any) -> Any:
        from apps.site_management.scoping import visible_zones

        return qs.filter(zone__in=visible_zones(request.user))

    list_display = ("report_date", "zone", "status_badge", "zone_supervisor", "submitted_at")
    list_filter = ("status", "report_date", "zone")
    search_fields = ("zone__name", "summary")
    date_hierarchy = "report_date"
    raw_id_fields = ("zone", "zone_supervisor", "created_by", "updated_by")
    readonly_fields = ("site_reports", "issues_extracted", "status", "submitted_at")
    actions = ["submit_zone_reports", "return_zone_reports"]

    @admin.display(description="Status")
    def status_badge(self, obj: ZoneSummaryReport) -> str:
        return obj.status

    @admin.action(description="Submit selected zone reports")
    def submit_zone_reports(self, request: Any, queryset: Any) -> None:
        from apps.site_management.reporting_services import submit_zone_summary  # noqa: PLC0415

        updated = 0
        for report in queryset.filter(status=ZoneReportStatus.DRAFT):
            try:
                submit_zone_summary(report=report, user=request.user)
                updated += 1
            except Exception:
                continue
        self.message_user(request, f"{updated} zone report(s) submitted.")

    @admin.action(description="Return selected zone reports")
    def return_zone_reports(self, request: Any, queryset: Any) -> None:
        from apps.site_management.reporting_services import return_zone_summary  # noqa: PLC0415

        updated = 0
        for report in queryset.filter(status=ZoneReportStatus.SUBMITTED):
            try:
                return_zone_summary(report=report, user=request.user, reason="Returned via admin")
                updated += 1
            except Exception:
                continue
        self.message_user(request, f"{updated} zone report(s) returned.")


class AssistantGeneralSummaryReportAdmin(ScopedAdminMixin, admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ("report_date", "status_badge", "assistant_general_supervisor", "submitted_at")
    list_filter = ("status", "report_date")
    date_hierarchy = "report_date"
    raw_id_fields = ("assistant_general_supervisor", "created_by", "updated_by")
    readonly_fields = ("zone_ids", "problems_extracted", "status", "submitted_at")
    actions = ["submit_assistant_reports", "return_assistant_reports"]

    @admin.display(description="Status")
    def status_badge(self, obj: AssistantGeneralSummaryReport) -> str:
        return obj.status

    @admin.action(description="Submit selected assistant reports")
    def submit_assistant_reports(self, request: Any, queryset: Any) -> None:
        from apps.site_management.reporting_services import submit_assistant_summary  # noqa: PLC0415

        updated = 0
        for report in queryset.filter(status=AssistantReportStatus.DRAFT):
            try:
                submit_assistant_summary(report=report, user=request.user)
                updated += 1
            except Exception:
                continue
        self.message_user(request, f"{updated} assistant report(s) submitted.")

    @admin.action(description="Return selected assistant reports")
    def return_assistant_reports(self, request: Any, queryset: Any) -> None:
        from apps.site_management.reporting_services import return_assistant_summary  # noqa: PLC0415

        updated = 0
        for report in queryset.filter(status=AssistantReportStatus.SUBMITTED):
            try:
                return_assistant_summary(report=report, user=request.user, reason="Returned via admin")
                updated += 1
            except Exception:
                continue
        self.message_user(request, f"{updated} assistant report(s) returned.")


class GeneralManagementReportAdmin(ScopedAdminMixin, admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ("report_date", "status_badge", "general_supervisor", "submitted_at")
    list_filter = ("status", "report_date")
    date_hierarchy = "report_date"
    raw_id_fields = ("general_supervisor", "created_by", "updated_by")
    readonly_fields = ("key_issues", "assigned_jobs", "status", "submitted_at")
    actions = ["submit_general_reports"]

    @admin.display(description="Status")
    def status_badge(self, obj: GeneralManagementReport) -> str:
        return obj.status

    @admin.action(description="Submit selected general reports")
    def submit_general_reports(self, request: Any, queryset: Any) -> None:
        from apps.site_management.reporting_services import submit_general_management_report  # noqa: PLC0415

        updated = 0
        for report in queryset.filter(status=GeneralReportStatus.DRAFT):
            try:
                submit_general_management_report(report=report, user=request.user)
                updated += 1
            except Exception:
                continue
        self.message_user(request, f"{updated} general report(s) submitted.")


admin.site.register(DailySiteReport, DailySiteReportAdmin)
admin.site.register(ZoneSummaryReport, ZoneSummaryReportAdmin)
admin.site.register(AssistantGeneralSummaryReport, AssistantGeneralSummaryReportAdmin)
admin.site.register(GeneralManagementReport, GeneralManagementReportAdmin)
