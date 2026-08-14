"""Site management API router.

Routers stay thin: parse/validate input, enforce authorization, delegate to
services (writes) or selectors (reads), and shape output schemas.
"""

from __future__ import annotations

from datetime import date
from typing import Any, cast

from constance import config
from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.http import Http404, StreamingHttpResponse
from ninja import File, Form, Query, Router, UploadedFile

from apps.accounts.models import RoleCode, User
from apps.accounts.permissions import management_required, role_required, user_can_manage_site
from apps.core.files import create_file_token
from apps.core.pagination import PageParams, Paginated, apply_ordering, paginate, paginated_response
from apps.core.requests import AuthenticatedRequest

from .assignment_policies import can_assign_cleaner, can_edit_assignment, can_view_assignment
from .assignment_selectors import (
    AssignmentFilter,
    assignment_area_schedules,
    assignment_list_queryset,
    assignment_shift_assignments,
    get_assignment_or_none,
    scheduled_cleaners_for_attendance,
)
from .assignment_services import (
    activate_assignment,
    assign_cleaner_area_schedule,
    assign_cleaner_shift,
    assign_cleaner_to_site,
    deactivate_area_schedule,
    end_assignment,
    remove_cleaner_shift,
    suspend_assignment,
    update_area_schedule,
    update_assignment,
)
from .attendance_selectors import (
    AttendanceFilter,
    attendance_daily_sheet,
    attendance_exceptions,
    attendance_history_queryset,
    attendance_summary,
    missing_attendance_sites,
)
from .attendance_services import (
    bulk_upsert_attendance,
    generate_daily_attendance_sheet,
    record_single_attendance,
    return_attendance_group,
    return_attendance_record,
    review_attendance_group,
    submit_daily_attendance,
)
from .cleaner_selectors import (
    CleanerFilter,
    can_view_document,
    cleaner_document_serialize,
    cleaner_documents,
    cleaner_list_queryset,
    cleaner_serialize,
    get_cleaner_document_or_none,
    get_cleaner_or_none,
)
from .cleaner_services import (
    change_cleaner_status,
    register_cleaner,
    reject_cleaner_document,
    update_cleaner,
    upload_cleaner_document,
    verify_cleaner_document,
)
from .inspection_selectors import (
    InspectionFilter,
    TemplateFilter,
    get_inspection_or_none,
    get_template_or_none,
    inspection_list,
    inspection_summary,
    template_list,
)
from .inspection_services import (
    add_inspection_result,
    create_template,
    deactivate_template,
    return_inspection,
    review_inspection,
    save_inspection_draft,
    start_inspection,
    submit_inspection,
    update_inspection_result,
    update_template,
    upload_result_photo,
)
from .issues_selectors import (
    IssueFilter,
    JobFilter,
    get_issue_or_none,
    get_job_or_none,
    issue_list,
    issue_summary,
    job_list,
    job_summary,
    overdue_jobs,
)
from .issues_services import (
    assign_job,
    assign_job_from_issue,
    close_job,
    complete_job,
    create_issue,
    create_job,
    escalate_issue,
    reopen_job,
    review_issue,
    start_job,
    update_issue,
    update_job,
    upload_job_photo,
    verify_job,
)
from .models import (
    Asset,
    AssetCategory,
    AssistantGeneralSummaryReport,
    AttendanceRecord,
    AttendanceStatus,
    Cleaner,
    CleanerAreaSchedule,
    CleanerAssignmentType,
    CleanerDocumentType,
    CleanerShiftAssignment,
    CleanerSiteAssignment,
    CleanerStatus,
    DailySiteReport,
    Department,
    Gender,
    GeneralManagementReport,
    IdType,
    Inspection,
    InspectionResult,
    InspectionTemplate,
    InspectionTemplateItem,
    Issue,
    Job,
    Notification,
    OperationalRole,
    Site,
    SiteArea,
    SiteShift,
    SiteStatus,
    SiteStore,
    SiteSupervisorAssignment,
    SiteType,
    StaffAssignment,
    StockMovement,
    StockMovementType,
    StockRequest,
    StoreItem,
    TraineeEvaluation,
    TraineeProgram,
    WorkMode,
    Zone,
    ZoneSummaryReport,
)
from .policies import can_export_data
from .reporting_selectors import (
    assistant_report_detail,
    general_report_detail,
    get_assistant_report_or_none,
    get_general_report_or_none,
    get_site_report_or_none,
    get_zone_report_or_none,
    missing_site_reports,
    reporting_status_dashboard,
    site_report_detail,
    site_reports_for_day,
    zone_report_detail,
)
from .reporting_services import (
    generate_assistant_summary,
    generate_general_management_report,
    generate_site_report,
    generate_zone_summary,
    return_assistant_summary,
    return_site_report,
    return_zone_summary,
    submit_assistant_summary,
    submit_general_management_report,
    submit_site_report,
    submit_zone_summary,
)
from .schemas import (
    AreaScheduleCreateIn,
    AreaScheduleUpdateIn,
    AssetCategoryOut,
    AssetCreateIn,
    AssetOut,
    AssetUpdateIn,
    AssignmentCreateIn,
    AssignmentOut,
    AssistantSummaryGenerateIn,
    AssistantSummaryOut,
    AttendanceBulkIn,
    AttendanceGroupIn,
    AttendanceRecordOut,
    AttendanceReturnIn,
    AttendanceSingleIn,
    AttendanceSubmitOut,
    AttendanceSummaryOut,
    CleanerAreaScheduleOut,
    CleanerCreateIn,
    CleanerDocumentOut,
    CleanerOut,
    CleanerShiftAssignmentOut,
    CleanerSiteAssignmentCreateIn,
    CleanerSiteAssignmentOut,
    CleanerSiteAssignmentUpdateIn,
    CleanerStatusIn,
    CleanerUpdateIn,
    DailySiteReportOut,
    DepartmentCreateIn,
    DepartmentOut,
    DepartmentUpdateIn,
    DocumentReviewIn,
    DownloadUrlOut,
    GeneralReportGenerateIn,
    GeneralReportOut,
    InspectionOut,
    InspectionResultCreateIn,
    InspectionResultOut,
    InspectionResultUpdateIn,
    InspectionReturnIn,
    InspectionStartIn,
    InspectionSummaryOut,
    InspectionTemplateCreateIn,
    InspectionTemplateOut,
    InspectionTemplateStatusIn,
    InspectionTemplateUpdateIn,
    InspectionUpdateIn,
    IssueCreateIn,
    IssueEscalateIn,
    IssueOut,
    IssueReviewIn,
    IssueSummaryOut,
    IssueUpdateIn,
    JobAssignIn,
    JobCompleteIn,
    JobCreateIn,
    JobOut,
    JobReopenIn,
    JobSummaryOut,
    JobUpdateIn,
    MessageOut,
    MissingSiteReportOut,
    NotificationOut,
    OperationalRoleCreateIn,
    OperationalRoleOut,
    OperationalRoleUpdateIn,
    ReportingStatusOut,
    ReportReturnIn,
    ScheduleRowOut,
    ShiftAssignIn,
    SiteAreaCreateIn,
    SiteAreaOut,
    SiteAreaUpdateIn,
    SiteCreateIn,
    SiteDetailOut,
    SiteShiftCreateIn,
    SiteShiftOut,
    SiteShiftUpdateIn,
    SiteStatsOut,
    SiteStatusOut,
    SiteSummaryOut,
    SiteSupervisorOut,
    SiteTypeOut,
    SiteUpdateIn,
    StatusRef,
    StatusUpdateIn,
    StockMovementCreateIn,
    StockMovementOut,
    StockRequestCreateIn,
    StockRequestDecisionIn,
    StockRequestItemOut,
    StockRequestOut,
    StockRequestReviewIn,
    StoreCreateIn,
    StoreItemCreateIn,
    StoreItemOut,
    StoreItemUpdateIn,
    StoreOut,
    TemplateItemIn,
    TemplateItemOut,
    ThemeOut,
    TraineeDecisionIn,
    TraineeEvaluationCreateIn,
    TraineeEvaluationOut,
    TraineeExtendIn,
    TraineeProgramCreateIn,
    TraineeProgramOut,
    TraineeProgramUpdateIn,
    TraineeSummaryOut,
    ZoneOut,
    ZoneReportGenerateIn,
    ZoneSummaryReportOut,
)
from .scoping import site_in_user_scope, visible_sites, visible_zones
from .selectors import (
    SiteFilter,
    get_kpi_overview,
    get_site_detail,
    get_site_or_none,
    get_site_stats,
    list_areas,
    list_assets,
    list_assignments,
    list_departments,
    list_notifications,
    list_operational_roles,
    list_shifts,
    list_site_statuses,
    list_site_types,
    list_sites_queryset,
    unread_notification_count,
)
from .services import (
    SiteDraft,
    archive_site,
    assign_staff,
    create_area,
    create_asset,
    create_department,
    create_operational_role,
    create_shift,
    create_site,
    deactivate_area,
    deactivate_asset,
    deactivate_department,
    deactivate_operational_role,
    deactivate_shift,
    mark_notifications_read,
    restore_site,
    set_primary_assignment,
    unassign_staff,
    update_area,
    update_asset,
    update_department,
    update_operational_role,
    update_shift,
    update_site,
)
from .store_selectors import (
    StockMovementFilter,
    StockRequestFilter,
    StoreFilter,
    low_stock_items,
    stock_items,
    stock_movements,
    stock_request_or_none,
    stock_requests,
    store_list,
)
from .store_services import (
    add_store_item,
    adjust_stock,
    complete_stock_request,
    create_stock_request,
    create_store,
    record_damage_loss,
    record_stock_movement,
    reject_stock_request,
    review_stock_request,
    submit_stock_request,
    update_store_item,
)
from .trainee_selectors import (
    TraineeFilter,
    get_trainee_program_or_none,
    trainee_evaluations,
    trainee_list_queryset,
    trainee_summary,
)
from .trainee_services import (
    drop_trainee,
    extend_trainee_program,
    fail_trainee,
    pass_trainee,
    record_trainee_evaluation,
    start_trainee_program,
    update_trainee_program,
)

PAGE_PARAMS_DEFAULT: Any = Query()  # type: ignore[type-arg]
FILE_PARAM_DEFAULT: Any = File(...)  # type: ignore[type-arg]
FORM_PARAM_DEFAULT: Any = Form(...)  # type: ignore[type-arg]
FORM_EMPTY_DEFAULT: Any = Form("")  # type: ignore[type-arg]
FORM_NONE_DEFAULT: Any = Form(None)  # type: ignore[type-arg]
FORM_FALSE_DEFAULT: Any = Form("false")  # type: ignore[type-arg]

router = Router()


# --------------------------------------------------------------------------- #
# Authorization helpers
# --------------------------------------------------------------------------- #


def _read_access(user: User, site_id: int) -> None:
    if user.is_system_admin:
        return
    if not site_in_user_scope(user, site_id):
        raise PermissionDenied("You do not have access to this site.")


def _write_access(user: User, site_id: int) -> None:
    if user.is_system_admin:
        return
    if not user_can_manage_site(user, site_id):
        raise PermissionDenied("You do not have permission to modify this site.")


def _load_site_or_404(site_id: int) -> Site:
    site = get_site_or_none(site_id)
    if site is None:
        raise Http404("Site not found.")
    return site


def _ensure_role(user: User, *roles: RoleCode) -> None:
    if not role_required(*roles)(user):
        raise PermissionDenied("Insufficient role for this operation.")


def _reload_detail(site_id: int) -> SiteDetailOut:
    payload = get_site_detail(site_id)
    if payload is None:
        raise Http404("Site not found.")
    return SiteDetailOut(**payload)


def _status_ref(site: Site) -> StatusRef | None:
    if site.status is None:
        return None
    return StatusRef(slug=site.status.slug, name=site.status.name, color=site.status.color)


def _summary(site: Site) -> SiteSummaryOut:
    return SiteSummaryOut(
        id=site.pk,
        name=site.name,
        slug=site.slug,
        code=site.code,
        zone_id=site.zone_id,
        zone_name=site.zone.name if site.zone else None,
        site_type=site.site_type.name if site.site_type else None,
        status=_status_ref(site),
        work_mode=WorkMode(site.work_mode),
        building_name=site.building_name,
        location=site.location,
        city=site.city,
        region=site.region,
        country=site.country,
        capacity=site.capacity,
        department_count=getattr(site, "n_departments", site.department_count),
        asset_count=getattr(site, "n_assets", site.asset_count),
        staff_count=getattr(site, "n_staff", site.staff_count),
    )


def _assignment_out(assignment: StaffAssignment) -> AssignmentOut:
    return AssignmentOut(
        id=assignment.pk,
        site_id=assignment.site_id,
        user_id=assignment.user_id,
        email=assignment.user.email,
        role=assignment.role,
        is_primary=assignment.is_primary,
        created_at=assignment.created_at,
    )


def _notification_out(notification: Notification) -> NotificationOut:
    return NotificationOut(
        id=notification.pk,
        title=notification.title,
        body=notification.body,
        entity_type=notification.entity_type,
        entity_id=notification.entity_id,
        is_read=notification.is_read,
        created_at=notification.created_at,
    )


def _type_or_none(site_type_id: int | None) -> SiteType | None:
    if site_type_id is None:
        return None
    return SiteType.objects.filter(pk=site_type_id).first()


def _zone_or_none(zone_id: int | None) -> Zone | None:
    if zone_id is None:
        return None
    return Zone.objects.filter(pk=zone_id).first()


def _status_or_none(status_id: int | None) -> SiteStatus | None:
    if status_id is None:
        return None
    return SiteStatus.objects.filter(pk=status_id).first()


def _category_or_none(category_id: int | None) -> AssetCategory | None:
    if category_id is None:
        return None
    return AssetCategory.objects.filter(pk=category_id).first()


# --------------------------------------------------------------------------- #
# Sites
# --------------------------------------------------------------------------- #


@router.get(
    "/sites",
    response=Paginated[SiteSummaryOut],
    summary="List sites (filterable, paginated)",
)
def site_list(
    request: AuthenticatedRequest,
    filters: PageParams = PAGE_PARAMS_DEFAULT,
    search: str | None = None,
    status: str | None = None,
    site_type: str | None = None,
    region: str | None = None,
    country: str | None = None,
    zone_id: int | None = None,
    work_mode: str | None = None,
    capacity_min: int | None = Query(None, ge=0),  # type: ignore[type-arg]
) -> Paginated[SiteSummaryOut]:
    spec = SiteFilter(
        search=search,
        status=status,
        site_type=site_type,
        region=region,
        country=country,
        capacity_min=capacity_min,
    )
    qs = list_sites_queryset(spec)
    if zone_id is not None:
        qs = qs.filter(zone_id=zone_id)
    if work_mode is not None:
        qs = qs.filter(work_mode=work_mode)
    if not request.auth.is_system_admin:
        qs = qs.filter(pk__in=visible_sites(request.auth))

    items, count, page, page_size = paginate(qs, filters.page, filters.page_size)
    summaries = [_summary(site) for site in items]
    return paginated_response(request, qs, page, page_size, summaries, count)


@router.get("/sites/{site_id}", response=SiteDetailOut, summary="Site detail (cached)")
def site_detail(request: AuthenticatedRequest, site_id: int) -> SiteDetailOut:
    _read_access(request.auth, site_id)
    return _reload_detail(site_id)


@router.post(
    "/sites",
    response=SiteDetailOut,
    summary="Create a site",
)
def site_create(request: AuthenticatedRequest, payload: SiteCreateIn) -> SiteDetailOut:
    _ensure_role(
        request.auth,
        RoleCode.SYSTEM_ADMIN,
        RoleCode.GENERAL_SUPERVISOR,
        RoleCode.ASSISTANT_GENERAL_SUPERVISOR,
        RoleCode.ZONE_SUPERVISOR,
        RoleCode.SITE_SUPERVISOR,
    )
    draft = SiteDraft(
        name=payload.name,
        zone=_zone_or_none(payload.zone_id),
        site_type=_type_or_none(payload.site_type_id),
        status=_status_or_none(payload.status_id),
        description=payload.description,
        building_name=payload.building_name,
        location=payload.location,
        address=payload.address,
        city=payload.city,
        region=payload.region,
        country=payload.country,
        postal_code=payload.postal_code,
        latitude=payload.latitude,
        longitude=payload.longitude,
        capacity=payload.capacity,
        contact_person=payload.contact_person,
        contact_email=payload.contact_email,
        contact_phone=payload.contact_phone,
        work_mode=payload.work_mode,
        working_days=payload.working_days,
        notes=payload.notes,
    )
    site = create_site(draft=draft, actor=request.auth)
    return _reload_detail(site.pk)


@router.patch(
    "/sites/{site_id}",
    response=SiteDetailOut,
    summary="Update a site",
)
def site_update(request: AuthenticatedRequest, site_id: int, payload: SiteUpdateIn) -> SiteDetailOut:
    _write_access(request.auth, site_id)
    current = _load_site_or_404(site_id)
    draft = _draft_from_update(payload, current)
    updated = update_site(site=current, draft=draft, actor=request.auth)
    return _reload_detail(updated.pk)


