"""Site management API router.

Routers stay thin: parse/validate input, enforce authorization, delegate to
services (writes) or selectors (reads), and shape output schemas.
"""

from __future__ import annotations

from typing import Any

from django.core.exceptions import PermissionDenied
from django.http import Http404
from ninja import Query, Router

from apps.accounts.models import Role, User
from apps.accounts.permissions import role_required, user_can_manage_site
from apps.common.requests import AuthenticatedRequest

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
from .schemas import (
    AssetCategoryOut,
    AssetCreateIn,
    AssetOut,
    AssetUpdateIn,
    AssignmentCreateIn,
    AssignmentOut,
    DepartmentCreateIn,
    DepartmentOut,
    DepartmentUpdateIn,
    MessageOut,
    NotificationOut,
    SiteCreateIn,
    SiteDetailOut,
    SiteStatsOut,
    SiteStatusOut,
    SiteSummaryOut,
    SiteTypeOut,
    SiteUpdateIn,
    StatusRef,
)
from .selectors import (
    SiteFilter,
    get_all_site_stats,
    get_site_detail,
    get_site_or_none,
    get_site_stats,
    list_assets,
    list_assignments,
    list_departments,
    list_notifications,
    list_site_statuses,
    list_site_types,
    list_sites,
    unread_notification_count,
)
from .services import (
    SiteDraft,
    archive_site,
    assign_staff,
    create_asset,
    create_department,
    create_site,
    deactivate_asset,
    deactivate_department,
    mark_notifications_read,
    restore_site,
    scoped_site_ids,
    set_primary_assignment,
    unassign_staff,
    update_asset,
    update_department,
    update_site,
)

router = Router()


# --------------------------------------------------------------------------- #
# Authorization helpers
# --------------------------------------------------------------------------- #


def _read_access(user: User, site_id: int) -> None:
    if user.is_admin:
        return
    if not Site.objects.filter(pk=site_id, staff_assignments__user=user).exists():
        raise PermissionDenied("You do not have access to this site.")


def _write_access(user: User, site_id: int) -> None:
    if user.is_admin:
        return
    if not user_can_manage_site(user, site_id):
        raise PermissionDenied("You do not have permission to modify this site.")


def _load_site_or_404(site_id: int) -> Site:
    site = get_site_or_none(site_id)
    if site is None:
        raise Http404("Site not found.")
    return site


def _ensure_role(user: User, *roles: Role) -> None:
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
        site_type=site.site_type.name if site.site_type else None,
        status=_status_ref(site),
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
        username=assignment.user.username,
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


@router.get("/sites", response=list[SiteSummaryOut], summary="List sites (filterable)")
def site_list(
    request: AuthenticatedRequest,
    search: str | None = None,
    status: str | None = None,
    site_type: str | None = None,
    region: str | None = None,
    country: str | None = None,
    capacity_min: int | None = Query(None, ge=0),  # type: ignore[type-arg]
) -> list[SiteSummaryOut]:
    spec = SiteFilter(
        search=search,
        status=status,
        site_type=site_type,
        region=region,
        country=country,
        capacity_min=capacity_min,
    )
    sites = list_sites(spec)
    if not request.auth.is_admin:
        allowed = set(scoped_site_ids(request.auth))
        sites = [site for site in sites if site.pk in allowed]
    return [_summary(site) for site in sites]


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
    _ensure_role(request.auth, Role.ADMIN, Role.MANAGER)
    draft = SiteDraft(
        name=payload.name,
        site_type=_type_or_none(payload.site_type_id),
        status=_status_or_none(payload.status_id),
        description=payload.description,
        address=payload.address,
        city=payload.city,
        region=payload.region,
        country=payload.country,
        postal_code=payload.postal_code,
        latitude=payload.latitude,
        longitude=payload.longitude,
        capacity=payload.capacity,
        contact_email=payload.contact_email,
        contact_phone=payload.contact_phone,
    )
    site = create_site(draft=draft, actor=request.auth)
    return _reload_detail(site.pk)


