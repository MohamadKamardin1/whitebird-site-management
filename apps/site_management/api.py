"""Site management API router.

Routers stay thin: parse/validate input, enforce authorization, delegate to
services (writes) or selectors (reads), and shape output schemas.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.http import Http404
from ninja import File, Form, Query, Router, UploadedFile

from apps.accounts.models import RoleCode, User
from apps.accounts.permissions import management_required, role_required, user_can_manage_site
from apps.core.files import create_file_token
from apps.core.pagination import PageParams, Paginated, paginate, paginated_response
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
from .models import (
    Asset,
    AssetCategory,
    CleanerAreaSchedule,
    CleanerAssignmentType,
    CleanerDocumentType,
    CleanerShiftAssignment,
    CleanerSiteAssignment,
    CleanerStatus,
    Department,
    Gender,
    IdType,
    Notification,
    OperationalRole,
    Site,
    SiteArea,
    SiteShift,
    SiteStatus,
    SiteSupervisorAssignment,
    SiteType,
    StaffAssignment,
    WorkMode,
    Zone,
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
    DepartmentCreateIn,
    DepartmentOut,
    DepartmentUpdateIn,
    DocumentReviewIn,
    DownloadUrlOut,
    MessageOut,
    NotificationOut,
    OperationalRoleCreateIn,
    OperationalRoleOut,
    OperationalRoleUpdateIn,
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
    ZoneOut,
)
from .scoping import site_in_user_scope, visible_sites, visible_zones
from .selectors import (
    SiteFilter,
    get_all_site_stats,
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
    per_site = get_all_site_stats()
    total_capacity = sum(s["capacity"] for s in per_site.values())
    total_staff = sum(s["staff"] for s in per_site.values())
    return {
        "site_count": len(per_site),
        "total_capacity": total_capacity,
        "total_staff": total_staff,
        "occupancy_ratio": round(total_staff / total_capacity, 4) if total_capacity else 0.0,
        "status_breakdown": _status_breakdown(list(per_site.values())),
    }


def _status_breakdown(rows: list[dict[str, object]]) -> dict[str, int]:
    breakdown: dict[str, int] = {}
    for row in rows:
        status = "unknown" if row.get("status") is None else str(row["status"])
        breakdown[status] = breakdown.get(status, 0) + 1
    return breakdown


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
) -> Paginated[CleanerOut]:
    _cleaner_read(request.auth)
    spec = CleanerFilter(search=search, status=status, id_type=id_type, gender=gender)
    qs = cleaner_list_queryset(request.auth, spec)
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