def _draft_from_update(payload: SiteUpdateIn, current: Site) -> SiteDraft:
    """Merge an update payload over the current state.

    ``None`` means "keep the current value" — use the dedicated management
    flows in the admin to explicitly clear optional fields.
    """

    def pick(value: Any, fallback: Any) -> Any:
        return fallback if value is None else value

    return SiteDraft(
        name=pick(payload.name, current.name),
        zone=(_zone_or_none(payload.zone_id) if payload.zone_id is not None else current.zone),
        site_type=(_type_or_none(payload.site_type_id) if payload.site_type_id is not None else current.site_type),
        status=(_status_or_none(payload.status_id) if payload.status_id is not None else current.status),
        description=pick(payload.description, current.description),
        building_name=pick(payload.building_name, current.building_name),
        location=pick(payload.location, current.location),
        address=pick(payload.address, current.address),
        city=pick(payload.city, current.city),
        region=pick(payload.region, current.region),
        country=pick(payload.country, current.country),
        postal_code=pick(payload.postal_code, current.postal_code),
        latitude=pick(payload.latitude, current.latitude),
        longitude=pick(payload.longitude, current.longitude),
        capacity=pick(payload.capacity, current.capacity),
        contact_person=pick(payload.contact_person, current.contact_person),
        contact_email=pick(payload.contact_email, current.contact_email),
        contact_phone=pick(payload.contact_phone, current.contact_phone),
        work_mode=pick(payload.work_mode, WorkMode(current.work_mode)),
        working_days=pick(payload.working_days, list(current.working_days)),
        notes=pick(payload.notes, current.notes),
    )


@router.delete(
    "/sites/{site_id}",
    response=MessageOut,
    summary="Archive a site (soft delete)",
)
def site_archive(request: AuthenticatedRequest, site_id: int) -> MessageOut:
    _write_access(request.auth, site_id)
    site = _load_site_or_404(site_id)
    archive_site(site=site, actor=request.auth)
    return MessageOut(detail="Site archived.")


@router.post(
    "/sites/{site_id}/restore",
    response=SiteDetailOut,
    summary="Restore an archived site",
)
def site_restore(request: AuthenticatedRequest, site_id: int) -> SiteDetailOut:
    _ensure_role(request.auth, RoleCode.SYSTEM_ADMIN)
    site = Site.objects.all_with_deleted().filter(pk=site_id).first()
    if site is None:
        raise Http404("Site not found.")
    restore_site(site=site, actor=request.auth)
    return _reload_detail(site.pk)


# --------------------------------------------------------------------------- #
# Zones
# --------------------------------------------------------------------------- #


def _zone_out(zone: Zone) -> ZoneOut:
    return ZoneOut(
        id=zone.pk,
        name=zone.name,
        code=zone.code,
        description=zone.description,
        is_active=zone.is_active,
        site_count=zone.sites.filter(is_active=True).count(),
        created_at=zone.created_at,
    )


@router.get(
    "/zones",
    response=Paginated[ZoneOut],
    summary="List zones (paginated, role-scoped)",
)
def zone_list(
    request: AuthenticatedRequest,
    filters: PageParams = PAGE_PARAMS_DEFAULT,
    search: str | None = None,
) -> Paginated[ZoneOut]:
    qs = visible_zones(request.auth)
    if search:
        qs = qs.filter(Q(name__icontains=search) | Q(code__icontains=search))
    items, count, page, page_size = paginate(qs, filters.page, filters.page_size)
    zones = [_zone_out(zone) for zone in items]
    return paginated_response(request, qs, page, page_size, zones, count)


@router.get("/zones/{zone_id}", response=ZoneOut, summary="Zone detail")
def zone_detail(request: AuthenticatedRequest, zone_id: int) -> ZoneOut:
    zone = visible_zones(request.auth).filter(pk=zone_id).first()
    if zone is None:
        raise Http404("Zone not found.")
    return _zone_out(zone)


@router.get(
    "/sites/{site_id}/supervisors",
    response=list[SiteSupervisorOut],
    summary="Active supervisors of a site",
)
def site_supervisors(request: AuthenticatedRequest, site_id: int) -> list[SiteSupervisorOut]:
    _read_access(request.auth, site_id)
    qs = SiteSupervisorAssignment.objects.filter(site_id=site_id, is_active=True).select_related("user", "site")
    return [
        SiteSupervisorOut(
            id=assignment.pk,
            user_id=assignment.user_id,
            email=assignment.user.email,
            full_name=assignment.user.full_name,
            assigned_from=assignment.assigned_from,
            assigned_to=assignment.assigned_to,
            is_primary=assignment.is_primary,
            is_active=assignment.is_active,
        )
        for assignment in qs.order_by("-is_primary", "assigned_from")
    ]


# --------------------------------------------------------------------------- #
# Site configuration: shifts, areas, operational roles
# --------------------------------------------------------------------------- #


def _can_configure_site(user: User) -> bool:
    """Users permitted to change site configuration.

    System admin, the general supervisor, and any user holding the
    ``manage_site_configuration`` permission (granted to assistant/zone/site
    supervisors via RBAC).
    """
    return (
        user.is_system_admin
        or user.role == RoleCode.GENERAL_SUPERVISOR
        or user.has_perm("accounts.manage_site_configuration")
    )


def _site_config_write(user: User, site_id: int) -> None:
    if not _can_configure_site(user):
        raise PermissionDenied("You do not have permission to configure this site.")
    _write_access(user, site_id)


def _shift_out(shift: SiteShift) -> SiteShiftOut:
    return SiteShiftOut(
        id=shift.pk,
        site_id=shift.site_id,
        shift_name=shift.shift_name,
        shift_code=shift.shift_code,
        start_time=shift.start_time,
        end_time=shift.end_time,
        effective_days=list(shift.effective_days),
        sequence=shift.sequence,
        description=shift.description,
        is_active=shift.is_active,
        crosses_midnight=shift.crosses_midnight,
        created_at=shift.created_at,
        updated_at=shift.updated_at,
    )


@router.get("/sites/{site_id}/shifts", response=list[SiteShiftOut], summary="List site shifts")
def shift_list(request: AuthenticatedRequest, site_id: int) -> list[SiteShiftOut]:
    _read_access(request.auth, site_id)
    return [_shift_out(shift) for shift in list_shifts(site_id)]


@router.post("/sites/{site_id}/shifts", response=SiteShiftOut, summary="Create a site shift")
def shift_create(request: AuthenticatedRequest, site_id: int, payload: SiteShiftCreateIn) -> SiteShiftOut:
    _site_config_write(request.auth, site_id)
    site = _load_site_or_404(site_id)
    shift = create_shift(
        site=site,
        shift_name=payload.shift_name,
        shift_code=payload.shift_code,
        start_time=payload.start_time,
        end_time=payload.end_time,
        effective_days=payload.effective_days,
        sequence=payload.sequence,
        description=payload.description,
        actor=request.auth,
    )
    return _shift_out(shift)


@router.put(
    "/sites/{site_id}/shifts/{shift_id}",
    response=SiteShiftOut,
    summary="Update a site shift",
)
def shift_update(
    request: AuthenticatedRequest, site_id: int, shift_id: int, payload: SiteShiftUpdateIn
) -> SiteShiftOut:
    _site_config_write(request.auth, site_id)
    shift = SiteShift.objects.filter(pk=shift_id, site_id=site_id).first()
    if shift is None:
        raise Http404("Shift not found.")
    updated = update_shift(
        shift=shift,
        actor=request.auth,
        shift_name=payload.shift_name,
        shift_code=payload.shift_code,
        start_time=payload.start_time,
        end_time=payload.end_time,
        effective_days=payload.effective_days,
        sequence=payload.sequence,
        description=payload.description,
    )
    return _shift_out(updated)


@router.patch(
    "/sites/{site_id}/shifts/{shift_id}/status",
    response=SiteShiftOut,
    summary="Activate or deactivate a site shift",
)
def shift_status(request: AuthenticatedRequest, site_id: int, shift_id: int, payload: StatusUpdateIn) -> SiteShiftOut:
    _site_config_write(request.auth, site_id)
    shift = SiteShift.objects.filter(pk=shift_id, site_id=site_id).first()
    if shift is None:
        raise Http404("Shift not found.")
    updated = (
        update_shift(shift=shift, actor=request.auth)
        if payload.is_active
        else deactivate_shift(shift=shift, actor=request.auth)
    )
    return _shift_out(updated)


def _area_out(area: SiteArea) -> SiteAreaOut:
    return SiteAreaOut(
        id=area.pk,
        site_id=area.site_id,
        area_name=area.area_name,
        area_code=area.area_code,
        floor=area.floor,
        description=area.description,
        is_active=area.is_active,
        created_at=area.created_at,
        updated_at=area.updated_at,
    )


@router.get("/sites/{site_id}/areas", response=list[SiteAreaOut], summary="List site areas")
def area_list(request: AuthenticatedRequest, site_id: int) -> list[SiteAreaOut]:
    _read_access(request.auth, site_id)
    return [_area_out(area) for area in list_areas(site_id)]


@router.post("/sites/{site_id}/areas", response=SiteAreaOut, summary="Create a site area")
def area_create(request: AuthenticatedRequest, site_id: int, payload: SiteAreaCreateIn) -> SiteAreaOut:
    _site_config_write(request.auth, site_id)
    site = _load_site_or_404(site_id)
    area = create_area(
        site=site,
        area_name=payload.area_name,
        area_code=payload.area_code,
        floor=payload.floor,
        description=payload.description,
        actor=request.auth,
    )
    return _area_out(area)


@router.put(
    "/sites/{site_id}/areas/{area_id}",
    response=SiteAreaOut,
    summary="Update a site area",
)
def area_update(request: AuthenticatedRequest, site_id: int, area_id: int, payload: SiteAreaUpdateIn) -> SiteAreaOut:
    _site_config_write(request.auth, site_id)
    area = SiteArea.objects.filter(pk=area_id, site_id=site_id).first()
    if area is None:
        raise Http404("Area not found.")
    updated = update_area(
        area=area,
        actor=request.auth,
        area_name=payload.area_name,
        area_code=payload.area_code,
        floor=payload.floor,
        description=payload.description,
    )
    return _area_out(updated)


@router.patch(
    "/sites/{site_id}/areas/{area_id}/status",
    response=SiteAreaOut,
    summary="Activate or deactivate a site area",
)
def area_status(request: AuthenticatedRequest, site_id: int, area_id: int, payload: StatusUpdateIn) -> SiteAreaOut:
    _site_config_write(request.auth, site_id)
    area = SiteArea.objects.filter(pk=area_id, site_id=site_id).first()
    if area is None:
        raise Http404("Area not found.")
    updated = (
        update_area(area=area, actor=request.auth)
        if payload.is_active
        else deactivate_area(area=area, actor=request.auth)
    )
    return _area_out(updated)


def _role_out(role: OperationalRole) -> OperationalRoleOut:
    return OperationalRoleOut(
        id=role.pk,
        name=role.name,
        code=role.code,
        description=role.description,
        is_active=role.is_active,
        created_at=role.created_at,
        updated_at=role.updated_at,
    )


@router.get("/operational-roles", response=list[OperationalRoleOut], summary="List operational roles")
def operational_role_list(request: AuthenticatedRequest) -> list[OperationalRoleOut]:
    if not management_required(request.auth):
        raise PermissionDenied("Operational roles require a management role.")
    return [_role_out(role) for role in list_operational_roles()]


@router.post("/operational-roles", response=OperationalRoleOut, summary="Create an operational role")
def operational_role_create(request: AuthenticatedRequest, payload: OperationalRoleCreateIn) -> OperationalRoleOut:
    if not _can_configure_site(request.auth):
        raise PermissionDenied("You do not have permission to configure operational roles.")
    role = create_operational_role(
        name=payload.name, code=payload.code, description=payload.description, actor=request.auth
    )
    return _role_out(role)


@router.put("/operational-roles/{role_id}", response=OperationalRoleOut, summary="Update an operational role")
def operational_role_update(
    request: AuthenticatedRequest, role_id: int, payload: OperationalRoleUpdateIn
) -> OperationalRoleOut:
    if not _can_configure_site(request.auth):
        raise PermissionDenied("You do not have permission to configure operational roles.")
    role = OperationalRole.objects.filter(pk=role_id).first()
    if role is None:
        raise Http404("Operational role not found.")
    updated = update_operational_role(
        role=role,
        actor=request.auth,
        name=payload.name,
        code=payload.code,
        description=payload.description,
    )
    return _role_out(updated)


@router.patch(
    "/operational-roles/{role_id}/status",
    response=OperationalRoleOut,
    summary="Activate or deactivate an operational role",
)
def operational_role_status(request: AuthenticatedRequest, role_id: int, payload: StatusUpdateIn) -> OperationalRoleOut:
    if not _can_configure_site(request.auth):
        raise PermissionDenied("You do not have permission to configure operational roles.")
    role = OperationalRole.objects.filter(pk=role_id).first()
    if role is None:
        raise Http404("Operational role not found.")
    updated = (
        update_operational_role(role=role, actor=request.auth)
        if payload.is_active
        else deactivate_operational_role(role=role, actor=request.auth)
    )
    return _role_out(updated)


# --------------------------------------------------------------------------- #
# Catalog (configuration-driven reference data)
# --------------------------------------------------------------------------- #


@router.get("/catalog/types", response=list[SiteTypeOut], summary="Site types catalog")
def catalog_types(request: AuthenticatedRequest) -> list[SiteType]:
    return list_site_types()


@router.get("/catalog/statuses", response=list[SiteStatusOut], summary="Site statuses catalog")
def catalog_statuses(request: AuthenticatedRequest) -> list[SiteStatus]:
    return list_site_statuses()


@router.get(
    "/catalog/categories",
    response=list[AssetCategoryOut],
    summary="Asset categories catalog",
)
def catalog_categories(request: AuthenticatedRequest) -> list[AssetCategory]:
    return list(AssetCategory.objects.filter(is_active=True))


# --------------------------------------------------------------------------- #
# Departments
# --------------------------------------------------------------------------- #


@router.get(
    "/sites/{site_id}/departments",
    response=list[DepartmentOut],
    summary="List departments",
)
def department_list(request: AuthenticatedRequest, site_id: int) -> list[Department]:
    _read_access(request.auth, site_id)
    return list_departments(site_id)


@router.post(
    "/sites/{site_id}/departments",
    response=DepartmentOut,
    summary="Create a department",
)
def department_create(request: AuthenticatedRequest, site_id: int, payload: DepartmentCreateIn) -> Department:
    _write_access(request.auth, site_id)
    site = _load_site_or_404(site_id)
    return create_department(site=site, name=payload.name, description=payload.description, actor=request.auth)


@router.patch(
    "/sites/{site_id}/departments/{department_id}",
    response=DepartmentOut,
    summary="Update a department",
)
def department_update(
    request: AuthenticatedRequest, site_id: int, department_id: int, payload: DepartmentUpdateIn
) -> Department:
    _write_access(request.auth, site_id)
    department = Department.objects.filter(pk=department_id, site_id=site_id, is_active=True).first()
    if department is None:
        raise Http404("Department not found.")
    return update_department(
        department=department,
        name=payload.name,
        description=payload.description,
        actor=request.auth,
    )


@router.delete(
    "/sites/{site_id}/departments/{department_id}",
    response=MessageOut,
    summary="Deactivate a department",
)
def department_delete(request: AuthenticatedRequest, site_id: int, department_id: int) -> MessageOut:
    _write_access(request.auth, site_id)
    department = Department.objects.filter(pk=department_id, site_id=site_id, is_active=True).first()
    if department is None:
        raise Http404("Department not found.")
    deactivate_department(department=department, actor=request.auth)
    return MessageOut(detail="Department deactivated.")


# --------------------------------------------------------------------------- #
# Assets
# --------------------------------------------------------------------------- #


@router.get("/sites/{site_id}/assets", response=list[AssetOut], summary="List assets")
def asset_list(request: AuthenticatedRequest, site_id: int, category: str | None = None) -> list[Asset]:
    _read_access(request.auth, site_id)
    return list_assets(site_id, category)


@router.post(
    "/sites/{site_id}/assets",
    response=AssetOut,
    summary="Register an asset",
)
def asset_create(request: AuthenticatedRequest, site_id: int, payload: AssetCreateIn) -> Asset:
    _write_access(request.auth, site_id)
    site = _load_site_or_404(site_id)
    return create_asset(
        site=site,
        name=payload.name,
        category=_category_or_none(payload.category_id),
        serial_number=payload.serial_number,
        quantity=payload.quantity,
        condition=payload.condition,
        actor=request.auth,
    )


@router.patch(
    "/sites/{site_id}/assets/{asset_id}",
    response=AssetOut,
    summary="Update an asset",
)
def asset_update(request: AuthenticatedRequest, site_id: int, asset_id: int, payload: AssetUpdateIn) -> Asset:
    _write_access(request.auth, site_id)
    asset = Asset.objects.filter(pk=asset_id, site_id=site_id, is_active=True).first()
    if asset is None:
        raise Http404("Asset not found.")
    return update_asset(
        asset=asset,
        name=payload.name,
        category=(_category_or_none(payload.category_id) if payload.category_id is not None else None),
        serial_number=payload.serial_number,
        quantity=payload.quantity,
        condition=payload.condition,
        actor=request.auth,
    )


@router.delete(
    "/sites/{site_id}/assets/{asset_id}",
    response=MessageOut,
    summary="Retire an asset",
)
def asset_delete(request: AuthenticatedRequest, site_id: int, asset_id: int) -> MessageOut:
    _write_access(request.auth, site_id)
    asset = Asset.objects.filter(pk=asset_id, site_id=site_id, is_active=True).first()
    if asset is None:
        raise Http404("Asset not found.")
    deactivate_asset(asset=asset, actor=request.auth)
    return MessageOut(detail="Asset retired.")


# --------------------------------------------------------------------------- #
# Staff assignments
# --------------------------------------------------------------------------- #


@router.get(
    "/sites/{site_id}/assignments",
    response=list[AssignmentOut],
    summary="List staff assignments",
)
def assignment_list(request: AuthenticatedRequest, site_id: int) -> list[AssignmentOut]:
    _read_access(request.auth, site_id)
    return [_assignment_out(a) for a in list_assignments(site_id)]


