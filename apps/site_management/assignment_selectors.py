"""Assignment & scheduling read selectors (optimised for attendance generation).

Selectors never mutate state and are N+1-free: relations are loaded with
``select_related``/``prefetch_related`` so callers can render schedules and
attendance without additional queries.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from django.db.models import Q, QuerySet

from apps.accounts.models import User

from .models import (
    CleanerAreaSchedule,
    CleanerShiftAssignment,
    CleanerSiteAssignment,
)
from .scoping import visible_sites


@dataclass(frozen=True)
class AssignmentFilter:
    cleaner_id: int | None = None
    site_id: int | None = None
    status: str | None = None
    assignment_type: str | None = None
    search: str | None = None


def assignment_list_queryset(user: User, spec: AssignmentFilter) -> QuerySet[CleanerSiteAssignment]:
    """Assignments visible to the user, filtered and annotated for listing."""
    qs: QuerySet[CleanerSiteAssignment] = CleanerSiteAssignment.objects.select_related("cleaner", "site", "assigned_by")
    if not user.is_system_admin:
        qs = qs.filter(site__in=visible_sites(user))
    if spec.cleaner_id:
        qs = qs.filter(cleaner_id=spec.cleaner_id)
    if spec.site_id:
        qs = qs.filter(site_id=spec.site_id)
    if spec.status:
        qs = qs.filter(status=spec.status)
    if spec.assignment_type:
        qs = qs.filter(assignment_type=spec.assignment_type)
    if spec.search:
        qs = qs.filter(Q(cleaner__first_name__icontains=spec.search) | Q(cleaner__last_name__icontains=spec.search))
    return qs


def get_assignment_or_none(assignment_id: int) -> CleanerSiteAssignment | None:
    return (
        CleanerSiteAssignment.objects.select_related("cleaner", "site", "assigned_by")
        .prefetch_related("shift_assignments__shift", "area_schedules__site_area", "area_schedules__operational_role")
        .filter(pk=assignment_id)
        .first()
    )


def assignment_shift_assignments(assignment_id: int) -> list[CleanerShiftAssignment]:
    return list(
        CleanerShiftAssignment.objects.filter(assignment_id=assignment_id, is_active=True)
        .select_related("shift")
        .order_by("effective_from")
    )


def assignment_area_schedules(assignment_id: int, *, active_only: bool = True) -> list[CleanerAreaSchedule]:
    qs = CleanerAreaSchedule.objects.filter(assignment_id=assignment_id).select_related(
        "site_area", "operational_role", "shift"
    )
    if active_only:
        qs = qs.filter(is_active=True)
    return list(qs.order_by("date", "start_time"))


def site_daily_schedule(site_id: int, day: date, shift_id: int | None = None) -> list[CleanerAreaSchedule]:
    """All active area schedules for a site on a date.

    Single query with all relations loaded — ready for attendance generation.
    """
    qs = CleanerAreaSchedule.objects.filter(assignment__site_id=site_id, date=day, is_active=True).select_related(
        "assignment__cleaner", "assignment", "site_area", "operational_role", "shift"
    )
    if shift_id:
        qs = qs.filter(shift_id=shift_id)
    return list(qs.order_by("start_time", "site_area__area_name"))


def cleaner_schedule(cleaner_id: int, date_from: date, date_to: date) -> list[CleanerAreaSchedule]:
    """Active area schedules for a cleaner over a date range."""
    return list(
        CleanerAreaSchedule.objects.filter(
            assignment__cleaner_id=cleaner_id, date__gte=date_from, date__lte=date_to, is_active=True
        )
        .select_related("assignment__site", "site_area", "operational_role", "shift")
        .order_by("date", "start_time")
    )


def scheduled_cleaners_for_attendance(site_id: int, day: date, shift_id: int | None = None) -> list[dict[str, Any]]:
    """Optimised projection of scheduled cleaners for attendance generation.

    Returns one entry per active area schedule with the fields attendance
    needs (cleaner, site, shift, area, role, times) without ORM instances.
    """
    qs = (
        CleanerAreaSchedule.objects.filter(
            assignment__site_id=site_id,
            assignment__status__in=["active", "suspended"],
            date=day,
            is_active=True,
        )
        .select_related("assignment__cleaner", "assignment", "site_area", "operational_role", "shift")
        .order_by("start_time")
    )
    if shift_id:
        qs = qs.filter(shift_id=shift_id)
    rows: list[dict[str, Any]] = []
    for schedule in qs:
        rows.append(
            {
                "schedule_id": schedule.pk,
                "cleaner_id": schedule.assignment.cleaner_id,
                "cleaner_name": schedule.assignment.cleaner.full_name,
                "assignment_id": schedule.assignment_id,
                "assignment_status": schedule.assignment.status,
                "site_id": schedule.assignment.site_id,
                "shift_id": schedule.shift_id,
                "shift_name": schedule.shift.shift_name if schedule.shift else None,
                "area_id": schedule.site_area_id,
                "area_name": schedule.site_area.area_name,
                "role_id": schedule.operational_role_id,
                "role_name": schedule.operational_role.name,
                "start_time": schedule.start_time.isoformat(),
                "end_time": schedule.end_time.isoformat(),
                "crosses_midnight": schedule.crosses_midnight,
            }
        )
    return rows
