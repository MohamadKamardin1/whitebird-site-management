"""Attendance read selectors (N+1-free, role-scoped, attendance-ready)."""

from __future__ import annotations

import datetime
from dataclasses import dataclass

from django.db.models import Count, QuerySet

from apps.accounts.models import User

from .models import AttendanceRecord, AttendanceStatus, Site
from .scoping import visible_sites


def _scoped_site_ids(user: User) -> QuerySet[Site]:
    return visible_sites(user)


def attendance_daily_sheet(
    user: User, site_id: int, day: datetime.date, shift_id: int | None = None
) -> list[AttendanceRecord]:
    """The day's attendance records for a site (single query)."""
    qs = AttendanceRecord.objects.filter(site_id=site_id, attendance_date=day).select_related(
        "cleaner", "site", "shift"
    )
    if shift_id:
        qs = qs.filter(shift_id=shift_id)
    return list(qs.order_by("cleaner__last_name", "shift__shift_name"))


@dataclass(frozen=True)
class AttendanceFilter:
    site_id: int | None = None
    date: datetime.date | None = None
    date_from: datetime.date | None = None
    date_to: datetime.date | None = None
    shift_id: int | None = None
    cleaner_id: int | None = None
    status: str | None = None
    review_status: str | None = None


def attendance_history_queryset(user: User, spec: AttendanceFilter) -> QuerySet[AttendanceRecord]:
    """Filtered attendance history scoped to the user's visible sites."""
    qs: QuerySet[AttendanceRecord] = AttendanceRecord.objects.select_related("cleaner", "site", "shift")
    if not user.is_system_admin:
        qs = qs.filter(site__in=_scoped_site_ids(user))
    if spec.site_id:
        qs = qs.filter(site_id=spec.site_id)
    if spec.date:
        qs = qs.filter(attendance_date=spec.date)
    if spec.date_from:
        qs = qs.filter(attendance_date__gte=spec.date_from)
    if spec.date_to:
        qs = qs.filter(attendance_date__lte=spec.date_to)
    if spec.shift_id:
        qs = qs.filter(shift_id=spec.shift_id)
    if spec.cleaner_id:
        qs = qs.filter(cleaner_id=spec.cleaner_id)
    if spec.status:
        qs = qs.filter(status=spec.status)
    if spec.review_status:
        qs = qs.filter(review_status=spec.review_status)
    return qs


def attendance_summary(user: User, spec: AttendanceFilter) -> dict[str, int | float]:
    """Aggregate counts for a filtered set of attendance records (single query)."""
    qs = attendance_history_queryset(user, spec)
    grouped = {item["status"]: item["n"] for item in qs.values("status").order_by().annotate(n=Count("pk"))}
    counts: dict[str, int | float] = {
        "total_scheduled": sum(grouped.values()),
        "present": grouped.get("present", 0),
        "late": grouped.get("late", 0),
        "absent": grouped.get("absent", 0),
        "sick": grouped.get("sick", 0),
        "leave": grouped.get("leave", 0),
        "permission": grouped.get("permission", 0),
        "off": grouped.get("off", 0),
    }
    attended = counts["present"] + counts["late"]
    denominator = attended + counts["absent"]
    rate = round((attended / denominator) * 100, 2) if denominator else 0.0
    counts["attendance_rate"] = rate
    return counts


def missing_attendance_sites(user: User, day: datetime.date) -> list[dict[str, object]]:
    """Visible sites that still have unsubmitted (or missing) attendance for a day."""
    result: list[dict[str, object]] = []
    for site in _scoped_site_ids(user):
        records = AttendanceRecord.objects.filter(site=site, attendance_date=day)
        if records.exists():
            open_count = records.filter(review_status__in=["draft", "returned"]).count()
            if open_count:
                result.append(
                    {
                        "site_id": site.pk,
                        "site_name": site.name,
                        "record_count": records.count(),
                        "open_records": open_count,
                    }
                )
        else:
            result.append({"site_id": site.pk, "site_name": site.name, "record_count": 0, "open_records": 0})
    return result


def attendance_exceptions(user: User, spec: AttendanceFilter) -> list[AttendanceRecord]:
    """Records with abnormal statuses (late/absent/sick/leave/permission)."""
    qs = attendance_history_queryset(
        user,
        AttendanceFilter(
            site_id=spec.site_id,
            date=spec.date,
            date_from=spec.date_from,
            date_to=spec.date_to,
            shift_id=spec.shift_id,
            cleaner_id=spec.cleaner_id,
        ),
    )
    qs = qs.filter(
        status__in=[
            AttendanceStatus.LATE,
            AttendanceStatus.ABSENT,
            AttendanceStatus.SICK,
            AttendanceStatus.LEAVE,
            AttendanceStatus.PERMISSION,
        ]
    )
    return list(qs.order_by("attendance_date")[:200])