@router.post(
    "/sites/{site_id}/assignments",
    response=AssignmentOut,
    summary="Assign staff to a site",
)
def assignment_create(request: AuthenticatedRequest, site_id: int, payload: AssignmentCreateIn) -> AssignmentOut:
    _write_access(request.auth, site_id)
    site = _load_site_or_404(site_id)
    user = User.objects.filter(pk=payload.user_id, is_active=True).first()
    if user is None:
        raise Http404("User not found.")
    assignment = assign_staff(
        site=site,
        user=user,
        role=payload.role,
        is_primary=payload.is_primary,
        actor=request.auth,
    )
    return _assignment_out(assignment)


@router.delete(
    "/sites/{site_id}/assignments/{assignment_id}",
    response=MessageOut,
    summary="Unassign staff from a site",
)
def assignment_delete(request: AuthenticatedRequest, site_id: int, assignment_id: int) -> MessageOut:
    _write_access(request.auth, site_id)
    assignment = StaffAssignment.objects.filter(pk=assignment_id, site_id=site_id).first()
    if assignment is None:
        raise Http404("Assignment not found.")
    unassign_staff(assignment=assignment, actor=request.auth)
    return MessageOut(detail="Staff unassigned.")


@router.post(
    "/sites/{site_id}/assignments/{assignment_id}/primary",
    response=AssignmentOut,
    summary="Mark assignment as the user's primary site",
)
def assignment_set_primary(request: AuthenticatedRequest, site_id: int, assignment_id: int) -> AssignmentOut:
    _write_access(request.auth, site_id)
    assignment = StaffAssignment.objects.filter(pk=assignment_id, site_id=site_id).first()
    if assignment is None:
        raise Http404("Assignment not found.")
    return _assignment_out(set_primary_assignment(assignment=assignment, actor=request.auth))


# --------------------------------------------------------------------------- #
# Statistics
# --------------------------------------------------------------------------- #


@router.get("/sites/{site_id}/stats", response=SiteStatsOut, summary="Per-site statistics (cached)")
def site_stats(request: AuthenticatedRequest, site_id: int) -> SiteStatsOut:
    _read_access(request.auth, site_id)
    payload = get_site_stats(site_id)
    if not payload:
        raise Http404("Site not found.")
    return SiteStatsOut(**payload)


@router.get(
    "/stats/overview",
    response=dict,
    summary="Cross-site statistics overview",
)
def stats_overview(request: AuthenticatedRequest) -> dict[str, object]:
    _ensure_role(request.auth, RoleCode.SYSTEM_ADMIN)
    return get_kpi_overview()


# --------------------------------------------------------------------------- #
# Notifications
# --------------------------------------------------------------------------- #


@router.get(
    "/notifications",
    response=list[NotificationOut],
    summary="My notifications",
)
def notification_list(request: AuthenticatedRequest, unread_only: bool = False) -> list[NotificationOut]:
    return [_notification_out(n) for n in list_notifications(request.auth, unread_only=unread_only)]


@router.get("/notifications/unread-count", response=dict, summary="Unread notification count")
def notification_unread_count(request: AuthenticatedRequest) -> dict[str, object]:
    return {"count": unread_notification_count(request.auth)}


@router.post(
    "/notifications/mark-read",
    response=dict,
    summary="Mark notifications as read",
)
def notification_mark_read(request: AuthenticatedRequest, notification_ids: list[int]) -> dict[str, object]:
    updated = mark_notifications_read(user=request.auth, notification_ids=notification_ids)
    return {"updated": updated}


# --------------------------------------------------------------------------- #
# Cleaner registry
# --------------------------------------------------------------------------- #


def _cleaner_read(user: User) -> None:
    if not management_required(user):
        raise PermissionDenied("Cleaner records require a management role.")


def _cleaner_write(user: User) -> None:
    if not (
        user.is_system_admin
        or user.role == RoleCode.GENERAL_SUPERVISOR
        or user.has_perm("accounts.manage_site_configuration")
    ):
        raise PermissionDenied("You do not have permission to manage cleaners.")


def _document_review(user: User) -> None:
    if not (
        user.is_system_admin
        or user.role == RoleCode.GENERAL_SUPERVISOR
        or user.has_perm("accounts.view_sensitive_cleaner_documents")
    ):
        raise PermissionDenied("You do not have permission to review cleaner documents.")


@router.get(
    "/cleaners",
    response=Paginated[CleanerOut],
    summary="List cleaners (paginated, PII masked)",
)
def cleaner_list(
    request: AuthenticatedRequest,
    filters: PageParams = PAGE_PARAMS_DEFAULT,
    search: str | None = None,
    status: str | None = None,
    id_type: str | None = None,
    gender: str | None = None,
    ordering: str | None = None,
) -> Paginated[CleanerOut]:
    _cleaner_read(request.auth)
    spec = CleanerFilter(search=search, status=status, id_type=id_type, gender=gender)
    qs = apply_ordering(cleaner_list_queryset(request.auth, spec), ordering, ["first_name", "last_name", "created_at"])
    items, count, page, page_size = paginate(qs, filters.page, filters.page_size)
    results = [CleanerOut(**cleaner_serialize(c, request.auth)) for c in items]
    return paginated_response(request, qs, page, page_size, results, count)


@router.post("/cleaners", response=CleanerOut, summary="Register a cleaner")
def cleaner_create(request: AuthenticatedRequest, payload: CleanerCreateIn) -> CleanerOut:
    _cleaner_write(request.auth)
    cleaner = register_cleaner(
        first_name=payload.first_name,
        last_name=payload.last_name,
        id_type=IdType(payload.id_type),
        id_number=payload.id_number,
        birth_date=payload.birth_date,
        gender=Gender(payload.gender),
        living_location=payload.living_location,
        phone_number=payload.phone_number,
        near_person_name=payload.near_person_name,
        near_person_relationship=payload.near_person_relationship,
        near_person_phone=payload.near_person_phone,
        notes=payload.notes,
        actor=request.auth,
    )
    return CleanerOut(**cleaner_serialize(cleaner, request.auth))


@router.get("/cleaners/{cleaner_id}", response=CleanerOut, summary="Cleaner detail")
def cleaner_detail(request: AuthenticatedRequest, cleaner_id: int) -> CleanerOut:
    _cleaner_read(request.auth)
    cleaner = get_cleaner_or_none(cleaner_id)
    if cleaner is None:
        raise Http404("Cleaner not found.")
    return CleanerOut(**cleaner_serialize(cleaner, request.auth))


@router.put("/cleaners/{cleaner_id}", response=CleanerOut, summary="Update a cleaner")
def cleaner_update(request: AuthenticatedRequest, cleaner_id: int, payload: CleanerUpdateIn) -> CleanerOut:
    _cleaner_write(request.auth)
    cleaner = get_cleaner_or_none(cleaner_id)
    if cleaner is None:
        raise Http404("Cleaner not found.")
    updated = update_cleaner(
        cleaner=cleaner,
        actor=request.auth,
        first_name=payload.first_name,
        last_name=payload.last_name,
        gender=Gender(payload.gender) if payload.gender else None,
        living_location=payload.living_location,
        phone_number=payload.phone_number,
        near_person_name=payload.near_person_name,
        near_person_relationship=payload.near_person_relationship,
        near_person_phone=payload.near_person_phone,
        notes=payload.notes,
    )
    return CleanerOut(**cleaner_serialize(updated, request.auth))


@router.patch("/cleaners/{cleaner_id}/status", response=CleanerOut, summary="Change cleaner status")
def cleaner_status(request: AuthenticatedRequest, cleaner_id: int, payload: CleanerStatusIn) -> CleanerOut:
    _cleaner_write(request.auth)
    cleaner = get_cleaner_or_none(cleaner_id)
    if cleaner is None:
        raise Http404("Cleaner not found.")
    updated = change_cleaner_status(cleaner=cleaner, new_status=CleanerStatus(payload.status), actor=request.auth)
    return CleanerOut(**cleaner_serialize(updated, request.auth))


# --------------------------------------------------------------------------- #
# Cleaner documents
# --------------------------------------------------------------------------- #


@router.get("/cleaners/{cleaner_id}/documents", response=list[CleanerDocumentOut], summary="List cleaner documents")
def document_list(request: AuthenticatedRequest, cleaner_id: int) -> list[CleanerDocumentOut]:
    _cleaner_read(request.auth)
    cleaner = get_cleaner_or_none(cleaner_id)
    if cleaner is None:
        raise Http404("Cleaner not found.")
    return [
        CleanerDocumentOut(**cleaner_document_serialize(doc, request.auth)) for doc in cleaner_documents(cleaner_id)
    ]


@router.post(
    "/cleaners/{cleaner_id}/documents",
    response=CleanerDocumentOut,
    summary="Upload a cleaner document (multipart)",
)
def document_upload(
    request: AuthenticatedRequest,
    cleaner_id: int,
    file: UploadedFile = FILE_PARAM_DEFAULT,
    document_type: str = FORM_PARAM_DEFAULT,
    document_number: str = FORM_EMPTY_DEFAULT,
    expires_at: str | None = FORM_NONE_DEFAULT,
    is_primary_id: str = FORM_FALSE_DEFAULT,
) -> CleanerDocumentOut:
    _cleaner_write(request.auth)
    cleaner = get_cleaner_or_none(cleaner_id)
    if cleaner is None:
        raise Http404("Cleaner not found.")
    expires = None
    if expires_at:
        expires = date.fromisoformat(expires_at)
    document = upload_cleaner_document(
        cleaner=cleaner,
        uploaded_file=file,
        document_type=CleanerDocumentType(document_type),
        document_number=document_number,
        expires_at=expires,
        is_primary_id=is_primary_id.lower() in {"true", "1", "yes"},
        actor=request.auth,
    )
    return CleanerDocumentOut(**cleaner_document_serialize(document, request.auth))


@router.get(
    "/cleaners/{cleaner_id}/documents/{document_id}",
    response=CleanerDocumentOut,
    summary="Cleaner document detail",
)
def document_detail(request: AuthenticatedRequest, cleaner_id: int, document_id: int) -> CleanerDocumentOut:
    _cleaner_read(request.auth)
    document = get_cleaner_document_or_none(cleaner_id, document_id)
    if document is None:
        raise Http404("Document not found.")
    return CleanerDocumentOut(**cleaner_document_serialize(document, request.auth))


@router.post(
    "/cleaners/{cleaner_id}/documents/{document_id}/verify",
    response=CleanerDocumentOut,
    summary="Verify a cleaner document",
)
def document_verify(request: AuthenticatedRequest, cleaner_id: int, document_id: int) -> CleanerDocumentOut:
    _document_review(request.auth)
    document = get_cleaner_document_or_none(cleaner_id, document_id)
    if document is None:
        raise Http404("Document not found.")
    verified = verify_cleaner_document(document=document, actor=request.auth)
    return CleanerDocumentOut(**cleaner_document_serialize(verified, request.auth))


@router.post(
    "/cleaners/{cleaner_id}/documents/{document_id}/reject",
    response=CleanerDocumentOut,
    summary="Reject a cleaner document",
)
def document_reject(
    request: AuthenticatedRequest, cleaner_id: int, document_id: int, payload: DocumentReviewIn
) -> CleanerDocumentOut:
    _document_review(request.auth)
    document = get_cleaner_document_or_none(cleaner_id, document_id)
    if document is None:
        raise Http404("Document not found.")
    rejected = reject_cleaner_document(document=document, actor=request.auth, reason=payload.reason)
    return CleanerDocumentOut(**cleaner_document_serialize(rejected, request.auth))


@router.get(
    "/cleaners/{cleaner_id}/documents/{document_id}/download-url",
    response=DownloadUrlOut,
    summary="Signed download URL for a private document",
)
def document_download_url(request: AuthenticatedRequest, cleaner_id: int, document_id: int) -> DownloadUrlOut:
    _cleaner_read(request.auth)
    document = get_cleaner_document_or_none(cleaner_id, document_id)
    if document is None:
        raise Http404("Document not found.")
    if not can_view_document(request.auth, document):
        raise PermissionDenied("You do not have permission to view this document.")
    token = create_file_token(
        user_id=request.auth.pk,
        app_label="site_management",
        model_name="cleanerdocument",
        object_id=document.pk,
    )
    return DownloadUrlOut(download_url=f"/{settings.API_V1_PREFIX}/files/signed/{token}/")


# --------------------------------------------------------------------------- #
# Cleaner assignments & scheduling
# --------------------------------------------------------------------------- #


def _assignment_read(user: User) -> None:
    if not (management_required(user) or user.is_management_viewer):
        raise PermissionDenied("Assignments require a management role.")


def _cleaner_assignment_out(a: CleanerSiteAssignment) -> CleanerSiteAssignmentOut:
    return CleanerSiteAssignmentOut(
        id=a.pk,
        cleaner_id=a.cleaner_id,
        cleaner_name=a.cleaner.full_name,
        site_id=a.site_id,
        site_name=a.site.name,
        assignment_type=a.assignment_type,
        start_date=a.start_date,
        end_date=a.end_date,
        status=a.status,
        assigned_by=a.assigned_by.email if a.assigned_by else None,
        notes=a.notes,
        created_at=a.created_at,
        updated_at=a.updated_at,
    )


def _cleaner_shift_out(sa: CleanerShiftAssignment) -> CleanerShiftAssignmentOut:
    return CleanerShiftAssignmentOut(
        id=sa.pk,
        assignment_id=sa.assignment_id,
        shift_id=sa.shift_id,
        shift_name=sa.shift.shift_name,
        effective_from=sa.effective_from,
        effective_to=sa.effective_to,
        is_active=sa.is_active,
    )


def _schedule_out(s: CleanerAreaSchedule) -> CleanerAreaScheduleOut:
    return CleanerAreaScheduleOut(
        id=s.pk,
        assignment_id=s.assignment_id,
        site_area_id=s.site_area_id,
        area_name=s.site_area.area_name,
        operational_role_id=s.operational_role_id,
        role_name=s.operational_role.name,
        date=s.date,
        start_time=s.start_time,
        end_time=s.end_time,
        shift_id=s.shift_id,
        shift_name=s.shift.shift_name if s.shift else None,
        notes=s.notes,
        is_active=s.is_active,
        crosses_midnight=s.crosses_midnight,
    )


@router.get(
    "/assignments",
    response=Paginated[CleanerSiteAssignmentOut],
    summary="List cleaner site assignments (paginated, role-scoped)",
)
def cleaner_assignment_list(
    request: AuthenticatedRequest,
    filters: PageParams = PAGE_PARAMS_DEFAULT,
    cleaner_id: int | None = None,
    site_id: int | None = None,
    status: str | None = None,
    assignment_type: str | None = None,
    search: str | None = None,
) -> Paginated[CleanerSiteAssignmentOut]:
    _assignment_read(request.auth)
    spec = AssignmentFilter(
        cleaner_id=cleaner_id, site_id=site_id, status=status, assignment_type=assignment_type, search=search
    )
    qs = assignment_list_queryset(request.auth, spec)
    items, count, page, page_size = paginate(qs, filters.page, filters.page_size)
    results = [_cleaner_assignment_out(a) for a in items]
    return paginated_response(request, qs, page, page_size, results, count)


@router.post("/assignments", response=CleanerSiteAssignmentOut, summary="Assign a cleaner to a site")
def cleaner_assignment_create(
    request: AuthenticatedRequest, payload: CleanerSiteAssignmentCreateIn
) -> CleanerSiteAssignmentOut:
    _assignment_read(request.auth)
    cleaner = get_cleaner_or_none(payload.cleaner_id)
    if cleaner is None:
        raise Http404("Cleaner not found.")
    site = get_site_or_none(payload.site_id)
    if site is None:
        raise Http404("Site not found.")
    if not can_assign_cleaner(request.auth, site, cleaner):
        raise PermissionDenied("You cannot assign cleaners to this site.")
    assignment = assign_cleaner_to_site(
        cleaner=cleaner,
        site=site,
        assignment_type=CleanerAssignmentType(payload.assignment_type),
        start_date=payload.start_date,
        end_date=payload.end_date,
        notes=payload.notes,
        actor=request.auth,
    )
    return _cleaner_assignment_out(assignment)


@router.get("/assignments/{assignment_id}", response=CleanerSiteAssignmentOut, summary="Assignment detail")
def cleaner_assignment_detail(request: AuthenticatedRequest, assignment_id: int) -> CleanerSiteAssignmentOut:
    _assignment_read(request.auth)
    assignment = get_assignment_or_none(assignment_id)
    if assignment is None:
        raise Http404("Assignment not found.")
    if not can_view_assignment(request.auth, assignment):
        raise PermissionDenied("You do not have access to this assignment.")
    return _cleaner_assignment_out(assignment)


@router.put("/assignments/{assignment_id}", response=CleanerSiteAssignmentOut, summary="Update an assignment")
def cleaner_assignment_update(
    request: AuthenticatedRequest, assignment_id: int, payload: CleanerSiteAssignmentUpdateIn
) -> CleanerSiteAssignmentOut:
    _assignment_read(request.auth)
    assignment = get_assignment_or_none(assignment_id)
    if assignment is None:
        raise Http404("Assignment not found.")
    if not can_edit_assignment(request.auth, assignment):
        raise PermissionDenied("You cannot edit this assignment.")
    updated = update_assignment(
        assignment=assignment, actor=request.auth, end_date=payload.end_date, notes=payload.notes
    )
    return _cleaner_assignment_out(updated)


@router.patch("/assignments/{assignment_id}/end", response=CleanerSiteAssignmentOut, summary="End an assignment")
def cleaner_assignment_end(request: AuthenticatedRequest, assignment_id: int) -> CleanerSiteAssignmentOut:
    _assignment_read(request.auth)
    assignment = get_assignment_or_none(assignment_id)
    if assignment is None:
        raise Http404("Assignment not found.")
    if not can_edit_assignment(request.auth, assignment):
        raise PermissionDenied("You cannot edit this assignment.")
    return _cleaner_assignment_out(end_assignment(assignment=assignment, actor=request.auth))