@router.patch(
    "/sites/{site_id}",
    response=SiteDetailOut,
    summary="Update a site",
)
def site_update(
    request: AuthenticatedRequest, site_id: int, payload: SiteUpdateIn
) -> SiteDetailOut:
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
        site_type=(
            _type_or_none(payload.site_type_id)
            if payload.site_type_id is not None
            else current.site_type
        ),
        status=(
            _status_or_none(payload.status_id)
            if payload.status_id is not None
            else current.status
        ),
        description=pick(payload.description, current.description),
        address=pick(payload.address, current.address),
        city=pick(payload.city, current.city),
        region=pick(payload.region, current.region),
        country=pick(payload.country, current.country),
        postal_code=pick(payload.postal_code, current.postal_code),
        latitude=pick(payload.latitude, current.latitude),
        longitude=pick(payload.longitude, current.longitude),
        capacity=pick(payload.capacity, current.capacity),
        contact_email=pick(payload.contact_email, current.contact_email),
        contact_phone=pick(payload.contact_phone, current.contact_phone),
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
    _ensure_role(request.auth, Role.ADMIN)
    site = Site.objects.all_with_deleted().filter(pk=site_id).first()
    if site is None:
        raise Http404("Site not found.")
    restore_site(site=site, actor=request.auth)
    return _reload_detail(site.pk)


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
def department_create(
    request: AuthenticatedRequest, site_id: int, payload: DepartmentCreateIn
) -> Department:
    _write_access(request.auth, site_id)
    site = _load_site_or_404(site_id)
    return create_department(
        site=site, name=payload.name, description=payload.description, actor=request.auth
    )


@router.patch(
    "/sites/{site_id}/departments/{department_id}",
    response=DepartmentOut,
    summary="Update a department",
)
def department_update(
    request: AuthenticatedRequest, site_id: int, department_id: int, payload: DepartmentUpdateIn
) -> Department:
    _write_access(request.auth, site_id)
    department = Department.objects.filter(
        pk=department_id, site_id=site_id, is_active=True
    ).first()
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
def department_delete(
    request: AuthenticatedRequest, site_id: int, department_id: int
) -> MessageOut:
    _write_access(request.auth, site_id)
    department = Department.objects.filter(
        pk=department_id, site_id=site_id, is_active=True
    ).first()
    if department is None:
        raise Http404("Department not found.")
    deactivate_department(department=department, actor=request.auth)
    return MessageOut(detail="Department deactivated.")


# --------------------------------------------------------------------------- #
# Assets
# --------------------------------------------------------------------------- #


@router.get("/sites/{site_id}/assets", response=list[AssetOut], summary="List assets")
def asset_list(
    request: AuthenticatedRequest, site_id: int, category: str | None = None
) -> list[Asset]:
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
def asset_update(
    request: AuthenticatedRequest, site_id: int, asset_id: int, payload: AssetUpdateIn
) -> Asset:
    _write_access(request.auth, site_id)
    asset = Asset.objects.filter(
        pk=asset_id, site_id=site_id, is_active=True
    ).first()
    if asset is None:
        raise Http404("Asset not found.")
    return update_asset(
        asset=asset,
        name=payload.name,
        category=(
            _category_or_none(payload.category_id)
            if payload.category_id is not None
            else None
        ),
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
    asset = Asset.objects.filter(
        pk=asset_id, site_id=site_id, is_active=True
    ).first()
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
def assignment_create(
    request: AuthenticatedRequest, site_id: int, payload: AssignmentCreateIn
) -> AssignmentOut:
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
def assignment_delete(
    request: AuthenticatedRequest, site_id: int, assignment_id: int
) -> MessageOut:
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
def assignment_set_primary(
    request: AuthenticatedRequest, site_id: int, assignment_id: int
) -> AssignmentOut:
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
    _ensure_role(request.auth, Role.ADMIN)
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
def notification_list(
    request: AuthenticatedRequest, unread_only: bool = False
) -> list[NotificationOut]:
    return [_notification_out(n) for n in list_notifications(request.auth, unread_only=unread_only)]


@router.get("/notifications/unread-count", response=dict, summary="Unread notification count")
def notification_unread_count(request: AuthenticatedRequest) -> dict[str, object]:
    return {"count": unread_notification_count(request.auth)}


@router.post(
    "/notifications/mark-read",
    response=dict,
    summary="Mark notifications as read",
)
def notification_mark_read(
    request: AuthenticatedRequest, notification_ids: list[int]
) -> dict[str, object]:
    updated = mark_notifications_read(user=request.auth, notification_ids=notification_ids)
    return {"updated": updated}
