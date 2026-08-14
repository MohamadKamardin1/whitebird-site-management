"""Read-only access to site data: queries, filtering, and cache-aware reads.

Selectors never mutate state. Writes go through ``apps.site_management.services`` which
is responsible for invalidating the caches these selectors populate.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import partial
from typing import Any

from django.db.models import Count, Q, QuerySet

from apps.accounts.models import User
from apps.core.cache import cached_or, invalidate, invalidate_prefix

from .models import (
    Asset,
    Department,
    Notification,
    OperationalRole,
    Site,
    SiteArea,
    SiteShift,
    SiteStatus,
    SiteType,
    SiteWorkingRule,
    StaffAssignment,
)

SITE_DETAIL_PREFIX = "site:detail"
SITE_STATS_PREFIX = "site:stats"
KPI_PREFIX = "kpi"
NOTIFICATIONS_PREFIX = "site:notifications"

DETAIL_CACHE_TTL = 300
STATS_CACHE_TTL = 300


@dataclass(frozen=True)
class SiteFilter:
    """Immutable filter spec for the site list query."""

    search: str | None = None
    status: str | None = None
    site_type: str | None = None
    region: str | None = None
    country: str | None = None
    capacity_min: int | None = None
    assigned_user_id: int | None = None


def _apply_filters(queryset: QuerySet[Site], spec: SiteFilter) -> QuerySet[Site]:
    qs: QuerySet[Site] = queryset
    if spec.search:
        qs = qs.filter(
            Q(name__icontains=spec.search)
            | Q(code__icontains=spec.search)
            | Q(city__icontains=spec.search)
            | Q(region__icontains=spec.search)
        )
    if spec.status:
        qs = qs.filter(status__slug=spec.status)
    if spec.site_type:
        qs = qs.filter(site_type__slug=spec.site_type)
    if spec.region:
        qs = qs.filter(region__iexact=spec.region)
    if spec.country:
        qs = qs.filter(country__iexact=spec.country)
    if spec.capacity_min is not None:
        qs = qs.filter(capacity__gte=spec.capacity_min)
    if spec.assigned_user_id is not None:
        qs = qs.filter(staff_assignments__user_id=spec.assigned_user_id).distinct()
    return qs


def list_sites_queryset(spec: SiteFilter) -> QuerySet[Site]:
    """Annotated site queryset used by paginated list endpoints."""
    qs: QuerySet[Site] = (
        Site.objects.select_related("site_type", "status", "zone")
        .annotate(
            n_departments=Count("departments", filter=Q(departments__is_active=True), distinct=True),
            n_assets=Count("assets", filter=Q(assets__is_active=True), distinct=True),
            n_staff=Count("staff_assignments", distinct=True),
        )
        .order_by("name")
    )
    return _apply_filters(qs, spec)


def list_sites(spec: SiteFilter) -> list[Site]:
    """List active sites with denormalised aggregate counts."""
    return list(list_sites_queryset(spec))


def get_site_or_none(site_id: int) -> Site | None:
    """Uncached direct lookup used by write paths and permission checks."""
    return Site.objects.select_related("site_type", "status", "zone").filter(pk=site_id).first()


def get_site_detail(site_id: int) -> dict[str, Any] | None:
    """Cache-aware site detail used by the API."""

    def loader() -> dict[str, Any] | None:
        site = get_site_or_none(site_id)
        if site is None:
            return None
        return {
            "id": site.pk,
            "name": site.name,
            "slug": site.slug,
            "code": site.code,
            "zone_id": site.zone_id,
            "zone_name": site.zone.name if site.zone else None,
            "site_type": site.site_type.name if site.site_type else None,
            "status": (
                {
                    "slug": site.status.slug,
                    "name": site.status.name,
                    "color": site.status.color,
                }
                if site.status
                else None
            ),
            "work_mode": site.work_mode,
            "building_name": site.building_name,
            "location": site.location,
            "description": site.description,
            "address": site.address,
            "city": site.city,
            "region": site.region,
            "country": site.country,
            "postal_code": site.postal_code,
            "latitude": site.latitude,
            "longitude": site.longitude,
            "capacity": site.capacity,
            "contact_person": site.contact_person,
            "contact_email": site.contact_email,
            "contact_phone": site.contact_phone,
            "working_days": list(site.working_days),
            "start_date": site.start_date.isoformat() if site.start_date else None,
            "notes": site.notes,
            "department_count": site.department_count,
            "asset_count": site.asset_count,
            "staff_count": site.staff_count,
            "created_at": site.created_at.isoformat(),
            "updated_at": site.updated_at.isoformat(),
        }

    return cached_or(SITE_DETAIL_PREFIX, (site_id,), loader, DETAIL_CACHE_TTL)


def invalidate_site(site_id: int) -> None:
    invalidate(SITE_DETAIL_PREFIX, site_id)
    invalidate(SITE_STATS_PREFIX, site_id)


def list_departments(site_id: int) -> list[Department]:
    return list(
        Department.objects.filter(site_id=site_id, is_active=True).select_related("site", "manager").order_by("name")
    )


def list_assets(site_id: int, category_slug: str | None = None) -> list[Asset]:
    qs = Asset.objects.filter(site_id=site_id, is_active=True).select_related("site", "category")
    if category_slug:
        qs = qs.filter(category__slug=category_slug)
    return list(qs.order_by("name"))


def list_assignments(site_id: int) -> list[StaffAssignment]:
    return list(StaffAssignment.objects.filter(site_id=site_id).select_related("site", "user").order_by("user__email"))


def list_notifications(user: User, *, unread_only: bool = False, limit: int = 50) -> list[Notification]:
    qs = Notification.objects.filter(recipient=user).select_related("recipient")
    if unread_only:
        qs = qs.filter(is_read=False)
    return list(qs[:limit])


def unread_notification_count(user: User) -> int:
    return Notification.objects.filter(recipient=user, is_read=False).count()


def _compute_site_stats(site_id: int) -> dict[str, Any]:
    site = get_site_or_none(site_id)
    if site is None:
        return {}
    return {
        "site_id": site_id,
        "name": site.name,
        "status": site.status.slug if site.status else None,
        "departments": site.department_count,
        "assets": site.asset_count,
        "staff": site.staff_count,
        "capacity": site.capacity,
        "occupancy_ratio": round(site.staff_count / site.capacity, 4) if site.capacity else 0.0,
    }


def get_site_stats(site_id: int) -> dict[str, Any]:
    """Cache-aware aggregate statistics for a single site."""
    return cached_or(
        SITE_STATS_PREFIX,
        (site_id,),
        lambda: _compute_site_stats(site_id),
        STATS_CACHE_TTL,
    )


def get_all_site_stats() -> dict[int, dict[str, Any]]:
    """Compute statistics for every active site in a single annotated query.

    Previously each site fired 3 extra ``.count()`` queries (departments,
    assets, staff); the annotated aggregate collapses the whole call into one
    query.
    """
    from django.db.models import Count

    qs = (
        Site.objects.filter(is_active=True)
        .select_related("status")
        .annotate(
            n_departments=Count("departments", distinct=True),
            n_assets=Count("assets", distinct=True),
            n_staff=Count("staff_assignments", distinct=True),
        )
    )
    return {
        site.pk: {
            "site_id": site.pk,
            "name": site.name,
            "status": site.status.slug if site.status else None,
            "departments": site.n_departments,
            "assets": site.n_assets,
            "staff": site.n_staff,
            "capacity": site.capacity,
            "occupancy_ratio": round(site.n_staff / site.capacity, 4) if site.capacity else 0.0,
        }
        for site in qs
    }


def get_kpi_overview() -> dict[str, Any]:
    """Cache-aware cross-site KPI overview (single aggregated query)."""

    def _compute() -> dict[str, Any]:
        per_site = get_all_site_stats()
        total_capacity = sum(s["capacity"] for s in per_site.values())
        total_staff = sum(s["staff"] for s in per_site.values())
        breakdown: dict[str, int] = {}
        for row in per_site.values():
            status = "unknown" if row.get("status") is None else str(row["status"])
            breakdown[status] = breakdown.get(status, 0) + 1
        return {
            "site_count": len(per_site),
            "total_capacity": total_capacity,
            "total_staff": total_staff,
            "occupancy_ratio": round(total_staff / total_capacity, 4) if total_capacity else 0.0,
            "status_breakdown": breakdown,
        }

    return cached_or(KPI_PREFIX, ("overview",), _compute, STATS_CACHE_TTL)


def refresh_all_site_stats_cache() -> None:
    stats = get_all_site_stats()
    for site_id, payload in stats.items():
        cached_or(
            SITE_STATS_PREFIX,
            (site_id,),
            partial(_pass_through, payload),
            STATS_CACHE_TTL,
        )
    invalidate_prefix(SITE_STATS_PREFIX)
    invalidate(KPI_PREFIX, "overview")


def _pass_through(payload: dict[str, Any]) -> dict[str, Any]:
    return payload


def list_site_types() -> list[SiteType]:
    return list(SiteType.objects.filter(is_active=True))


def list_site_statuses() -> list[SiteStatus]:
    return list(SiteStatus.objects.filter(is_active=True))


def list_shifts(site_id: int) -> list[SiteShift]:
    """Active shifts for a site, ordered by sequence then start time."""
    return list(
        SiteShift.objects.filter(site_id=site_id, is_active=True)
        .select_related("site")
        .order_by("sequence", "start_time", "shift_name")
    )


def list_areas(site_id: int) -> list[SiteArea]:
    """Active areas for a site, ordered by name."""
    return list(SiteArea.objects.filter(site_id=site_id, is_active=True).select_related("site").order_by("area_name"))


def list_operational_roles() -> list[OperationalRole]:
    """Active global operational roles."""
    return list(OperationalRole.objects.filter(is_active=True).order_by("name"))


def get_site_working_rule(site: Site) -> SiteWorkingRule:
    """Return the site's working rule, creating the default if absent."""
    rule, _ = SiteWorkingRule.objects.get_or_create(site=site)
    return rule
