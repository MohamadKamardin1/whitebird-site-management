"""Assignment permission policies.

These decide whether a user may view/edit an assignment or assign a cleaner,
and are the only place such rules live (routers call them, never re-implement).
"""

from __future__ import annotations

from django.db.models import QuerySet

from apps.accounts.models import User

from .models import Cleaner, CleanerSiteAssignment, Site
from .scoping import site_in_user_scope, visible_sites


def can_view_assignment(user: User, assignment: CleanerSiteAssignment) -> bool:
    """Read access follows the user's visible site scope."""
    if user.is_system_admin:
        return True
    return site_in_user_scope(user, assignment.site_id)


def can_edit_assignment(user: User, assignment: CleanerSiteAssignment) -> bool:
    """Write access requires management capacity over the assignment's site."""
    if user.is_system_admin:
        return True
    return user_can_manage_site_here(user, assignment.site_id)


def can_assign_cleaner(user: User, site: Site, cleaner: Cleaner) -> bool:
    """A user may assign a cleaner only to a site they manage."""
    return user_can_manage_site_here(user, site.pk)


def visible_sites_for_user(user: User) -> QuerySet[Site]:
    """Visible sites queryset for scoping list endpoints."""
    return visible_sites(user)


def user_can_manage_site_here(user: User, site_id: int | str) -> bool:
    """Delegate to the shared write-capacity check (avoids circular imports)."""
    from apps.accounts.permissions import user_can_manage_site  # noqa: PLC0415

    return user_can_manage_site(user, site_id)