@router.patch(
    "/assignments/{assignment_id}/suspend", response=CleanerSiteAssignmentOut, summary="Suspend an assignment"
)
def cleaner_assignment_suspend(request: AuthenticatedRequest, assignment_id: int) -> CleanerSiteAssignmentOut:
    _assignment_read(request.auth)
    assignment = get_assignment_or_none(assignment_id)
    if assignment is None:
        raise Http404("Assignment not found.")
    if not can_edit_assignment(request.auth, assignment):
        raise PermissionDenied("You cannot edit this assignment.")
    return _cleaner_assignment_out(suspend_assignment(assignment=assignment, actor=request.auth))


@router.patch(
    "/assignments/{assignment_id}/activate", response=CleanerSiteAssignmentOut, summary="Activate an assignment"
)
def cleaner_assignment_activate(request: AuthenticatedRequest, assignment_id: int) -> CleanerSiteAssignmentOut:
    _assignment_read(request.auth)
    assignment = get_assignment_or_none(assignment_id)
    if assignment is None:
        raise Http404("Assignment not found.")
    if not can_edit_assignment(request.auth, assignment):
        raise PermissionDenied("You cannot edit this assignment.")
    return _cleaner_assignment_out(activate_assignment(assignment=assignment, actor=request.auth))


@router.get(
    "/assignments/{assignment_id}/shifts", response=list[CleanerShiftAssignmentOut], summary="List assignment shifts"
)
def cleaner_assignment_shifts(request: AuthenticatedRequest, assignment_id: int) -> list[CleanerShiftAssignmentOut]:
    _assignment_read(request.auth)
    assignment = get_assignment_or_none(assignment_id)
    if assignment is None:
        raise Http404("Assignment not found.")
    if not can_view_assignment(request.auth, assignment):
        raise PermissionDenied("You do not have access to this assignment.")
    return [_cleaner_shift_out(sa) for sa in assignment_shift_assignments(assignment_id)]


@router.post(
    "/assignments/{assignment_id}/shifts", response=CleanerShiftAssignmentOut, summary="Assign a shift to the cleaner"
)
def cleaner_assignment_shift_create(
    request: AuthenticatedRequest, assignment_id: int, payload: ShiftAssignIn
) -> CleanerShiftAssignmentOut:
    _assignment_read(request.auth)
    assignment = get_assignment_or_none(assignment_id)
    if assignment is None:
        raise Http404("Assignment not found.")
    if not can_edit_assignment(request.auth, assignment):
        raise PermissionDenied("You cannot edit this assignment.")
    shift = SiteShift.objects.filter(pk=payload.shift_id).first()
    if shift is None:
        raise Http404("Shift not found.")
    sa = assign_cleaner_shift(
        assignment=assignment,
        shift=shift,
        effective_from=payload.effective_from,
        effective_to=payload.effective_to,
        actor=request.auth,
    )
    return _cleaner_shift_out(sa)


@router.delete(
    "/assignments/{assignment_id}/shifts/{shift_assignment_id}",
    response=MessageOut,
    summary="Remove a shift from the assignment",
)
def cleaner_assignment_shift_delete(
    request: AuthenticatedRequest, assignment_id: int, shift_assignment_id: int
) -> MessageOut:
    _assignment_read(request.auth)
    assignment = get_assignment_or_none(assignment_id)
    if assignment is None:
        raise Http404("Assignment not found.")
    if not can_edit_assignment(request.auth, assignment):
        raise PermissionDenied("You cannot edit this assignment.")
    sa = CleanerShiftAssignment.objects.filter(pk=shift_assignment_id, assignment_id=assignment_id).first()
    if sa is None:
        raise Http404("Shift assignment not found.")
    remove_cleaner_shift(shift_assignment=sa, actor=request.auth)
    return MessageOut(detail="Shift removed.")


@router.get(
    "/assignments/{assignment_id}/area-schedules",
    response=list[CleanerAreaScheduleOut],
    summary="List assignment area schedules",
)
def cleaner_assignment_schedules(request: AuthenticatedRequest, assignment_id: int) -> list[CleanerAreaScheduleOut]:
    _assignment_read(request.auth)
    assignment = get_assignment_or_none(assignment_id)
    if assignment is None:
        raise Http404("Assignment not found.")
    if not can_view_assignment(request.auth, assignment):
        raise PermissionDenied("You do not have access to this assignment.")
    return [_schedule_out(s) for s in assignment_area_schedules(assignment_id)]


@router.post(
    "/assignments/{assignment_id}/area-schedules",
    response=CleanerAreaScheduleOut,
    summary="Schedule a cleaner for an area/task/time",
)
def cleaner_assignment_schedule_create(
    request: AuthenticatedRequest, assignment_id: int, payload: AreaScheduleCreateIn
) -> CleanerAreaScheduleOut:
    _assignment_read(request.auth)
    assignment = get_assignment_or_none(assignment_id)
    if assignment is None:
        raise Http404("Assignment not found.")
    if not can_edit_assignment(request.auth, assignment):
        raise PermissionDenied("You cannot edit this assignment.")
    site_area = SiteArea.objects.filter(pk=payload.site_area_id).first()
    if site_area is None:
        raise Http404("Area not found.")
    role = OperationalRole.objects.filter(pk=payload.operational_role_id).first()
    if role is None:
        raise Http404("Operational role not found.")
    shift = SiteShift.objects.filter(pk=payload.shift_id).first() if payload.shift_id else None
    schedule = assign_cleaner_area_schedule(
        assignment=assignment,
        site_area=site_area,
        operational_role=role,
        day=payload.date,
        start_time=payload.start_time,
        end_time=payload.end_time,
        shift=shift,
        notes=payload.notes,
        actor=request.auth,
    )
    return _schedule_out(schedule)


@router.put(
    "/assignments/{assignment_id}/area-schedules/{schedule_id}",
    response=CleanerAreaScheduleOut,
    summary="Update an area schedule",
)
def cleaner_assignment_schedule_update(
    request: AuthenticatedRequest, assignment_id: int, schedule_id: int, payload: AreaScheduleUpdateIn
) -> CleanerAreaScheduleOut:
    _assignment_read(request.auth)
    assignment = get_assignment_or_none(assignment_id)
    if assignment is None:
        raise Http404("Assignment not found.")
    if not can_edit_assignment(request.auth, assignment):
        raise PermissionDenied("You cannot edit this assignment.")
    schedule = CleanerAreaSchedule.objects.filter(pk=schedule_id, assignment_id=assignment_id).first()
    if schedule is None:
        raise Http404("Schedule not found.")
    site_area = SiteArea.objects.filter(pk=payload.site_area_id).first() if payload.site_area_id else None
    role = (
        OperationalRole.objects.filter(pk=payload.operational_role_id).first() if payload.operational_role_id else None
    )
    shift = SiteShift.objects.filter(pk=payload.shift_id).first() if payload.shift_id else None
    updated = update_area_schedule(
        schedule=schedule,
        actor=request.auth,
        site_area=site_area,
        operational_role=role,
        start_time=payload.start_time,
        end_time=payload.end_time,
        shift=shift,
        notes=payload.notes,
    )
    return _schedule_out(updated)


@router.delete(
    "/assignments/{assignment_id}/area-schedules/{schedule_id}",
    response=MessageOut,
    summary="Remove an area schedule",
)
def cleaner_assignment_schedule_delete(
    request: AuthenticatedRequest, assignment_id: int, schedule_id: int
) -> MessageOut:
    _assignment_read(request.auth)
    assignment = get_assignment_or_none(assignment_id)
    if assignment is None:
        raise Http404("Assignment not found.")
    if not can_edit_assignment(request.auth, assignment):
        raise PermissionDenied("You cannot edit this assignment.")
    schedule = CleanerAreaSchedule.objects.filter(pk=schedule_id, assignment_id=assignment_id).first()
    if schedule is None:
        raise Http404("Schedule not found.")
    deactivate_area_schedule(schedule=schedule, actor=request.auth)
    return MessageOut(detail="Schedule removed.")


@router.get(
    "/schedules",
    response=list[ScheduleRowOut],
    summary="Daily site schedule (attendance-ready)",
)
def site_schedule(
    request: AuthenticatedRequest,
    site_id: int,
    date: date,
    shift_id: int | None = None,
) -> list[ScheduleRowOut]:
    _assignment_read(request.auth)
    site = get_site_or_none(site_id)
    if site is None:
        raise Http404("Site not found.")
    if not site_in_user_scope(request.auth, site_id):
        raise PermissionDenied("You do not have access to this site.")
    rows = scheduled_cleaners_for_attendance(site_id, date, shift_id)
    return [ScheduleRowOut(**row) for row in rows]


# --------------------------------------------------------------------------- #
# Attendance
# --------------------------------------------------------------------------- #


def _attendance_read(user: User) -> None:
    if not (management_required(user) or user.is_management_viewer):
        raise PermissionDenied("Attendance requires a management role.")


def _attendance_write(user: User, site_id: int) -> None:
    _attendance_read(user)
    if not user_can_manage_site(user, site_id):
        raise PermissionDenied("You cannot manage attendance for this site.")


def _attendance_out(r: AttendanceRecord) -> AttendanceRecordOut:
    return AttendanceRecordOut(
        id=r.pk,
        cleaner_id=r.cleaner_id,
        cleaner_name=r.cleaner.full_name,
        site_id=r.site_id,
        site_name=r.site.name,
        shift_id=r.shift_id,
        shift_name=r.shift.shift_name if r.shift else None,
        attendance_date=r.attendance_date,
        status=r.status,
        check_in_time=r.check_in_time,
        check_out_time=r.check_out_time,
        notes=r.notes,
        review_status=r.review_status,
        return_reason=r.return_reason,
        submitted_at=r.submitted_at,
        is_editable=r.is_editable,
    )


@router.get(
    "/attendance/daily",
    response=list[AttendanceRecordOut],
    summary="Daily attendance sheet for a site",
)
def attendance_daily(
    request: AuthenticatedRequest,
    site_id: int,
    date: date,
    shift_id: int | None = None,
) -> list[AttendanceRecordOut]:
    _attendance_read(request.auth)
    site = get_site_or_none(site_id)
    if site is None:
        raise Http404("Site not found.")
    if not site_in_user_scope(request.auth, site_id):
        raise PermissionDenied("You do not have access to this site.")
    generate_daily_attendance_sheet(site_id=site_id, day=date, shift_id=shift_id, actor=request.auth)
    records = attendance_daily_sheet(request.auth, site_id, date, shift_id)
    return [_attendance_out(r) for r in records]


@router.post("/attendance/bulk", response=list[AttendanceRecordOut], summary="Bulk attendance entry")
def attendance_bulk(request: AuthenticatedRequest, payload: AttendanceBulkIn) -> list[AttendanceRecordOut]:
    _attendance_write(request.auth, payload.site_id)
    allow_future = request.auth.is_system_admin or request.auth.role == RoleCode.GENERAL_SUPERVISOR
    records = bulk_upsert_attendance(
        site_id=payload.site_id,
        day=payload.attendance_date,
        entries=[e.model_dump() for e in payload.entries],
        user=request.auth,
        shift_id=payload.shift_id,
        allow_future=allow_future,
    )
    return [_attendance_out(r) for r in records]


@router.post("/attendance/submit", response=AttendanceSubmitOut, summary="Submit a day's attendance")
def attendance_submit(request: AuthenticatedRequest, payload: AttendanceGroupIn) -> AttendanceSubmitOut:
    _attendance_write(request.auth, payload.site_id)
    submitted = submit_daily_attendance(
        site_id=payload.site_id, day=payload.attendance_date, user=request.auth, shift_id=payload.shift_id
    )
    return AttendanceSubmitOut(submitted=submitted)


@router.post("/attendance/return", response=dict, summary="Return attendance for correction")
def attendance_return(request: AuthenticatedRequest, payload: AttendanceReturnIn) -> dict[str, object]:
    if payload.record_id is not None:
        record = AttendanceRecord.objects.filter(pk=payload.record_id).select_related("site").first()
        if record is None:
            raise Http404("Attendance record not found.")
        _attendance_write(request.auth, record.site_id)
        returned = return_attendance_record(record=record, user=request.auth, reason=payload.reason)
        return {"returned": 1, "record_id": returned.pk}
    if payload.site_id is None or payload.attendance_date is None:
        raise PermissionDenied("Provide a record_id or a site_id + date.")
    _attendance_write(request.auth, payload.site_id)
    returned_count = return_attendance_group(
        site_id=payload.site_id,
        day=payload.attendance_date,
        user=request.auth,
        reason=payload.reason,
        shift_id=payload.shift_id,
    )
    return {"returned": returned_count}


@router.post("/attendance/review", response=dict, summary="Review a submitted day's attendance")
def attendance_review(request: AuthenticatedRequest, payload: AttendanceGroupIn) -> dict[str, object]:
    _attendance_write(request.auth, payload.site_id)
    reviewed = review_attendance_group(
        site_id=payload.site_id, day=payload.attendance_date, user=request.auth, shift_id=payload.shift_id
    )
    return {"reviewed": reviewed}


@router.get(
    "/attendance/history",
    response=Paginated[AttendanceRecordOut],
    summary="Attendance history (paginated, filtered)",
)
def attendance_history(
    request: AuthenticatedRequest,
    filters: PageParams = PAGE_PARAMS_DEFAULT,
    site_id: int | None = None,
    date: date | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    shift_id: int | None = None,
    cleaner_id: int | None = None,
    status: str | None = None,
    review_status: str | None = None,
) -> Paginated[AttendanceRecordOut]:
    _attendance_read(request.auth)
    spec = AttendanceFilter(
        site_id=site_id,
        date=date,
        date_from=date_from,
        date_to=date_to,
        shift_id=shift_id,
        cleaner_id=cleaner_id,
        status=status,
        review_status=review_status,
    )
    qs = attendance_history_queryset(request.auth, spec).order_by("-attendance_date", "site__name")
    items, count, page, page_size = paginate(qs, filters.page, filters.page_size)
    results = [_attendance_out(r) for r in items]
    return paginated_response(request, qs, page, page_size, results, count)


@router.get("/attendance/summary", response=AttendanceSummaryOut, summary="Attendance summary")
def attendance_summary_endpoint(
    request: AuthenticatedRequest,
    site_id: int | None = None,
    date: date | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    shift_id: int | None = None,
    cleaner_id: int | None = None,
) -> AttendanceSummaryOut:
    _attendance_read(request.auth)
    spec = AttendanceFilter(
        site_id=site_id, date=date, date_from=date_from, date_to=date_to, shift_id=shift_id, cleaner_id=cleaner_id
    )
    return AttendanceSummaryOut(**cast(dict[str, Any], attendance_summary(request.auth, spec)))


@router.get("/attendance/missing", response=list[dict[str, object]], summary="Sites missing attendance submission")
def attendance_missing(request: AuthenticatedRequest, date: date) -> list[dict[str, object]]:
    _attendance_read(request.auth)
    return missing_attendance_sites(request.auth, date)


@router.get("/attendance/exceptions", response=list[AttendanceRecordOut], summary="Attendance exceptions")
def attendance_exceptions_endpoint(
    request: AuthenticatedRequest,
    site_id: int | None = None,
    date: date | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    shift_id: int | None = None,
    cleaner_id: int | None = None,
) -> list[AttendanceRecordOut]:
    _attendance_read(request.auth)
    spec = AttendanceFilter(
        site_id=site_id, date=date, date_from=date_from, date_to=date_to, shift_id=shift_id, cleaner_id=cleaner_id
    )
    return [_attendance_out(r) for r in attendance_exceptions(request.auth, spec)]


@router.put("/attendance/{record_id}", response=AttendanceRecordOut, summary="Record single attendance")
def attendance_single(
    request: AuthenticatedRequest, record_id: int, payload: AttendanceSingleIn
) -> AttendanceRecordOut:
    record = AttendanceRecord.objects.filter(pk=record_id).select_related("site").first()
    if record is None:
        raise Http404("Attendance record not found.")
    _attendance_write(request.auth, record.site_id)
    updated = record_single_attendance(
        record_id=record_id,
        status=AttendanceStatus(payload.status),
        user=request.auth,
        check_in_time=payload.check_in_time,
        check_out_time=payload.check_out_time,
        notes=payload.notes,
    )
    return _attendance_out(updated)


# --------------------------------------------------------------------------- #
# Trainee lifecycle
# --------------------------------------------------------------------------- #


def _trainee_read(user: User) -> None:
    if not (management_required(user) or user.is_management_viewer):
        raise PermissionDenied("Trainee records require a management role.")


def _trainee_manage(user: User, site_id: int) -> None:
    _trainee_read(user)
    if not user_can_manage_site(user, site_id):
        raise PermissionDenied("You cannot manage trainees for this site.")


def _trainee_decide(user: User) -> None:
    if not (user.is_system_admin or user.role in {RoleCode.GENERAL_SUPERVISOR, RoleCode.ASSISTANT_GENERAL_SUPERVISOR}):
        raise PermissionDenied("Only senior management can make final trainee decisions.")


def _trainee_out(p: TraineeProgram) -> TraineeProgramOut:
    latest = p.evaluations.order_by("-evaluation_date").first()
    return TraineeProgramOut(
        id=p.pk,
        cleaner_id=p.cleaner_id,
        cleaner_name=p.cleaner.full_name,
        site_id=p.site_id,
        site_name=p.site.name,
        assigned_site_supervisor=p.assigned_site_supervisor.email if p.assigned_site_supervisor else None,
        start_date=p.start_date,
        expected_end_date=p.expected_end_date,
        actual_end_date=p.actual_end_date,
        status=p.status,
        notes=p.notes,
        evaluation_count=p.evaluations.count(),
        latest_total=latest.total_score if latest else None,
    )


