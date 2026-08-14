"""Role-scoped dashboard KPI and chart selectors.

Every metric is scoped to the caller's ``visible_sites`` and computed with a
small number of aggregated queries (never per-row Python loops). Results are
cached under versioned, namespaced keys; invalidate with
:func:`invalidate_dashboard_caches`.
"""

from __future__ import annotations

import datetime
from typing import Any

from django.conf import settings
from django.db.models import Count, F, Q

from apps.accounts.models import User
from apps.core.cache import cached_or, invalidate_prefix

from .models import (
    AttendanceRecord,
    AttendanceStatus,
    Cleaner,
    CleanerStatus,
    DailySiteReport,
    Inspection,
    Issue,
    Job,
    JobStatus,
    SiteReportStatus,
    StoreItem,
    TraineeProgram,
    TraineeProgramStatus,
)
from .scoping import visible_sites

DASHBOARD_PREFIX = "dash"
DASHBOARD_VERSION = "v1"


def _visible_sites_q(user: User) -> Q:
    """Q() restricting by ``site__in`` to the user's visible sites (admin: all)."""
    if user.is_system_admin:
        return Q()
    return Q(site__in=visible_sites(user))


def _cleaner_scope(user: User) -> Q:
    """Cleaners must be scoped through their site assignments."""
    if user.is_system_admin:
        return Q()
    return Q(site_assignments__site__in=visible_sites(user))


def _store_item_scope(user: User) -> Q:
    """Store items are scoped through their store's site."""
    if user.is_system_admin:
        return Q()
    return Q(store__site__in=visible_sites(user))


def _dashboard_cache_ttl() -> int:
    return int(getattr(settings, "DASHBOARD_CACHE_TTL_SECONDS", 300))


def dashboard_kpis(user: User, day: datetime.date | None = None) -> dict[str, Any]:
    """Role-scoped KPI summary for a date (cached per user + date)."""
    day = day or datetime.date.today()

    def _compute() -> dict[str, Any]:
        scope = _visible_sites_q(user)

        active_sites = visible_sites(user).filter(is_active=True).count()

        active_cleaners = (
            Cleaner.objects.filter(status=CleanerStatus.ACTIVE).filter(_cleaner_scope(user)).distinct().count()
        )

        trainees = TraineeProgram.objects.filter(
            status__in=[TraineeProgramStatus.IN_TRAINING, TraineeProgramStatus.EXTENDED]
        ).filter(scope)
        trainees_in_training = trainees.count()

        attendance = AttendanceRecord.objects.filter(attendance_date=day).filter(scope)
        att_counts = {row["status"]: row["n"] for row in attendance.values("status").order_by().annotate(n=Count("pk"))}
        present = att_counts.get(AttendanceStatus.PRESENT, 0)
        late = att_counts.get(AttendanceStatus.LATE, 0)
        absent = att_counts.get(AttendanceStatus.ABSENT, 0)
        denominator = present + late + absent
        attendance_rate = round(((present + late) / denominator) * 100, 2) if denominator else 0.0

        open_issues = Issue.objects.exclude(status="closed").filter(scope).count()
        escalated_issues = Issue.objects.filter(is_escalated=True).filter(scope).count()

        overdue_jobs = (
            Job.objects.filter(
                due_date__lt=day,
                status__in=[JobStatus.OPEN, JobStatus.ASSIGNED, JobStatus.IN_PROGRESS, JobStatus.REOPENED],
            )
            .filter(scope)
            .count()
        )

        low_stock_items = (
            StoreItem.objects.filter(current_stock__lte=F("minimum_stock_level"))
            .filter(_store_item_scope(user))
            .count()
        )

        window_start = day - datetime.timedelta(days=30)
        inspections = Inspection.objects.exclude(status="draft").filter(inspection_date__gte=window_start).filter(scope)
        insp_counts = {
            row["overall_status"]: row["n"]
            for row in inspections.values("overall_status").order_by().annotate(n=Count("pk"))
        }
        insp_total = sum(insp_counts.values())
        insp_pass = insp_counts.get("passed", 0)
        inspections_pass_rate = round((insp_pass / insp_total) * 100, 2) if insp_total else 0.0

        submitted_today = set(DailySiteReport.objects.filter(report_date=day).values_list("site_id", flat=True))
        visible_ids = set(visible_sites(user).values_list("pk", flat=True))
        missing_site_reports = len(visible_ids - submitted_today)

        pending_reports = (
            DailySiteReport.objects.filter(
                report_date=day,
                status__in=[SiteReportStatus.DRAFT, SiteReportStatus.SUBMITTED, SiteReportStatus.RETURNED],
            )
            .filter(scope)
            .count()
        )

        return {
            "active_sites": active_sites,
            "active_cleaners": active_cleaners,
            "trainees_in_training": trainees_in_training,
            "attendance_rate": attendance_rate,
            "absences_today": absent,
            "late_today": late,
            "open_issues": open_issues,
            "overdue_jobs": overdue_jobs,
            "low_stock_items": low_stock_items,
            "inspections_pass_rate": inspections_pass_rate,
            "missing_site_reports": missing_site_reports,
            "pending_reports": pending_reports,
            "escalated_issues": escalated_issues,
        }

    return cached_or(
        DASHBOARD_PREFIX, (DASHBOARD_VERSION, "kpis", day.isoformat(), user.pk), _compute, _dashboard_cache_ttl()
    )


