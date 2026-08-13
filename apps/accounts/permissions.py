"""Role-based authorization primitives.

Authorization rules are enforced in routers/services, never in models. The
priority order mirrors a least-privilege posture:

* superusers pass everything;
* SYSTEM_ADMIN passes everything;
* supervisor roles are restricted to the sites they are assigned to;
* MANAGEMENT_VIEWER is read-only.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable

from apps.site_management.models import AssignmentRole

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

    System admins manage everything. Other users need an explicit assignment
    *and* a managing capacity: any supervisor role or a site-manager
    assignment.
    """
    if user.is_system_admin:
        return True
    assignment = user.staff_assignments.filter(site_id=site_id).first()
    if assignment is None:
        return False
    return user.role in SUPERVISOR_ROLES or assignment.role == AssignmentRole.SITE_MANAGER


def user_site_ids(user: User) -> Iterable[int]:
    """Ids of sites the user can see when their role is site-scoped."""
    if user.is_system_admin:
        return ()
    return tuple(user.staff_assignments.values_list("site_id", flat=True))