def _evaluation_out(e: TraineeEvaluation) -> TraineeEvaluationOut:
    return TraineeEvaluationOut(
        id=e.pk,
        trainee_program_id=e.trainee_program_id,
        evaluation_date=e.evaluation_date,
        attendance_score=e.attendance_score,
        performance_score=e.performance_score,
        behavior_score=e.behavior_score,
        skill_score=e.skill_score,
        total_score=e.total_score or 0,
        comments=e.comments,
        is_final=e.is_final,
        evaluated_by=e.evaluated_by.email if e.evaluated_by else None,
    )


@router.get(
    "/trainees",
    response=Paginated[TraineeProgramOut],
    summary="List trainee programs (paginated, role-scoped)",
)
def trainee_list(
    request: AuthenticatedRequest,
    filters: PageParams = PAGE_PARAMS_DEFAULT,
    site_id: int | None = None,
    status: str | None = None,
    search: str | None = None,
    ordering: str | None = None,
) -> Paginated[TraineeProgramOut]:
    _trainee_read(request.auth)
    spec = TraineeFilter(site_id=site_id, status=status, search=search)
    qs = apply_ordering(
        trainee_list_queryset(request.auth, spec), ordering, ["start_date", "expected_end_date", "created_at"]
    )
    items, count, page, page_size = paginate(qs, filters.page, filters.page_size)
    results = [_trainee_out(p) for p in items]
    return paginated_response(request, qs, page, page_size, results, count)


@router.post("/trainees", response=TraineeProgramOut, summary="Start a trainee program")
def trainee_create(request: AuthenticatedRequest, payload: TraineeProgramCreateIn) -> TraineeProgramOut:
    _trainee_read(request.auth)
    cleaner = get_cleaner_or_none(payload.cleaner_id)
    if cleaner is None:
        raise Http404("Cleaner not found.")
    site = get_site_or_none(payload.site_id)
    if site is None:
        raise Http404("Site not found.")
    _trainee_manage(request.auth, site.pk)
    supervisor = (
        User.objects.filter(pk=payload.assigned_site_supervisor_id).first()
        if payload.assigned_site_supervisor_id
        else None
    )
    program = start_trainee_program(
        cleaner=cleaner,
        site=site,
        expected_end_date=payload.expected_end_date,
        start_date=payload.start_date,
        assigned_site_supervisor=supervisor,
        notes=payload.notes,
        actor=request.auth,
    )
    return _trainee_out(program)


@router.get("/trainees/summary", response=TraineeSummaryOut, summary="Trainee summary")
def trainee_summary_endpoint(
    request: AuthenticatedRequest,
    site_id: int | None = None,
    status: str | None = None,
) -> TraineeSummaryOut:
    _trainee_read(request.auth)
    return TraineeSummaryOut(**trainee_summary(request.auth, TraineeFilter(site_id=site_id, status=status)))


@router.get("/trainees/{program_id}", response=TraineeProgramOut, summary="Trainee program detail")
def trainee_detail(request: AuthenticatedRequest, program_id: int) -> TraineeProgramOut:
    _trainee_read(request.auth)
    program = get_trainee_program_or_none(program_id)
    if program is None:
        raise Http404("Trainee program not found.")
    if not site_in_user_scope(request.auth, program.site_id):
        raise PermissionDenied("You do not have access to this trainee program.")
    return _trainee_out(program)


@router.put("/trainees/{program_id}", response=TraineeProgramOut, summary="Update a trainee program")
def trainee_update(
    request: AuthenticatedRequest, program_id: int, payload: TraineeProgramUpdateIn
) -> TraineeProgramOut:
    _trainee_read(request.auth)
    program = get_trainee_program_or_none(program_id)
    if program is None:
        raise Http404("Trainee program not found.")
    _trainee_manage(request.auth, program.site_id)
    supervisor = (
        User.objects.filter(pk=payload.assigned_site_supervisor_id).first()
        if payload.assigned_site_supervisor_id
        else None
    )
    updated = update_trainee_program(
        program=program, actor=request.auth, assigned_site_supervisor=supervisor, notes=payload.notes
    )
    return _trainee_out(updated)


@router.get(
    "/trainees/{program_id}/evaluations",
    response=list[TraineeEvaluationOut],
    summary="List trainee evaluations",
)
def trainee_evaluations_list(request: AuthenticatedRequest, program_id: int) -> list[TraineeEvaluationOut]:
    _trainee_read(request.auth)
    program = get_trainee_program_or_none(program_id)
    if program is None:
        raise Http404("Trainee program not found.")
    if not site_in_user_scope(request.auth, program.site_id):
        raise PermissionDenied("You do not have access to this trainee program.")
    return [_evaluation_out(e) for e in trainee_evaluations(program_id)]


@router.post(
    "/trainees/{program_id}/evaluations",
    response=TraineeEvaluationOut,
    summary="Record a trainee evaluation",
)
def trainee_evaluation_create(
    request: AuthenticatedRequest, program_id: int, payload: TraineeEvaluationCreateIn
) -> TraineeEvaluationOut:
    _trainee_read(request.auth)
    program = get_trainee_program_or_none(program_id)
    if program is None:
        raise Http404("Trainee program not found.")
    _trainee_manage(request.auth, program.site_id)
    evaluation = record_trainee_evaluation(
        program=program,
        evaluation_date=payload.evaluation_date,
        actor=request.auth,
        attendance_score=payload.attendance_score,
        performance_score=payload.performance_score,
        behavior_score=payload.behavior_score,
        skill_score=payload.skill_score,
        total_score=payload.total_score,
        comments=payload.comments,
        is_final=payload.is_final,
    )
    return _evaluation_out(evaluation)


@router.post(
    "/trainees/{program_id}/extend",
    response=TraineeProgramOut,
    summary="Extend a trainee program",
)
def trainee_extend(request: AuthenticatedRequest, program_id: int, payload: TraineeExtendIn) -> TraineeProgramOut:
    _trainee_read(request.auth)
    program = get_trainee_program_or_none(program_id)
    if program is None:
        raise Http404("Trainee program not found.")
    _trainee_manage(request.auth, program.site_id)
    updated = extend_trainee_program(
        program=program, new_expected_end_date=payload.new_expected_end_date, reason=payload.reason, actor=request.auth
    )
    return _trainee_out(updated)


@router.post(
    "/trainees/{program_id}/pass",
    response=TraineeProgramOut,
    summary="Pass a trainee (converts to ACTIVE cleaner)",
)
def trainee_pass(request: AuthenticatedRequest, program_id: int, payload: TraineeDecisionIn) -> TraineeProgramOut:
    _trainee_read(request.auth)
    program = get_trainee_program_or_none(program_id)
    if program is None:
        raise Http404("Trainee program not found.")
    _trainee_decide(request.auth)
    updated = pass_trainee(
        program=program, actor=request.auth, actual_end_date=payload.actual_end_date, reason=payload.reason
    )
    return _trainee_out(updated)


@router.post(
    "/trainees/{program_id}/fail",
    response=TraineeProgramOut,
    summary="Fail a trainee",
)
def trainee_fail(request: AuthenticatedRequest, program_id: int, payload: TraineeDecisionIn) -> TraineeProgramOut:
    _trainee_read(request.auth)
    program = get_trainee_program_or_none(program_id)
    if program is None:
        raise Http404("Trainee program not found.")
    _trainee_decide(request.auth)
    updated = fail_trainee(program=program, actor=request.auth, reason=payload.reason)
    return _trainee_out(updated)


@router.post(
    "/trainees/{program_id}/drop",
    response=TraineeProgramOut,
    summary="Drop a trainee",
)
def trainee_drop(request: AuthenticatedRequest, program_id: int, payload: TraineeDecisionIn) -> TraineeProgramOut:
    _trainee_read(request.auth)
    program = get_trainee_program_or_none(program_id)
    if program is None:
        raise Http404("Trainee program not found.")
    _trainee_decide(request.auth)
    updated = drop_trainee(program=program, actor=request.auth, reason=payload.reason)
    return _trainee_out(updated)


# --------------------------------------------------------------------------- #
# Site store & stock requests
# --------------------------------------------------------------------------- #


def _store_read(user: User, store_id: int) -> None:
    if not (management_required(user) or user.is_management_viewer):
        raise PermissionDenied("Store records require a management role.")
    if not user.is_system_admin and not site_in_user_scope(user, getattr(_load_store_or_404(store_id), "site_id", 0)):
        raise PermissionDenied("You do not have access to this store.")


def _store_manage(user: User, store_id: int) -> None:
    _store_read(user, store_id)
    store = _load_store_or_404(store_id)
    if not user_can_manage_site(user, store.site_id):
        raise PermissionDenied("You do not have permission to manage this store.")


def _store_review(user: User) -> None:
    if not (
        user.is_system_admin
        or user.role
        in {
            RoleCode.GENERAL_SUPERVISOR,
            RoleCode.ASSISTANT_GENERAL_SUPERVISOR,
            RoleCode.ZONE_SUPERVISOR,
        }
    ):
        raise PermissionDenied("Only zone-level management can review stock requests.")


def _load_store_or_404(store_id: int) -> SiteStore:
    store = SiteStore.objects.filter(pk=store_id).first()
    if store is None:
        raise Http404("Store not found.")
    return store


def _store_out(store: SiteStore) -> StoreOut:
    annotated = getattr(store, "annotated_item_count", None)
    managed_by = store.managed_by
    return StoreOut(
        id=store.pk,
        site_id=store.site_id,
        site_name=store.site.name,
        store_name=store.store_name,
        location=store.location,
        managed_by=managed_by.email if managed_by else None,
        managed_by_id=store.managed_by_id,
        is_active=store.is_active,
        item_count=annotated if annotated is not None else store.item_count,
        low_stock_count=store.low_stock_count,
        created_at=store.created_at,
    )


def _store_item_out(item: StoreItem) -> StoreItemOut:
    return StoreItemOut(
        id=item.pk,
        store_id=item.store_id,
        item_name=item.item_name,
        item_code=item.item_code,
        unit=item.unit,
        category=item.category,
        opening_stock=item.opening_stock,
        current_stock=item.current_stock,
        minimum_stock_level=item.minimum_stock_level,
        low_stock=item.low_stock,
        is_active=item.is_active,
        created_at=item.created_at,
    )


def _movement_out(m: StockMovement) -> StockMovementOut:
    cleaner = m.cleaner
    area = m.area
    recorded_by = m.recorded_by
    return StockMovementOut(
        id=m.pk,
        store_id=m.store_item.store_id,
        store_name=m.store_item.store.store_name,
        store_item_id=m.store_item_id,
        item_name=m.store_item.item_name,
        movement_type=m.movement_type,
        quantity=m.quantity,
        movement_date=m.movement_date,
        cleaner_id=m.cleaner_id,
        cleaner_name=cleaner.full_name if cleaner else None,
        area_id=m.area_id,
        area_name=area.area_name if area else None,
        notes=m.notes,
        recorded_by=recorded_by.email if recorded_by else None,
        created_at=m.created_at,
    )


def _request_out(r: StockRequest) -> StockRequestOut:
    requested_by = r.requested_by
    reviewed_by = r.reviewed_by
    items = [
        StockRequestItemOut(
            id=item.pk,
            store_item_id=item.store_item_id,
            item_name=item.store_item.item_name,
            requested_quantity=item.requested_quantity,
            approved_quantity=item.approved_quantity,
            notes=item.notes,
        )
        for item in r.items.all()
    ]
    return StockRequestOut(
        id=r.pk,
        site_id=r.site_id,
        site_name=r.site.name,
        store_id=r.store_id,
        store_name=r.store.store_name,
        request_date=r.request_date,
        requested_by=requested_by.email if requested_by else None,
        status=r.status,
        notes=r.notes,
        reviewed_by=reviewed_by.email if reviewed_by else None,
        reviewed_at=r.reviewed_at,
        items=items,
        created_at=r.created_at,
    )


def _load_request_or_404(store_id: int, request_id: int) -> StockRequest:
    request = stock_request_or_none(request_id)
    if request is None or request.store_id != store_id:
        raise Http404("Stock request not found.")
    return request


@router.get(
    "/stores",
    response=Paginated[StoreOut],
    summary="List stores (paginated, role-scoped)",
)
def store_list_endpoint(
    request: AuthenticatedRequest,
    filters: PageParams = PAGE_PARAMS_DEFAULT,
    site_id: int | None = None,
    search: str | None = None,
    ordering: str | None = None,
) -> Paginated[StoreOut]:
    if not (management_required(request.auth) or request.auth.is_management_viewer):
        raise PermissionDenied("Store records require a management role.")
    qs = apply_ordering(
        store_list(request.auth, StoreFilter(site_id=site_id, search=search)), ordering, ["store_name", "created_at"]
    )
    items, count, page, page_size = paginate(qs, filters.page, filters.page_size)
    results = [_store_out(s) for s in items]
    return paginated_response(request, qs, page, page_size, results, count)


@router.get(
    "/stores/low-stock",
    response=list[StoreItemOut],
    summary="List low-stock items (role-scoped)",
)
def store_low_stock_endpoint(
    request: AuthenticatedRequest,
    site_id: int | None = None,
) -> list[StoreItemOut]:
    if not (management_required(request.auth) or request.auth.is_management_viewer):
        raise PermissionDenied("Store records require a management role.")
    return [_store_item_out(item) for item in low_stock_items(request.auth, site_id)]


@router.post("/stores", response=StoreOut, summary="Create a store")
def store_create(request: AuthenticatedRequest, payload: StoreCreateIn) -> StoreOut:
    site = _load_site_or_404(payload.site_id)
    if not user_can_manage_site(request.auth, site.pk):
        raise PermissionDenied("You do not have permission to create a store for this site.")
    managed_by = User.objects.filter(pk=payload.managed_by_id).first() if payload.managed_by_id else None
    return _store_out(
        create_store(
            site=site,
            store_name=payload.store_name,
            actor=request.auth,
            location=payload.location,
            managed_by=managed_by,
        )
    )


@router.get("/stores/{store_id}", response=StoreOut, summary="Store detail")
def store_detail_endpoint(request: AuthenticatedRequest, store_id: int) -> StoreOut:
    _store_read(request.auth, store_id)
    store = _load_store_or_404(store_id)
    return _store_out(store)


@router.get("/stores/{store_id}/items", response=list[StoreItemOut], summary="Store items")
def store_items_endpoint(request: AuthenticatedRequest, store_id: int) -> list[StoreItemOut]:
    _store_read(request.auth, store_id)
    return [_store_item_out(item) for item in stock_items(request.auth, store_id)]


@router.post("/stores/{store_id}/items", response=StoreItemOut, summary="Add a store item")
def store_item_create(request: AuthenticatedRequest, store_id: int, payload: StoreItemCreateIn) -> StoreItemOut:
    _store_manage(request.auth, store_id)
    store = _load_store_or_404(store_id)
    return _store_item_out(
        add_store_item(
            store=store,
            item_name=payload.item_name,
            actor=request.auth,
            item_code=payload.item_code,
            unit=payload.unit,
            category=payload.category,
            opening_stock=payload.opening_stock,
            minimum_stock_level=payload.minimum_stock_level,
        )
    )


@router.put(
    "/stores/{store_id}/items/{item_id}",
    response=StoreItemOut,
    summary="Update a store item",
)
def store_item_update(
    request: AuthenticatedRequest, store_id: int, item_id: int, payload: StoreItemUpdateIn
) -> StoreItemOut:
    _store_manage(request.auth, store_id)
    item = StoreItem.objects.filter(pk=item_id, store_id=store_id).first()
    if item is None:
        raise Http404("Store item not found.")
    return _store_item_out(
        update_store_item(
            item=item,
            actor=request.auth,
            item_name=payload.item_name,
            item_code=payload.item_code,
            unit=payload.unit,
            category=payload.category,
            minimum_stock_level=payload.minimum_stock_level,
            is_active=payload.is_active,
        )
    )