# --------------------------------------------------------------------------- #
# Charts
# --------------------------------------------------------------------------- #


def attendance_trend(user: User, days: int = 7) -> dict[str, Any]:
    """Daily present/late/absent counts for the last N days (scoped)."""
    days = 7 if days not in (7, 30) else days
    today = datetime.date.today()
    start = today - datetime.timedelta(days=days - 1)
    scope = _visible_sites_q(user)

    def _compute() -> dict[str, Any]:
        rows = (
            AttendanceRecord.objects.filter(attendance_date__gte=start, attendance_date__lte=today)
            .filter(scope)
            .values("attendance_date", "status")
            .order_by("attendance_date")
            .annotate(n=Count("pk"))
        )
        labels: list[str] = []
        present: list[int] = []
        late: list[int] = []
        absent: list[int] = []
        by_day: dict[str, dict[str, int]] = {}
        for r in rows:
            key = r["attendance_date"].isoformat()
            bucket = by_day.setdefault(key, {"present": 0, "late": 0, "absent": 0})
            if r["status"] == AttendanceStatus.PRESENT:
                bucket["present"] += r["n"]
            elif r["status"] == AttendanceStatus.LATE:
                bucket["late"] += r["n"]
            elif r["status"] == AttendanceStatus.ABSENT:
                bucket["absent"] += r["n"]
        for offset in range(days):
            key = (start + datetime.timedelta(days=offset)).isoformat()
            labels.append(key)
            bucket = by_day.get(key, {"present": 0, "late": 0, "absent": 0})
            present.append(bucket["present"])
            late.append(bucket["late"])
            absent.append(bucket["absent"])
        return {"labels": labels, "present": present, "late": late, "absent": absent}

    return cached_or(
        DASHBOARD_PREFIX, (DASHBOARD_VERSION, "attendance-trend", days, user.pk), _compute, _dashboard_cache_ttl()
    )


def issues_by_category(user: User) -> dict[str, Any]:
    """Open issue counts grouped by category (scoped)."""
    scope = _visible_sites_q(user)

    def _compute() -> dict[str, Any]:
        rows = (
            Issue.objects.exclude(status="closed")
            .filter(scope)
            .values("issue_category")
            .order_by()
            .annotate(n=Count("pk"))
        )
        return {"labels": [r["issue_category"] for r in rows], "values": [r["n"] for r in rows]}

    return cached_or(
        DASHBOARD_PREFIX, (DASHBOARD_VERSION, "issues-by-category", user.pk), _compute, _dashboard_cache_ttl()
    )


def issues_by_site(user: User) -> dict[str, Any]:
    """Open issue counts grouped by site (scoped)."""
    scope = _visible_sites_q(user)

    def _compute() -> dict[str, Any]:
        rows = (
            Issue.objects.exclude(status="closed").filter(scope).values("site__name").order_by().annotate(n=Count("pk"))
        )
        return {"labels": [r["site__name"] for r in rows], "values": [r["n"] for r in rows]}

    return cached_or(DASHBOARD_PREFIX, (DASHBOARD_VERSION, "issues-by-site", user.pk), _compute, _dashboard_cache_ttl())


