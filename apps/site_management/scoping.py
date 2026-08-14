"""Role-based data scoping for the organisation hierarchy.

These selectors answer "what can this user see/supervise?" without leaking
query internals to routers. Rules:

* SYSTEM_ADMIN and GENERAL_SUPERVISOR see everything.
* MANAGEMENT_VIEWER sees everything read-only (no write capacity).
* ASSISTANT_GENERAL_SUPERVISOR sees all zones when an active ``all_zones``
  assignment exists, otherwise only the zones they are assigned to.
* ZONE_SUPERVISOR sees the zones (and their sites) they are assigned to.
* SITE_SUPERVISOR sees only the sites they are actively assigned to.
"""

from __future__ import annotations

from django.db.models import Q, QuerySet

from apps.accounts.models import RoleCode, User

from .models import AssistantGeneralSupervisorAssignment, Site, SiteSupervisorAssignment, Zone, ZoneSupervisorAssignment

ACTIVE = Q(is_active=True)


def _sees_all_zones(user: User) -> bool:
    """True when the user's scope covers every zone."""
    if user.is_system_admin or user.role in {
        RoleCode.GENERAL_SUPERVISOR,
        RoleCode.MANAGEMENT_VIEWER,
    }:
        return True
    if user.role == RoleCode.ASSISTANT_GENERAL_SUPERVISOR:
        return user.ags_assignments.filter(ACTIVE, all_zones=True).exists()
    return False


def assigned_zone_ids(user: User) -> set[int]:
    """Zone ids the user supervises (zone supervisor + non-all assistant)."""
    zone_ids = set(ZoneSupervisorAssignment.objects.filter(user=user, is_active=True).values_list("zone_id", flat=True))
    zone_ids |= set(
        AssistantGeneralSupervisorAssignment.objects.filter(
            user=user, is_active=True, all_zones=False, zone__isnull=False
        ).values_list("zone_id", flat=True)
    )
    return zone_ids


def visible_zones(user: User) -> QuerySet[Zone]:
    """Zones the user may read."""
    if _sees_all_zones(user):
        return Zone.objects.all()
    return Zone.objects.filter(pk__in=assigned_zone_ids(user))


def visible_sites(user: User) -> QuerySet[Site]:
    """Sites the user may read (active sites only)."""
    if _sees_all_zones(user):
        return Site.objects.all()
    if user.role == RoleCode.SITE_SUPERVISOR:
        return Site.objects.filter(supervisor_assignments__user=user, supervisor_assignments__is_active=True).distinct()
    return Site.objects.filter(zone_id__in=assigned_zone_ids(user))


def supervised_sites(user: User) -> QuerySet[Site]:
    """Sites the user has management (write) capacity over."""
    if user.is_system_admin or user.role in {
        RoleCode.GENERAL_SUPERVISOR,
        RoleCode.ASSISTANT_GENERAL_SUPERVISOR,
    }:
        if user.role == RoleCode.ASSISTANT_GENERAL_SUPERVISOR and not _sees_all_zones(user):
            return Site.objects.filter(zone_id__in=assigned_zone_ids(user))
        return Site.objects.all()
    if user.is_management_viewer:
        return Site.objects.none()
    if user.role == RoleCode.SITE_SUPERVISOR:
        return Site.objects.filter(supervisor_assignments__user=user, supervisor_assignments__is_active=True).distinct()
    if user.role == RoleCode.ZONE_SUPERVISOR:
        return Site.objects.filter(zone_id__in=assigned_zone_ids(user))
    return Site.objects.none()


def site_in_user_scope(user: User, site_id: int | str) -> bool:
    """True when the user may read the given site."""
    return visible_sites(user).filter(pk=site_id).exists()


def active_site_supervisor_ids(site_id: int) -> set[int]:
    """User ids of active supervisors for a site."""
    return set(
        SiteSupervisorAssignment.objects.filter(site_id=site_id, is_active=True).values_list("user_id", flat=True)
    )