@router.get(
    "/stores/{store_id}/movements",
    response=Paginated[StockMovementOut],
    summary="List stock movements (paginated, filtered)",
)
def store_movements_endpoint(
    request: AuthenticatedRequest,
    store_id: int,
    filters: PageParams = PAGE_PARAMS_DEFAULT,
    store_item_id: int | None = None,
    movement_type: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> Paginated[StockMovementOut]:
    _store_read(request.auth, store_id)
    spec = StockMovementFilter(
        store_id=store_id,
        store_item_id=store_item_id,
        movement_type=movement_type,
        date_from=date_from,
        date_to=date_to,
    )
    qs = stock_movements(request.auth, spec)
    items, count, page, page_size = paginate(qs, filters.page, filters.page_size)
    results = [_movement_out(m) for m in items]
    return paginated_response(request, qs, page, page_size, results, count)


@router.post(
    "/stores/{store_id}/movements",
    response=StockMovementOut,
    summary="Record a stock movement",
)
def store_movement_create(
    request: AuthenticatedRequest, store_id: int, payload: StockMovementCreateIn
) -> StockMovementOut:
    _store_manage(request.auth, store_id)
    item = StoreItem.objects.filter(pk=payload.store_item_id, store_id=store_id).first()
    if item is None:
        raise Http404("Store item not found.")
    cleaner = Cleaner.objects.filter(pk=payload.cleaner_id).first() if payload.cleaner_id else None
    area = SiteArea.objects.filter(pk=payload.area_id).first() if payload.area_id else None
    if payload.movement_type in {StockMovementType.DAMAGED, StockMovementType.LOST}:
        movement = record_damage_loss(
            store_item=item,
            movement_type=payload.movement_type,
            quantity=payload.quantity,
            actor=request.auth,
            reason=payload.reason,
            movement_date=payload.movement_date,
            notes=payload.notes,
        )
    elif payload.movement_type == StockMovementType.ADJUSTMENT:
        movement = adjust_stock(
            store_item=item,
            signed_quantity=payload.quantity,
            actor=request.auth,
            reason=payload.reason,
            movement_date=payload.movement_date,
        )
    else:
        movement = record_stock_movement(
            store_item=item,
            movement_type=payload.movement_type,
            quantity=payload.quantity,
            actor=request.auth,
            movement_date=payload.movement_date,
            cleaner=cleaner,
            area=area,
            notes=payload.notes,
        )
    return _movement_out(movement)


@router.get(
    "/stores/{store_id}/requests",
    response=Paginated[StockRequestOut],
    summary="List stock requests (paginated, filtered)",
)
def store_requests_endpoint(
    request: AuthenticatedRequest,
    store_id: int,
    filters: PageParams = PAGE_PARAMS_DEFAULT,
    status: str | None = None,
    request_date: date | None = None,
) -> Paginated[StockRequestOut]:
    _store_read(request.auth, store_id)
    spec = StockRequestFilter(store_id=store_id, status=status, request_date=request_date)
    qs = stock_requests(request.auth, spec)
    items, count, page, page_size = paginate(qs, filters.page, filters.page_size)
    results = [_request_out(r) for r in items]
    return paginated_response(request, qs, page, page_size, results, count)


@router.post(
    "/stores/{store_id}/requests",
    response=StockRequestOut,
    summary="Create a stock request (draft)",
)
def store_request_create(
    request: AuthenticatedRequest, store_id: int, payload: StockRequestCreateIn
) -> StockRequestOut:
    _store_manage(request.auth, store_id)
    store = _load_store_or_404(store_id)
    items = [
        {"store_item_id": row.store_item_id, "requested_quantity": row.requested_quantity, "notes": row.notes}
        for row in payload.items
    ]
    created = create_stock_request(
        site=store.site,
        store=store,
        actor=request.auth,
        items=items,
        request_date=payload.request_date,
        notes=payload.notes,
    )
    return _request_out(stock_request_or_none(created.pk) or created)


@router.post(
    "/stores/{store_id}/requests/{request_id}/submit",
    response=StockRequestOut,
    summary="Submit a draft stock request",
)
def store_request_submit(request: AuthenticatedRequest, store_id: int, request_id: int) -> StockRequestOut:
    _store_manage(request.auth, store_id)
    stock_request = _load_request_or_404(store_id, request_id)
    submit_stock_request(request=stock_request, actor=request.auth)
    return _request_out(stock_request_or_none(stock_request.pk) or stock_request)


@router.post(
    "/stores/{store_id}/requests/{request_id}/review",
    response=StockRequestOut,
    summary="Review a submitted stock request (zone)",
)
def store_request_review(
    request: AuthenticatedRequest, store_id: int, request_id: int, payload: StockRequestReviewIn
) -> StockRequestOut:
    _store_review(request.auth)
    stock_request = _load_request_or_404(store_id, request_id)
    approved = [{"item_id": row.item_id, "approved_quantity": row.approved_quantity} for row in payload.approved]
    review_stock_request(request=stock_request, actor=request.auth, approved=approved, notes=payload.notes)
    return _request_out(stock_request_or_none(stock_request.pk) or stock_request)


@router.post(
    "/stores/{store_id}/requests/{request_id}/reject",
    response=StockRequestOut,
    summary="Reject a stock request",
)
def store_request_reject(
    request: AuthenticatedRequest, store_id: int, request_id: int, payload: StockRequestDecisionIn
) -> StockRequestOut:
    _store_review(request.auth)
    stock_request = _load_request_or_404(store_id, request_id)
    reject_stock_request(request=stock_request, actor=request.auth, reason=payload.reason)
    return _request_out(stock_request_or_none(stock_request.pk) or stock_request)


@router.post(
    "/stores/{store_id}/requests/{request_id}/complete",
    response=StockRequestOut,
    summary="Complete a reviewed stock request (issues approved stock)",
)
def store_request_complete(request: AuthenticatedRequest, store_id: int, request_id: int) -> StockRequestOut:
    _store_review(request.auth)
    stock_request = _load_request_or_404(store_id, request_id)
    complete_stock_request(request=stock_request, actor=request.auth)
    return _request_out(stock_request_or_none(stock_request.pk) or stock_request)


# --------------------------------------------------------------------------- #
# Inspections
# --------------------------------------------------------------------------- #


def _inspection_read(user: User) -> None:
    if not (management_required(user) or user.is_management_viewer):
        raise PermissionDenied("Inspection records require a management role.")


def _inspection_manage(user: User, site_id: int) -> None:
    _inspection_read(user)
    if not user_can_manage_site(user, site_id):
        raise PermissionDenied("You do not have permission to manage inspections for this site.")


def _inspection_review(user: User) -> None:
    if not (
        user.is_system_admin
        or user.role
        in {
            RoleCode.GENERAL_SUPERVISOR,
            RoleCode.ASSISTANT_GENERAL_SUPERVISOR,
            RoleCode.ZONE_SUPERVISOR,
        }
    ):
        raise PermissionDenied("Only zone-level management can review inspections.")


def _load_template_or_404(template_id: int) -> InspectionTemplate:
    template = get_template_or_none(template_id)
    if template is None:
        raise Http404("Inspection template not found.")
    return template


def _load_inspection_or_404(inspection_id: int) -> Inspection:
    inspection = get_inspection_or_none(inspection_id)
    if inspection is None:
        raise Http404("Inspection not found.")
    return inspection


def _template_out(template: InspectionTemplate) -> InspectionTemplateOut:
    annotated = getattr(template, "annotated_item_count", None)
    site = template.site
    area = template.area
    return InspectionTemplateOut(
        id=template.pk,
        template_name=template.template_name,
        description=template.description,
        site_id=template.site_id,
        site_name=site.name if site else None,
        area_id=template.area_id,
        area_name=area.area_name if area else None,
        frequency=template.frequency,
        is_active=template.is_active,
        item_count=annotated if annotated is not None else template.item_count,
        items=[_template_item_out(item) for item in template.items.all()],
        created_at=template.created_at,
    )


def _template_item_out(item: InspectionTemplateItem) -> TemplateItemOut:
    return TemplateItemOut(
        id=item.pk,
        item_label=item.item_label,
        item_type=item.item_type,
        required=item.required,
        sequence=item.sequence,
        help_text=item.help_text,
    )


def _result_out(r: InspectionResult) -> InspectionResultOut:
    return InspectionResultOut(
        id=r.pk,
        inspection_id=r.inspection_id,
        template_item_id=r.template_item_id,
        item_label=r.template_item.item_label,
        item_type=r.template_item.item_type,
        required=r.template_item.required,
        value_text=r.value_text,
        value_number=r.value_number,
        value_boolean=r.value_boolean,
        passed=r.passed,
        notes=r.notes,
        has_photo=bool(r.file),
    )


def _inspection_out(inspection: Inspection) -> InspectionOut:
    results = [_result_out(r) for r in inspection.results.all()]
    inspected_by = inspection.inspected_by
    shift = inspection.shift
    return InspectionOut(
        id=inspection.pk,
        site_id=inspection.site_id,
        site_name=inspection.site.name,
        area_id=inspection.area_id,
        area_name=inspection.area.area_name,
        template_id=inspection.template_id,
        template_name=inspection.template.template_name,
        inspection_date=inspection.inspection_date,
        shift_id=inspection.shift_id,
        shift_name=shift.shift_name if shift else None,
        inspected_by=inspected_by.email if inspected_by else None,
        overall_status=inspection.overall_status,
        score=inspection.score,
        notes=inspection.notes,
        status=inspection.status,
        submitted_at=inspection.submitted_at,
        results=results,
        created_at=inspection.created_at,
    )


@router.get(
    "/inspection-templates",
    response=Paginated[InspectionTemplateOut],
    summary="List inspection templates (paginated, role-scoped)",
)
def inspection_template_list(
    request: AuthenticatedRequest,
    filters: PageParams = PAGE_PARAMS_DEFAULT,
    site_id: int | None = None,
    frequency: str | None = None,
    search: str | None = None,
    is_active: bool | None = None,
) -> Paginated[InspectionTemplateOut]:
    _inspection_read(request.auth)
    spec = TemplateFilter(site_id=site_id, frequency=frequency, search=search, is_active=is_active)
    qs = template_list(request.auth, spec)
    items, count, page, page_size = paginate(qs, filters.page, filters.page_size)
    results = [_template_out(t) for t in items]
    return paginated_response(request, qs, page, page_size, results, count)


@router.post(
    "/inspection-templates",
    response=InspectionTemplateOut,
    summary="Create an inspection template",
)
def inspection_template_create(
    request: AuthenticatedRequest, payload: InspectionTemplateCreateIn
) -> InspectionTemplateOut:
    _inspection_read(request.auth)
    site = None
    if payload.site_id:
        site = _load_site_or_404(payload.site_id)
        _inspection_manage(request.auth, site.pk)
    area = SiteArea.objects.filter(pk=payload.area_id).first() if payload.area_id else None
    items = [_item_payload(row) for row in payload.items]
    created = create_template(
        template_name=payload.template_name,
        actor=request.auth,
        description=payload.description,
        site=site,
        area=area,
        frequency=payload.frequency,
        items=items,
    )
    return _template_out(get_template_or_none(created.pk) or created)


def _item_payload(row: TemplateItemIn) -> dict[str, Any]:
    return {
        "item_label": row.item_label,
        "item_type": row.item_type,
        "required": row.required,
        "sequence": row.sequence,
        "help_text": row.help_text,
    }


@router.get(
    "/inspection-templates/{template_id}",
    response=InspectionTemplateOut,
    summary="Inspection template detail",
)
def inspection_template_detail(request: AuthenticatedRequest, template_id: int) -> InspectionTemplateOut:
    _inspection_read(request.auth)
    template = _load_template_or_404(template_id)
    return _template_out(template)


@router.put(
    "/inspection-templates/{template_id}",
    response=InspectionTemplateOut,
    summary="Update an inspection template",
)
def inspection_template_update(
    request: AuthenticatedRequest, template_id: int, payload: InspectionTemplateUpdateIn
) -> InspectionTemplateOut:
    _inspection_read(request.auth)
    template = _load_template_or_404(template_id)
    if template.site_id and not user_can_manage_site(request.auth, template.site_id):
        raise PermissionDenied("You do not have permission to edit this template.")
    items = [_item_payload(row) for row in payload.items] if payload.items is not None else None
    updated = update_template(
        template=template,
        actor=request.auth,
        template_name=payload.template_name,
        description=payload.description,
        frequency=payload.frequency,
        items=items,
    )
    return _template_out(get_template_or_none(updated.pk) or updated)


@router.patch(
    "/inspection-templates/{template_id}/status",
    response=InspectionTemplateOut,
    summary="Activate or deactivate an inspection template",
)
def inspection_template_status(
    request: AuthenticatedRequest, template_id: int, payload: InspectionTemplateStatusIn
) -> InspectionTemplateOut:
    _inspection_read(request.auth)
    template = _load_template_or_404(template_id)
    if template.site_id and not user_can_manage_site(request.auth, template.site_id):
        raise PermissionDenied("You do not have permission to change this template.")
    if payload.is_active:
        template.is_active = True
        template.updated_by = request.auth
        template.save(update_fields=["is_active", "updated_by", "updated_at"])
    else:
        deactivate_template(template=template, actor=request.auth)
    return _template_out(get_template_or_none(template.pk) or template)


@router.get(
    "/inspections",
    response=Paginated[InspectionOut],
    summary="List inspections (paginated, filtered)",
)
def inspection_list_endpoint(
    request: AuthenticatedRequest,
    filters: PageParams = PAGE_PARAMS_DEFAULT,
    site_id: int | None = None,
    area_id: int | None = None,
    template_id: int | None = None,
    status: str | None = None,
    overall_status: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    ordering: str | None = None,
) -> Paginated[InspectionOut]:
    _inspection_read(request.auth)
    spec = InspectionFilter(
        site_id=site_id,
        area_id=area_id,
        template_id=template_id,
        status=status,
        overall_status=overall_status,
        date_from=date_from,
        date_to=date_to,
    )
    qs = apply_ordering(inspection_list(request.auth, spec), ordering, ["inspection_date", "created_at"])
    items, count, page, page_size = paginate(qs, filters.page, filters.page_size)
    results = [_inspection_out(i) for i in items]
    return paginated_response(request, qs, page, page_size, results, count)


@router.get(
    "/inspections/summary",
    response=InspectionSummaryOut,
    summary="Inspection summary counts",
)
def inspection_summary_endpoint(
    request: AuthenticatedRequest,
    site_id: int | None = None,
) -> InspectionSummaryOut:
    _inspection_read(request.auth)
    return InspectionSummaryOut(**inspection_summary(request.auth, site_id))


@router.post("/inspections", response=InspectionOut, summary="Start an inspection")
def inspection_start(request: AuthenticatedRequest, payload: InspectionStartIn) -> InspectionOut:
    site = _load_site_or_404(payload.site_id)
    _inspection_manage(request.auth, site.pk)
    area = SiteArea.objects.filter(pk=payload.area_id).first()
    if area is None or area.site_id != site.pk:
        raise Http404("Area not found.")
    template = _load_template_or_404(payload.template_id)
    if template.site_id and template.site_id != site.pk:
        raise PermissionDenied("Template is not scoped to this site.")
    shift = SiteShift.objects.filter(pk=payload.shift_id, site_id=site.pk).first() if payload.shift_id else None
    inspected_by: User = request.auth
    if payload.inspected_by_id:
        found = User.objects.filter(pk=payload.inspected_by_id).first()
        if found is None:
            raise Http404("Inspector not found.")
        inspected_by = found
    created = start_inspection(
        site=site,
        area=area,
        template=template,
        inspected_by=inspected_by,
        actor=request.auth,
        inspection_date=payload.inspection_date,
        shift=shift,
        notes=payload.notes,
    )
    return _inspection_out(get_inspection_or_none(created.pk) or created)


@router.get("/inspections/{inspection_id}", response=InspectionOut, summary="Inspection detail")
def inspection_detail_endpoint(request: AuthenticatedRequest, inspection_id: int) -> InspectionOut:
    _inspection_read(request.auth)
    inspection = _load_inspection_or_404(inspection_id)
    if not site_in_user_scope(request.auth, inspection.site_id):
        raise PermissionDenied("You do not have access to this inspection.")
    return _inspection_out(inspection)


@router.put("/inspections/{inspection_id}", response=InspectionOut, summary="Save an inspection draft")
def inspection_update(request: AuthenticatedRequest, inspection_id: int, payload: InspectionUpdateIn) -> InspectionOut:
    inspection = _load_inspection_or_404(inspection_id)
    _inspection_manage(request.auth, inspection.site_id)
    saved = save_inspection_draft(inspection=inspection, actor=request.auth, notes=payload.notes)
    return _inspection_out(get_inspection_or_none(saved.pk) or saved)


@router.post(
    "/inspections/{inspection_id}/submit",
    response=InspectionOut,
    summary="Submit an inspection",
)
def inspection_submit(request: AuthenticatedRequest, inspection_id: int) -> InspectionOut:
    inspection = _load_inspection_or_404(inspection_id)
    _inspection_manage(request.auth, inspection.site_id)
    submitted = submit_inspection(inspection=inspection, actor=request.auth)
    return _inspection_out(get_inspection_or_none(submitted.pk) or submitted)


@router.post(
    "/inspections/{inspection_id}/return",
    response=InspectionOut,
    summary="Return an inspection for correction",
)
def inspection_return(request: AuthenticatedRequest, inspection_id: int, payload: InspectionReturnIn) -> InspectionOut:
    inspection = _load_inspection_or_404(inspection_id)
    _inspection_review(request.auth)
    returned = return_inspection(inspection=inspection, actor=request.auth, reason=payload.reason)
    return _inspection_out(get_inspection_or_none(returned.pk) or returned)


@router.post(
    "/inspections/{inspection_id}/review",
    response=InspectionOut,
    summary="Review a submitted inspection",
)
def inspection_review(request: AuthenticatedRequest, inspection_id: int) -> InspectionOut:
    inspection = _load_inspection_or_404(inspection_id)
    _inspection_review(request.auth)
    reviewed = review_inspection(inspection=inspection, actor=request.auth)
    return _inspection_out(get_inspection_or_none(reviewed.pk) or reviewed)


@router.post(
    "/inspections/{inspection_id}/results",
    response=InspectionResultOut,
    summary="Add an inspection result",
)
def inspection_result_create(
    request: AuthenticatedRequest, inspection_id: int, payload: InspectionResultCreateIn
) -> InspectionResultOut:
    inspection = _load_inspection_or_404(inspection_id)
    _inspection_manage(request.auth, inspection.site_id)
    template_item = InspectionTemplateItem.objects.filter(
        pk=payload.template_item_id, template_id=inspection.template_id
    ).first()
    if template_item is None:
        raise Http404("Template item not found.")
    result = add_inspection_result(
        inspection=inspection,
        template_item=template_item,
        actor=request.auth,
        value_text=payload.value_text,
        value_number=payload.value_number,
        value_boolean=payload.value_boolean,
        passed=payload.passed,
        notes=payload.notes,
    )
    return _result_out(result)


@router.put(
    "/inspections/{inspection_id}/results/{result_id}",
    response=InspectionResultOut,
    summary="Update an inspection result",
)
def inspection_result_update(
    request: AuthenticatedRequest, inspection_id: int, result_id: int, payload: InspectionResultUpdateIn
) -> InspectionResultOut:
    inspection = _load_inspection_or_404(inspection_id)
    _inspection_manage(request.auth, inspection.site_id)
    result = InspectionResult.objects.filter(pk=result_id, inspection_id=inspection_id).first()
    if result is None:
        raise Http404("Inspection result not found.")
    updated = update_inspection_result(
        result=result,
        actor=request.auth,
        value_text=payload.value_text,
        value_number=payload.value_number,
        value_boolean=payload.value_boolean,
        passed=payload.passed,
        notes=payload.notes,
    )
    return _result_out(updated)


@router.post(
    "/inspections/{inspection_id}/results/{result_id}/photo",
    response=InspectionResultOut,
    summary="Upload a private photo for a PHOTO result",
)
def inspection_result_photo(
    request: AuthenticatedRequest,
    inspection_id: int,
    result_id: int,
    file: UploadedFile = FILE_PARAM_DEFAULT,
) -> InspectionResultOut:
    inspection = _load_inspection_or_404(inspection_id)
    _inspection_manage(request.auth, inspection.site_id)
    result = InspectionResult.objects.filter(pk=result_id, inspection_id=inspection_id).first()
    if result is None:
        raise Http404("Inspection result not found.")
    updated = upload_result_photo(result=result, uploaded_file=file, actor=request.auth)
    return _result_out(updated)


@router.get(
    "/inspections/{inspection_id}/results/{result_id}/download-url",
    response=DownloadUrlOut,
    summary="Signed download URL for a private inspection photo",
)
def inspection_result_download_url(request: AuthenticatedRequest, inspection_id: int, result_id: int) -> DownloadUrlOut:
    _inspection_read(request.auth)
    inspection = _load_inspection_or_404(inspection_id)
    if not site_in_user_scope(request.auth, inspection.site_id):
        raise PermissionDenied("You do not have access to this inspection.")
    result = InspectionResult.objects.filter(pk=result_id, inspection_id=inspection_id).first()
    if result is None:
        raise Http404("Inspection result not found.")
    if not result.file:
        raise Http404("This result has no photo.")
    token = create_file_token(
        user_id=request.auth.pk,
        app_label="site_management",
        model_name="inspectionresult",
        object_id=result.pk,
    )
    return DownloadUrlOut(download_url=f"/{settings.API_V1_PREFIX}/files/signed/{token}/")


# --------------------------------------------------------------------------- #
# Issues & jobs
# --------------------------------------------------------------------------- #


def _issues_read(user: User) -> None:
    if not (management_required(user) or user.is_management_viewer):
        raise PermissionDenied("Issue records require a management role.")


def _issues_manage(user: User, site_id: int) -> None:
    _issues_read(user)
    if not user_can_manage_site(user, site_id):
        raise PermissionDenied("You do not have permission to manage issues for this site.")


def _issues_review(user: User) -> None:
    if not (
        user.is_system_admin
        or user.role
        in {
            RoleCode.GENERAL_SUPERVISOR,
            RoleCode.ASSISTANT_GENERAL_SUPERVISOR,
            RoleCode.ZONE_SUPERVISOR,
        }
    ):
        raise PermissionDenied("Only zone-level management can review issues.")


def _issues_escalate(user: User) -> None:
    if not (user.is_system_admin or user.role in {RoleCode.GENERAL_SUPERVISOR, RoleCode.ASSISTANT_GENERAL_SUPERVISOR}):
        raise PermissionDenied("Only senior management can escalate issues.")


def _issues_assign(user: User, site_id: int) -> None:
    _issues_read(user)
    if not user.has_perm("accounts.assign_job"):
        raise PermissionDenied("You do not have permission to assign jobs.")
    if not user_can_manage_site(user, site_id):
        raise PermissionDenied("You do not have permission to assign jobs at this site.")


def _issues_verify(user: User, site_id: int) -> None:
    _issues_read(user)
    if not user.has_perm("accounts.verify_job"):
        raise PermissionDenied("You do not have permission to verify jobs.")
    if not user_can_manage_site(user, site_id):
        raise PermissionDenied("You do not have permission to verify jobs at this site.")


def _load_issue_or_404(issue_id: int) -> Issue:
    issue = get_issue_or_none(issue_id)
    if issue is None:
        raise Http404("Issue not found.")
    return issue


def _load_job_or_404(job_id: int) -> Job:
    job = get_job_or_none(job_id)
    if job is None:
        raise Http404("Job not found.")
    return job


def _issue_out(issue: Issue) -> IssueOut:
    area = issue.area
    cleaner = issue.cleaner
    raised_by = issue.raised_by
    assigned_to = issue.assigned_to
    return IssueOut(
        id=issue.pk,
        title=issue.title,
        description=issue.description,
        source=issue.source,
        site_id=issue.site_id,
        site_name=issue.site.name,
        area_id=issue.area_id,
        area_name=area.area_name if area else None,
        cleaner_id=issue.cleaner_id,
        cleaner_name=cleaner.full_name if cleaner else None,
        inspection_id=issue.inspection_id,
        issue_category=issue.issue_category,
        priority=issue.priority,
        status=issue.status,
        raised_by=raised_by.email if raised_by else None,
        assigned_to=assigned_to.email if assigned_to else None,
        assigned_to_id=issue.assigned_to_id,
        due_date=issue.due_date,
        resolved_at=issue.resolved_at,
        closed_at=issue.closed_at,
        escalation_level=issue.escalation_level,
        is_escalated=issue.is_escalated,
        job_count=issue.job_count if hasattr(issue, "job_count") else issue.jobs.count(),
        created_at=issue.created_at,
    )


def _job_out(job: Job) -> JobOut:
    assigned_user = job.assigned_to_user
    assigned_cleaner = job.assigned_to_cleaner
    assigned_by = job.assigned_by
    verified_by = job.verified_by
    issue = job.issue
    return JobOut(
        id=job.pk,
        issue_id=job.issue_id,
        issue_title=issue.title if issue else None,
        job_title=job.job_title,
        description=job.description,
        site_id=job.site_id,
        site_name=job.site.name,
        assigned_to_user=assigned_user.email if assigned_user else None,
        assigned_to_user_id=job.assigned_to_user_id,
        assigned_to_cleaner=assigned_cleaner.full_name if assigned_cleaner else None,
        assigned_to_cleaner_id=job.assigned_to_cleaner_id,
        assigned_by=assigned_by.email if assigned_by else None,
        due_date=job.due_date,
        priority=job.priority,
        status=job.status,
        completion_notes=job.completion_notes,
        has_completion_photo=bool(job.file),
        completed_at=job.completed_at,
        verified_by=verified_by.email if verified_by else None,
        verified_at=job.verified_at,
        closed_at=job.closed_at,
        created_at=job.created_at,
    )


@router.get(
    "/issues",
    response=Paginated[IssueOut],
    summary="List issues (paginated, filtered)",
)
def issue_list_endpoint(
    request: AuthenticatedRequest,
    filters: PageParams = PAGE_PARAMS_DEFAULT,
    site_id: int | None = None,
    status: str | None = None,
    priority: str | None = None,
    category: str | None = None,
    source: str | None = None,
    assigned_to_id: int | None = None,
    escalated: bool | None = None,
    ordering: str | None = None,
) -> Paginated[IssueOut]:
    _issues_read(request.auth)
    spec = IssueFilter(
        site_id=site_id,
        status=status,
        priority=priority,
        category=category,
        source=source,
        assigned_to_id=assigned_to_id,
        escalated=escalated,
    )
    qs = apply_ordering(
        issue_list(request.auth, spec), ordering, ["created_at", "due_date", "priority", "escalation_level"]
    )
    items, count, page, page_size = paginate(qs, filters.page, filters.page_size)
    results = [_issue_out(i) for i in items]
    return paginated_response(request, qs, page, page_size, results, count)


@router.get(
    "/issues/summary",
    response=IssueSummaryOut,
    summary="Issue summary counts",
)
def issue_summary_endpoint(
    request: AuthenticatedRequest,
    site_id: int | None = None,
    status: str | None = None,
    priority: str | None = None,
    category: str | None = None,
) -> IssueSummaryOut:
    _issues_read(request.auth)
    spec = IssueFilter(site_id=site_id, status=status, priority=priority, category=category)
    return IssueSummaryOut(**issue_summary(request.auth, spec))


@router.post("/issues", response=IssueOut, summary="Raise an issue")
def issue_create(request: AuthenticatedRequest, payload: IssueCreateIn) -> IssueOut:
    site = _load_site_or_404(payload.site_id)
    _issues_manage(request.auth, site.pk)
    area = SiteArea.objects.filter(pk=payload.area_id).first() if payload.area_id else None
    cleaner = Cleaner.objects.filter(pk=payload.cleaner_id).first() if payload.cleaner_id else None
    inspection = None
    if payload.inspection_id:
        inspection = Inspection.objects.filter(pk=payload.inspection_id).first()
        if inspection is None or inspection.site_id != site.pk:
            raise Http404("Inspection not found.")
    created = create_issue(
        title=payload.title,
        site=site,
        raised_by=request.auth,
        actor=request.auth,
        description=payload.description,
        source=payload.source,
        issue_category=payload.issue_category,
        priority=payload.priority,
        area=area,
        cleaner=cleaner,
        inspection=inspection,
        due_date=payload.due_date,
    )
    return _issue_out(get_issue_or_none(created.pk) or created)


@router.get(
    "/issues/export",
    summary="Stream visible issues as CSV",
    tags=["Issues & Jobs"],
)
def issues_export_endpoint(
    request: AuthenticatedRequest,
    site_id: int | None = None,
    status: str | None = None,
    priority: str | None = None,
) -> StreamingHttpResponse:
    """Export the caller's visible issues as CSV (streamed, never loaded fully)."""
    _issues_read(request.auth)
    if not can_export_data(request.auth, "issues"):
        raise PermissionDenied("You do not have permission to export data.")

    spec = IssueFilter(site_id=site_id, status=status, priority=priority)
    headers = ["id", "title", "site", "category", "priority", "status", "created_at"]
    rows = (
        issue_list(request.auth, spec)
        .order_by("created_at")
        .values("id", "title", "site__name", "issue_category", "priority", "status", "created_at")
    )

    def _stream() -> Any:
        yield _csv_line(headers)
        for row in rows.iterator(chunk_size=500):
            yield _csv_line(
                [
                    str(row["id"]),
                    row["title"],
                    row["site__name"],
                    row["issue_category"],
                    row["priority"],
                    row["status"],
                    row["created_at"].isoformat() if row["created_at"] else "",
                ]
            )

    return StreamingHttpResponse(_stream(), content_type="text/csv")


def _csv_line(fields: list[str]) -> str:
    escaped = [f'"{field.replace(chr(34), chr(34) + chr(34))}"' for field in fields]
    return ",".join(escaped) + "\n"


@router.get("/issues/{issue_id}", response=IssueOut, summary="Issue detail")
def issue_detail_endpoint(request: AuthenticatedRequest, issue_id: int) -> IssueOut:
    _issues_read(request.auth)
    issue = _load_issue_or_404(issue_id)
    if not site_in_user_scope(request.auth, issue.site_id):
        raise PermissionDenied("You do not have access to this issue.")
    return _issue_out(issue)


@router.put("/issues/{issue_id}", response=IssueOut, summary="Update an issue")
def issue_update(request: AuthenticatedRequest, issue_id: int, payload: IssueUpdateIn) -> IssueOut:
    issue = _load_issue_or_404(issue_id)
    _issues_manage(request.auth, issue.site_id)
    area = SiteArea.objects.filter(pk=payload.area_id).first() if payload.area_id is not None else None
    cleaner = Cleaner.objects.filter(pk=payload.cleaner_id).first() if payload.cleaner_id is not None else None
    updated = update_issue(
        issue=issue,
        actor=request.auth,
        title=payload.title,
        description=payload.description,
        issue_category=payload.issue_category,
        priority=payload.priority,
        area=area,
        cleaner=cleaner,
        due_date=payload.due_date,
    )
    return _issue_out(get_issue_or_none(updated.pk) or updated)


@router.post("/issues/{issue_id}/review", response=IssueOut, summary="Review an issue")
def issue_review(request: AuthenticatedRequest, issue_id: int, payload: IssueReviewIn) -> IssueOut:
    issue = _load_issue_or_404(issue_id)
    _issues_review(request.auth)
    reviewed = review_issue(issue=issue, actor=request.auth, notes=payload.notes)
    return _issue_out(get_issue_or_none(reviewed.pk) or reviewed)


@router.post("/issues/{issue_id}/escalate", response=IssueOut, summary="Escalate an issue")
def issue_escalate(request: AuthenticatedRequest, issue_id: int, payload: IssueEscalateIn) -> IssueOut:
    issue = _load_issue_or_404(issue_id)
    _issues_escalate(request.auth)
    escalated = escalate_issue(issue=issue, actor=request.auth, reason=payload.reason)
    return _issue_out(get_issue_or_none(escalated.pk) or escalated)


@router.post("/issues/{issue_id}/jobs", response=JobOut, summary="Assign a job from an issue")
def issue_assign_job(request: AuthenticatedRequest, issue_id: int, payload: JobAssignIn) -> JobOut:
    issue = _load_issue_or_404(issue_id)
    _issues_assign(request.auth, issue.site_id)
    assigned_user = User.objects.filter(pk=payload.assigned_to_user_id).first() if payload.assigned_to_user_id else None
    assigned_cleaner = (
        Cleaner.objects.filter(pk=payload.assigned_to_cleaner_id).first() if payload.assigned_to_cleaner_id else None
    )
    job = assign_job_from_issue(
        issue=issue,
        actor=request.auth,
        assigned_to_user=assigned_user,
        assigned_to_cleaner=assigned_cleaner,
    )
    return _job_out(get_job_or_none(job.pk) or job)


@router.get(
    "/jobs",
    response=Paginated[JobOut],
    summary="List jobs (paginated, filtered)",
)
def job_list_endpoint(
    request: AuthenticatedRequest,
    filters: PageParams = PAGE_PARAMS_DEFAULT,
    site_id: int | None = None,
    status: str | None = None,
    priority: str | None = None,
    issue_id: int | None = None,
    assigned_to_user_id: int | None = None,
    ordering: str | None = None,
) -> Paginated[JobOut]:
    _issues_read(request.auth)
    spec = JobFilter(
        site_id=site_id,
        status=status,
        priority=priority,
        issue_id=issue_id,
        assigned_to_user_id=assigned_to_user_id,
    )
    qs = apply_ordering(job_list(request.auth, spec), ordering, ["due_date", "created_at", "priority"])
    items, count, page, page_size = paginate(qs, filters.page, filters.page_size)
    results = [_job_out(j) for j in items]
    return paginated_response(request, qs, page, page_size, results, count)


@router.get(
    "/jobs/overdue",
    response=list[JobOut],
    summary="List overdue jobs",
)
def job_overdue_endpoint(
    request: AuthenticatedRequest,
    site_id: int | None = None,
) -> list[JobOut]:
    _issues_read(request.auth)
    return [_job_out(j) for j in overdue_jobs(request.auth, site_id)]


@router.get(
    "/jobs/summary",
    response=JobSummaryOut,
    summary="Job summary counts",
)
def job_summary_endpoint(
    request: AuthenticatedRequest,
    site_id: int | None = None,
    status: str | None = None,
) -> JobSummaryOut:
    _issues_read(request.auth)
    spec = JobFilter(site_id=site_id, status=status)
    return JobSummaryOut(**job_summary(request.auth, spec))


@router.post("/jobs", response=JobOut, summary="Create a job")
def job_create(request: AuthenticatedRequest, payload: JobCreateIn) -> JobOut:
    site = _load_site_or_404(payload.site_id)
    _issues_manage(request.auth, site.pk)
    issue = None
    if payload.issue_id:
        issue = Issue.objects.filter(pk=payload.issue_id).first()
        if issue is None or issue.site_id != site.pk:
            raise Http404("Issue not found.")
    assigned_user = User.objects.filter(pk=payload.assigned_to_user_id).first() if payload.assigned_to_user_id else None
    assigned_cleaner = (
        Cleaner.objects.filter(pk=payload.assigned_to_cleaner_id).first() if payload.assigned_to_cleaner_id else None
    )
    created = create_job(
        job_title=payload.job_title,
        site=site,
        assigned_by=request.auth,
        actor=request.auth,
        description=payload.description,
        issue=issue,
        assigned_to_user=assigned_user,
        assigned_to_cleaner=assigned_cleaner,
        due_date=payload.due_date,
        priority=payload.priority,
    )
    return _job_out(get_job_or_none(created.pk) or created)


@router.get("/jobs/{job_id}", response=JobOut, summary="Job detail")
def job_detail_endpoint(request: AuthenticatedRequest, job_id: int) -> JobOut:
    _issues_read(request.auth)
    job = _load_job_or_404(job_id)
    if not site_in_user_scope(request.auth, job.site_id):
        raise PermissionDenied("You do not have access to this job.")
    return _job_out(job)


@router.put("/jobs/{job_id}", response=JobOut, summary="Update a job")
def job_update(request: AuthenticatedRequest, job_id: int, payload: JobUpdateIn) -> JobOut:
    job = _load_job_or_404(job_id)
    _issues_manage(request.auth, job.site_id)
    updated = update_job(
        job=job,
        actor=request.auth,
        job_title=payload.job_title,
        description=payload.description,
        due_date=payload.due_date,
        priority=payload.priority,
    )
    return _job_out(get_job_or_none(updated.pk) or updated)


@router.post("/jobs/{job_id}/assign", response=JobOut, summary="Assign a job")
def job_assign(request: AuthenticatedRequest, job_id: int, payload: JobAssignIn) -> JobOut:
    job = _load_job_or_404(job_id)
    _issues_assign(request.auth, job.site_id)
    assigned_user = User.objects.filter(pk=payload.assigned_to_user_id).first() if payload.assigned_to_user_id else None
    assigned_cleaner = (
        Cleaner.objects.filter(pk=payload.assigned_to_cleaner_id).first() if payload.assigned_to_cleaner_id else None
    )
    assigned = assign_job(
        job=job,
        actor=request.auth,
        assigned_to_user=assigned_user,
        assigned_to_cleaner=assigned_cleaner,
    )
    return _job_out(get_job_or_none(assigned.pk) or assigned)


@router.post("/jobs/{job_id}/start", response=JobOut, summary="Start a job")
def job_start(request: AuthenticatedRequest, job_id: int) -> JobOut:
    job = _load_job_or_404(job_id)
    _issues_manage(request.auth, job.site_id)
    started = start_job(job=job, actor=request.auth)
    return _job_out(get_job_or_none(started.pk) or started)


@router.post("/jobs/{job_id}/complete", response=JobOut, summary="Complete a job")
def job_complete(request: AuthenticatedRequest, job_id: int, payload: JobCompleteIn) -> JobOut:
    job = _load_job_or_404(job_id)
    _issues_manage(request.auth, job.site_id)
    completed = complete_job(job=job, actor=request.auth, completion_notes=payload.completion_notes)
    return _job_out(get_job_or_none(completed.pk) or completed)


@router.post(
    "/jobs/{job_id}/photo",
    response=JobOut,
    summary="Upload a private completion photo for a job",
)
def job_photo_upload(
    request: AuthenticatedRequest,
    job_id: int,
    file: UploadedFile = FILE_PARAM_DEFAULT,
) -> JobOut:
    job = _load_job_or_404(job_id)
    _issues_manage(request.auth, job.site_id)
    updated = upload_job_photo(job=job, uploaded_file=file, actor=request.auth)
    return _job_out(get_job_or_none(updated.pk) or updated)


@router.get(
    "/jobs/{job_id}/photo/download-url",
    response=DownloadUrlOut,
    summary="Signed download URL for a job completion photo",
)
def job_photo_download_url(request: AuthenticatedRequest, job_id: int) -> DownloadUrlOut:
    _issues_read(request.auth)
    job = _load_job_or_404(job_id)
    if not site_in_user_scope(request.auth, job.site_id):
        raise PermissionDenied("You do not have access to this job.")
    if not job.file:
        raise Http404("This job has no completion photo.")
    token = create_file_token(
        user_id=request.auth.pk,
        app_label="site_management",
        model_name="job",
        object_id=job.pk,
    )
    return DownloadUrlOut(download_url=f"/{settings.API_V1_PREFIX}/files/signed/{token}/")


@router.post("/jobs/{job_id}/verify", response=JobOut, summary="Verify a completed job")
def job_verify(request: AuthenticatedRequest, job_id: int) -> JobOut:
    job = _load_job_or_404(job_id)
    _issues_verify(request.auth, job.site_id)
    verified = verify_job(job=job, actor=request.auth)
    return _job_out(get_job_or_none(verified.pk) or verified)


@router.post("/jobs/{job_id}/close", response=JobOut, summary="Close a verified job")
def job_close(request: AuthenticatedRequest, job_id: int) -> JobOut:
    job = _load_job_or_404(job_id)
    _issues_review(request.auth)
    closed = close_job(job=job, actor=request.auth)
    return _job_out(get_job_or_none(closed.pk) or closed)


@router.post("/jobs/{job_id}/reopen", response=JobOut, summary="Reopen a job")
def job_reopen(request: AuthenticatedRequest, job_id: int, payload: JobReopenIn) -> JobOut:
    job = _load_job_or_404(job_id)
    _issues_review(request.auth)
    reopened = reopen_job(job=job, actor=request.auth, reason=payload.reason)
    return _job_out(get_job_or_none(reopened.pk) or reopened)


# --------------------------------------------------------------------------- #
# Reporting chain
# --------------------------------------------------------------------------- #


def _report_read(user: User) -> None:
    if not (management_required(user) or user.is_management_viewer):
        raise PermissionDenied("Reports require a management role.")


def _report_review(user: User) -> None:
    if not (
        user.is_system_admin
        or user.role
        in {
            RoleCode.GENERAL_SUPERVISOR,
            RoleCode.ASSISTANT_GENERAL_SUPERVISOR,
            RoleCode.ZONE_SUPERVISOR,
        }
    ):
        raise PermissionDenied("Only zone-level management can review reports.")


def _assistant_report_manage(user: User) -> None:
    if not (user.is_system_admin or user.role in {RoleCode.GENERAL_SUPERVISOR, RoleCode.ASSISTANT_GENERAL_SUPERVISOR}):
        raise PermissionDenied("Only assistant general management can author these reports.")


def _general_report_manage(user: User) -> None:
    if not (user.is_system_admin or user.role == RoleCode.GENERAL_SUPERVISOR):
        raise PermissionDenied("Only the general supervisor can author this report.")


def _load_site_report_or_404(site_id: int, day: date) -> DailySiteReport:
    report = site_report_detail(site_id, day)
    if report is None:
        raise Http404("Site report not found.")
    return report


def _load_zone_report_or_404(report_id: int) -> ZoneSummaryReport:
    report = get_zone_report_or_none(report_id)
    if report is None:
        raise Http404("Zone report not found.")
    return report


def _load_assistant_report_or_404(report_id: int) -> AssistantGeneralSummaryReport:
    report = get_assistant_report_or_none(report_id)
    if report is None:
        raise Http404("Assistant report not found.")
    return report


def _load_general_report_or_404(report_id: int) -> GeneralManagementReport:
    report = get_general_report_or_none(report_id)
    if report is None:
        raise Http404("General report not found.")
    return report


def _site_report_out(r: DailySiteReport) -> DailySiteReportOut:
    created_by = r.created_by
    return DailySiteReportOut(
        id=r.pk,
        site_id=r.site_id,
        site_name=r.site.name,
        report_date=r.report_date,
        attendance_summary=r.attendance_summary,
        store_summary=r.store_summary,
        inspection_summary=r.inspection_summary,
        trainee_summary=r.trainee_summary,
        issues_summary=r.issues_summary,
        general_comments=r.general_comments,
        status=r.status,
        snapshot=r.snapshot,
        submitted_at=r.submitted_at,
        returned_reason=r.returned_reason,
        created_by=created_by.email if created_by else None,
    )


def _zone_report_out(r: ZoneSummaryReport) -> ZoneSummaryReportOut:
    supervisor = r.zone_supervisor
    return ZoneSummaryReportOut(
        id=r.pk,
        zone_id=r.zone_id,
        zone_name=r.zone.name,
        report_date=r.report_date,
        summary=r.summary,
        issues_extracted=r.issues_extracted,
        site_reports=r.site_reports,
        status=r.status,
        submitted_at=r.submitted_at,
        zone_supervisor=supervisor.email if supervisor else None,
    )


def _assistant_report_out(r: AssistantGeneralSummaryReport) -> AssistantSummaryOut:
    author = r.assistant_general_supervisor
    return AssistantSummaryOut(
        id=r.pk,
        report_date=r.report_date,
        zone_ids=r.zone_ids,
        summary=r.summary,
        problems_extracted=r.problems_extracted,
        recommendations=r.recommendations,
        status=r.status,
        submitted_at=r.submitted_at,
        assistant_general_supervisor=author.email if author else None,
    )


def _general_report_out(r: GeneralManagementReport) -> GeneralReportOut:
    author = r.general_supervisor
    return GeneralReportOut(
        id=r.pk,
        report_date=r.report_date,
        final_summary=r.final_summary,
        key_issues=r.key_issues,
        assigned_jobs=r.assigned_jobs,
        recommendations=r.recommendations,
        status=r.status,
        submitted_at=r.submitted_at,
        general_supervisor=author.email if author else None,
    )


@router.get(
    "/reports/site",
    response=Paginated[DailySiteReportOut],
    summary="List daily site reports (paginated)",
)
def site_report_list_endpoint(
    request: AuthenticatedRequest,
    filters: PageParams = PAGE_PARAMS_DEFAULT,
    report_date: date | None = None,
    site_id: int | None = None,
    status: str | None = None,
    ordering: str | None = None,
) -> Paginated[DailySiteReportOut]:
    _report_read(request.auth)
    qs = site_reports_for_day(request.auth, report_date or date.today())
    if site_id:
        qs = qs.filter(site_id=site_id)
    if status:
        qs = qs.filter(status=status)
    qs = apply_ordering(qs, ordering, ["report_date", "created_at"])
    items, count, page, page_size = paginate(qs, filters.page, filters.page_size)
    results = [_site_report_out(r) for r in items]
    return paginated_response(request, qs, page, page_size, results, count)


@router.get("/reports/site/{site_id}/{report_date}", response=DailySiteReportOut, summary="Site report detail")
def site_report_detail_endpoint(request: AuthenticatedRequest, site_id: int, report_date: date) -> DailySiteReportOut:
    _report_read(request.auth)
    report = _load_site_report_or_404(site_id, report_date)
    if not site_in_user_scope(request.auth, report.site_id):
        raise PermissionDenied("You do not have access to this report.")
    return _site_report_out(report)


@router.post(
    "/reports/site/{site_id}/{report_date}/generate",
    response=DailySiteReportOut,
    summary="Generate a daily site report",
)
def site_report_generate_endpoint(request: AuthenticatedRequest, site_id: int, report_date: date) -> DailySiteReportOut:
    site = _load_site_or_404(site_id)
    _issues_manage(request.auth, site.pk)
    report = generate_site_report(site_id=site_id, day=report_date, user=request.auth)
    return _site_report_out(report)


@router.post(
    "/reports/site/{site_id}/{report_date}/submit",
    response=DailySiteReportOut,
    summary="Submit a daily site report",
)
def site_report_submit_endpoint(request: AuthenticatedRequest, site_id: int, report_date: date) -> DailySiteReportOut:
    report = _load_site_report_or_404(site_id, report_date)
    _issues_manage(request.auth, report.site_id)
    submitted = submit_site_report(report=report, user=request.auth)
    return _site_report_out(get_site_report_or_none(submitted.pk) or submitted)


@router.post(
    "/reports/site/{site_id}/{report_date}/return",
    response=DailySiteReportOut,
    summary="Return a submitted site report",
)
def site_report_return_endpoint(
    request: AuthenticatedRequest, site_id: int, report_date: date, payload: ReportReturnIn
) -> DailySiteReportOut:
    report = _load_site_report_or_404(site_id, report_date)
    _report_review(request.auth)
    returned = return_site_report(report=report, user=request.auth, reason=payload.reason)
    return _site_report_out(get_site_report_or_none(returned.pk) or returned)


@router.get(
    "/reports/zone",
    response=list[ZoneSummaryReportOut],
    summary="List zone summary reports",
)
def zone_report_list_endpoint(
    request: AuthenticatedRequest, report_date: date | None = None
) -> list[ZoneSummaryReportOut]:
    _report_read(request.auth)
    qs = ZoneSummaryReport.objects.select_related("zone", "zone_supervisor")
    if report_date:
        qs = qs.filter(report_date=report_date)
    if not request.auth.is_system_admin:
        qs = qs.filter(zone__in=visible_zones(request.auth))
    return [_zone_report_out(r) for r in qs]


@router.post(
    "/reports/zone/generate",
    response=ZoneSummaryReportOut,
    summary="Generate a zone summary report",
)
def zone_report_generate_endpoint(request: AuthenticatedRequest, payload: ZoneReportGenerateIn) -> ZoneSummaryReportOut:
    _report_review(request.auth)
    report = generate_zone_summary(zone_id=payload.zone_id, day=payload.report_date, user=request.auth)
    return _zone_report_out(zone_report_detail(payload.zone_id, payload.report_date) or report)


@router.post(
    "/reports/zone/{report_id}/submit",
    response=ZoneSummaryReportOut,
    summary="Submit a zone summary report",
)
def zone_report_submit_endpoint(request: AuthenticatedRequest, report_id: int) -> ZoneSummaryReportOut:
    report = _load_zone_report_or_404(report_id)
    _report_review(request.auth)
    submitted = submit_zone_summary(report=report, user=request.auth)
    return _zone_report_out(get_zone_report_or_none(submitted.pk) or submitted)


@router.post(
    "/reports/zone/{report_id}/return",
    response=ZoneSummaryReportOut,
    summary="Return a zone summary report",
)
def zone_report_return_endpoint(
    request: AuthenticatedRequest, report_id: int, payload: ReportReturnIn
) -> ZoneSummaryReportOut:
    report = _load_zone_report_or_404(report_id)
    _assistant_report_manage(request.auth)
    returned = return_zone_summary(report=report, user=request.auth, reason=payload.reason)
    return _zone_report_out(get_zone_report_or_none(returned.pk) or returned)


@router.get(
    "/reports/assistant",
    response=list[AssistantSummaryOut],
    summary="List assistant general summaries",
)
def assistant_report_list_endpoint(
    request: AuthenticatedRequest, report_date: date | None = None
) -> list[AssistantSummaryOut]:
    _report_read(request.auth)
    qs = AssistantGeneralSummaryReport.objects.select_related("assistant_general_supervisor")
    if report_date:
        qs = qs.filter(report_date=report_date)
    return [_assistant_report_out(r) for r in qs]


@router.post(
    "/reports/assistant/generate",
    response=AssistantSummaryOut,
    summary="Generate an assistant general summary",
)
def assistant_report_generate_endpoint(
    request: AuthenticatedRequest, payload: AssistantSummaryGenerateIn
) -> AssistantSummaryOut:
    _assistant_report_manage(request.auth)
    report = generate_assistant_summary(day=payload.report_date, user=request.auth, zone_ids=payload.zone_ids)
    return _assistant_report_out(assistant_report_detail(payload.report_date) or report)


@router.post(
    "/reports/assistant/{report_id}/submit",
    response=AssistantSummaryOut,
    summary="Submit an assistant general summary",
)
def assistant_report_submit_endpoint(request: AuthenticatedRequest, report_id: int) -> AssistantSummaryOut:
    report = _load_assistant_report_or_404(report_id)
    _assistant_report_manage(request.auth)
    submitted = submit_assistant_summary(report=report, user=request.auth)
    return _assistant_report_out(get_assistant_report_or_none(submitted.pk) or submitted)


@router.post(
    "/reports/assistant/{report_id}/return",
    response=AssistantSummaryOut,
    summary="Return an assistant general summary",
)
def assistant_report_return_endpoint(
    request: AuthenticatedRequest, report_id: int, payload: ReportReturnIn
) -> AssistantSummaryOut:
    report = _load_assistant_report_or_404(report_id)
    _general_report_manage(request.auth)
    returned = return_assistant_summary(report=report, user=request.auth, reason=payload.reason)
    return _assistant_report_out(get_assistant_report_or_none(returned.pk) or returned)


@router.get(
    "/reports/general",
    response=list[GeneralReportOut],
    summary="List general management reports",
)
def general_report_list_endpoint(
    request: AuthenticatedRequest, report_date: date | None = None
) -> list[GeneralReportOut]:
    _report_read(request.auth)
    qs = GeneralManagementReport.objects.select_related("general_supervisor")
    if report_date:
        qs = qs.filter(report_date=report_date)
    return [_general_report_out(r) for r in qs]


@router.post(
    "/reports/general/generate",
    response=GeneralReportOut,
    summary="Generate the final management report",
)
def general_report_generate_endpoint(
    request: AuthenticatedRequest, payload: GeneralReportGenerateIn
) -> GeneralReportOut:
    _general_report_manage(request.auth)
    report = generate_general_management_report(day=payload.report_date, user=request.auth)
    return _general_report_out(general_report_detail(payload.report_date) or report)


@router.post(
    "/reports/general/{report_id}/submit",
    response=GeneralReportOut,
    summary="Submit the management report",
)
def general_report_submit_endpoint(request: AuthenticatedRequest, report_id: int) -> GeneralReportOut:
    report = _load_general_report_or_404(report_id)
    _general_report_manage(request.auth)
    submitted = submit_general_management_report(report=report, user=request.auth)
    return _general_report_out(get_general_report_or_none(submitted.pk) or submitted)


@router.get("/reports/status", response=ReportingStatusOut, summary="Reporting status dashboard")
def reporting_status_endpoint(request: AuthenticatedRequest, report_date: date | None = None) -> ReportingStatusOut:
    _report_read(request.auth)
    return ReportingStatusOut(**reporting_status_dashboard(request.auth, report_date or date.today()))


@router.get(
    "/reports/missing",
    response=list[MissingSiteReportOut],
    summary="Sites missing a submitted report for a date",
)
def missing_site_reports_endpoint(
    request: AuthenticatedRequest, report_date: date | None = None
) -> list[MissingSiteReportOut]:
    _report_read(request.auth)
    return [MissingSiteReportOut(**m) for m in missing_site_reports(request.auth, report_date or date.today())]


@router.get("/theme", response=ThemeOut, summary="Brand theme metadata", tags=["Theme"])
def theme_endpoint(request: AuthenticatedRequest) -> ThemeOut:
    """Return brand identity for the frontend (name + colours), cached briefly."""
    _report_read(request.auth)
    from apps.core.cache import cached_or

    def _load() -> dict[str, Any]:
        return {
            "brand_name": config.BRAND_NAME,
            "brand_primary_color": config.BRAND_PRIMARY_COLOR,
            "brand_accent_color": config.BRAND_ACCENT_COLOR,
            "brand_background_color": config.BRAND_BACKGROUND_COLOR,
            "logo_url": "/static/images/logo.svg",
            "version": getattr(settings, "API_VERSION", "1.0.0"),
        }

    return ThemeOut(**cached_or("theme", (), _load, int(config.REPORT_CACHE_TTL)))
