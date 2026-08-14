"""Accounts selectors — read-only data access."""

from __future__ import annotations

from django.db.models import Count, QuerySet

from .models import ApiToken, RoleCode, User
from .rbac import group_permission_codenames

#: Backend permission codename -> mobile client action name.
_ACTION_BY_CODENAME = {
    "assign_job": "assign_jobs",
    "verify_job": "verify_jobs",
    "review_zone_report": "review_zone_report",
    "review_assistant_report": "review_assistant_report",
    "approve_general_report": "review_general_report",
    "submit_site_report": "review_site_report",
    "manage_site_configuration": "manage_configuration",
    "export_site_management_data": "export_data",
    "approve_trainee": "approve_trainees",
    "view_sensitive_cleaner_documents": "view_cleaner_documents",
}

#: Mobile client action -> client resource bucket.
_RESOURCE_BY_ACTION = {
    "edit_site": "sites",
    "record_attendance": "attendance",
    "review_site_report": "reports",
    "review_zone_report": "reports",
    "review_assistant_report": "reports",
    "review_general_report": "reports",
    "assign_jobs": "jobs",
    "verify_jobs": "jobs",
    "manage_configuration": "configuration",
    "export_data": "exports",
}

_ADMIN_ACTIONS = frozenset(
    {
        "edit_site",
        "record_attendance",
        "review_site_report",
        "review_zone_report",
        "review_assistant_report",
        "review_general_report",
        "assign_jobs",
        "verify_jobs",
        "manage_configuration",
        "export_data",
    }
)


def list_active_tokens(user: User) -> QuerySet[ApiToken]:
    return user.api_tokens.filter(is_active=True)


def user_stats(user: User) -> dict[str, object]:
    """Aggregate counts for the authenticated user's dashboard."""
    assignments = user.staff_assignments.select_related("site")
    return {
        "username": user.get_username(),
        "role": user.role,
        "site_count": assignments.count(),
        "sites": [{"id": assignment.site_id, "name": assignment.site.name} for assignment in assignments],
    }


def user_permissions(user: User) -> dict[str, object]:
    """Return the mobile client permission set for an authenticated user.

    Mirrors the ``PermissionSet`` contract expected by the Expo app: a list of
    action names, the resource buckets they apply to, and the site/zone scopes
    the user can access.
    """
    if user.is_superuser or user.role == RoleCode.SYSTEM_ADMIN:
        actions: set[str] = set(_ADMIN_ACTIONS)
        resources: set[str] = set(_RESOURCE_BY_ACTION.values())
    else:
        actions = {
            _ACTION_BY_CODENAME[codename]
            for _, codename in group_permission_codenames(RoleCode(user.role))
            if codename in _ACTION_BY_CODENAME
        }
        if ("site_management", "change_site") in group_permission_codenames(RoleCode(user.role)):
            actions.add("edit_site")
        if user.role != RoleCode.MANAGEMENT_VIEWER:
            actions.add("record_attendance")
        resources = {resource for action in actions if (resource := _RESOURCE_BY_ACTION.get(action))}

    site_ids = [str(assignment.site_id) for assignment in user.staff_assignments.only("site_id")]
    return {
        "actions": sorted(actions),
        "resources": sorted(resources),
        "site_ids": site_ids,
        "zone_ids": [],
    }


def staff_directory() -> list[User]:
    return list(
        User.objects.filter(is_active=True)
        .annotate(assignment_count=Count("staff_assignments"))
        .order_by("last_name", "first_name")
    )
