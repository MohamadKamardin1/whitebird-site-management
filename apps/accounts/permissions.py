"""Role-based authorization primitives.

Authorization rules are enforced in services/routers, never in models.
The priority order mirrors a least-privilege posture:

* superusers pass everything;
* ADMIN users pass everything;
* MANAGER/STAFF/VIEWER are restricted to the sites they are assigned to.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable

from apps.sites.models import AssignmentRole

from .models import Role, User


def role_required(*roles: Role) -> Callable[[User], bool]:
    """Return a predicate granting access only to the given roles (or admins)."""

    allowed = {role.value for role in roles}

    def predicate(user: User) -> bool:
        return user.is_superuser or user.role in allowed

    return predicate


def user_can_manage_site(user: User, site_id: int | str) -> bool:
    """Return whether the user may write to the given site.

    Admins may manage everything. Other users need an explicit assignment
    *and* a managing capacity: either a platform MANAGER role or a
    site-manager assignment.
    """
    if user.is_admin:
        return True
    assignment = user.staff_assignments.filter(site_id=site_id).first()
    if assignment is None:
        return False
    return user.role == Role.MANAGER or assignment.role == AssignmentRole.SITE_MANAGER


def user_site_ids(user: User) -> Iterable[int]:
    """Ids of sites the user can see when their role is site-scoped."""
    if user.is_admin:
        return ()
    return tuple(user.staff_assignments.values_list("site_id", flat=True))
