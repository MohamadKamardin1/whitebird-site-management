"""Accounts selectors — read-only data access."""

from __future__ import annotations

from django.db.models import Count, QuerySet

from .models import ApiToken, User


def list_active_tokens(user: User) -> QuerySet[ApiToken]:
    return user.api_tokens.filter(is_active=True)


def user_stats(user: User) -> dict[str, object]:
    """Aggregate counts for the authenticated user's dashboard."""
    assignments = user.staff_assignments.select_related("site")
    return {
        "username": user.get_username(),
        "role": user.role,
        "site_count": assignments.count(),
        "sites": [
            {"id": assignment.site_id, "name": assignment.site.name}
            for assignment in assignments
        ],
    }


def staff_directory() -> list[User]:
    return list(
        User.objects.filter(is_active=True)
        .annotate(assignment_count=Count("staff_assignments"))
        .order_by("last_name", "first_name")
    )