def inspection_trend(user: User, days: int = 7) -> dict[str, Any]:
    """Daily pass/fail/needs-attention inspection counts for the last N days."""
    days = 7 if days not in (7, 30) else days
    today = datetime.date.today()
    start = today - datetime.timedelta(days=days - 1)
    scope = _visible_sites_q(user)

    def _compute() -> dict[str, Any]:
        rows = (
            Inspection.objects.exclude(status="draft")
            .filter(inspection_date__gte=start, inspection_date__lte=today)
            .filter(scope)
            .values("inspection_date", "overall_status")
            .order_by("inspection_date")
            .annotate(n=Count("pk"))
        )
        by_day: dict[str, dict[str, int]] = {}
        for r in rows:
            bucket = by_day.setdefault(
                r["inspection_date"].isoformat(), {"passed": 0, "failed": 0, "needs_attention": 0}
            )
            if r["overall_status"] in bucket:
                bucket[r["overall_status"]] += r["n"]
        labels: list[str] = []
        passed: list[int] = []
        failed: list[int] = []
        needs: list[int] = []
        for offset in range(days):
            key = (start + datetime.timedelta(days=offset)).isoformat()
            labels.append(key)
            bucket = by_day.get(key, {"passed": 0, "failed": 0, "needs_attention": 0})
            passed.append(bucket["passed"])
            failed.append(bucket["failed"])
            needs.append(bucket["needs_attention"])
        return {"labels": labels, "passed": passed, "failed": failed, "needs_attention": needs}

    return cached_or(
        DASHBOARD_PREFIX, (DASHBOARD_VERSION, "inspection-trend", days, user.pk), _compute, _dashboard_cache_ttl()
    )


def jobs_open_vs_closed(user: User) -> dict[str, Any]:
    """Open vs closed job counts (scoped)."""
    scope = _visible_sites_q(user)

    def _compute() -> dict[str, Any]:
        open_count = Job.objects.exclude(status=JobStatus.CLOSED).filter(scope).count()
        closed_count = Job.objects.filter(status=JobStatus.CLOSED).filter(scope).count()
        return {"labels": ["Open", "Closed"], "values": [open_count, closed_count]}

    return cached_or(
        DASHBOARD_PREFIX, (DASHBOARD_VERSION, "jobs-open-vs-closed", user.pk), _compute, _dashboard_cache_ttl()
    )


def low_stock_by_site(user: User) -> dict[str, Any]:
    """Low-stock item counts grouped by site (scoped)."""

    def _compute() -> dict[str, Any]:
        rows = (
            StoreItem.objects.filter(current_stock__lte=F("minimum_stock_level"))
            .filter(_store_item_scope(user))
            .values("store__site__name")
            .order_by()
            .annotate(n=Count("pk"))
        )
        return {"labels": [r["store__site__name"] for r in rows], "values": [r["n"] for r in rows]}

    return cached_or(
        DASHBOARD_PREFIX, (DASHBOARD_VERSION, "low-stock-by-site", user.pk), _compute, _dashboard_cache_ttl()
    )


def report_status_by_site(user: User, day: datetime.date | None = None) -> dict[str, Any]:
    """Site report submission status counts for a date (scoped)."""
    day = day or datetime.date.today()
    scope = _visible_sites_q(user)

    def _compute() -> dict[str, Any]:
        rows = (
            DailySiteReport.objects.filter(report_date=day)
            .filter(scope)
            .values("status")
            .order_by()
            .annotate(n=Count("pk"))
        )
        return {"labels": [r["status"] for r in rows], "values": [r["n"] for r in rows]}

    return cached_or(
        DASHBOARD_PREFIX,
        (DASHBOARD_VERSION, "report-status", day.isoformat(), user.pk),
        _compute,
        _dashboard_cache_ttl(),
    )


def all_dashboard_charts(user: User, days: int = 7) -> dict[str, Any]:
    """Bundle every chart dataset for a dashboard page render."""
    return {
        "attendance_trend": attendance_trend(user, days),
        "issues_by_category": issues_by_category(user),
        "issues_by_site": issues_by_site(user),
        "inspection_trend": inspection_trend(user, days),
        "jobs_open_vs_closed": jobs_open_vs_closed(user),
        "low_stock_by_site": low_stock_by_site(user),
        "report_status_by_site": report_status_by_site(user),
    }


def invalidate_dashboard_caches(user: User | None = None) -> None:
    """Best-effort bulk invalidation of the dashboard cache family."""
    invalidate_prefix(DASHBOARD_PREFIX)
