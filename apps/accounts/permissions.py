"""Role-based authorization primitives.

Authorization rules are enforced in routers/services, never in models. The
priority order mirrors a least-privilege posture:

* superusers and SYSTEM_ADMIN pass everything;
* GENERAL_SUPERVISOR manages everything;
* supervisor roles are restricted to their active assignments/zones;
* MANAGEMENT_VIEWER is read-only.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable

from .models import SUPERVISOR_ROLES, RoleCode, User


def role_required(*roles: RoleCode) -> Callable[[User], bool]:
    """Return a predicate granting access only to the given roles (or admins)."""

    allowed = {role.value for role in roles}

    def predicate(user: User) -> bool:
        return user.is_superuser or user.role in allowed

    return predicate


def management_required(user: User) -> bool:
    """True for system admins and any supervisor role (not viewers)."""
    return user.is_system_admin or user.role in SUPERVISOR_ROLES


def user_can_manage_site(user: User, site_id: int | str) -> bool:
    """Return whether the user may write to the given site.

    System admins and the general supervisor manage everything; site
    supervisors manage sites they are actively assigned to; zone supervisors
    and assistant general supervisors manage sites inside their scope.
    Management viewers never write.
    """
    if user.is_system_admin or user.role == RoleCode.GENERAL_SUPERVISOR:
        return True
    if user.is_management_viewer:
        return False
    if user.role == RoleCode.SITE_SUPERVISOR:
        from apps.site_management.models import SiteSupervisorAssignment  # noqa: PLC0415

        return SiteSupervisorAssignment.objects.filter(user=user, site_id=site_id, is_active=True).exists()
    if user.role in {RoleCode.ZONE_SUPERVISOR, RoleCode.ASSISTANT_GENERAL_SUPERVISOR}:
        from apps.site_management.scoping import site_in_user_scope  # noqa: PLC0415

        return site_in_user_scope(user, site_id)
    return False


def user_site_ids(user: User) -> Iterable[int]:
    """Ids of sites the user can see when their role is site-scoped."""
    if user.is_system_admin:
        return ()
    from apps.site_management.scoping import visible_sites  # noqa: PLC0415

    return tuple(visible_sites(user).values_list("pk", flat=True))
