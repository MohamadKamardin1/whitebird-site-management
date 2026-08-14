"""Streaming CSV export services.

Every export respects the caller's visible-site scope, streams rows with
``QuerySet.iterator`` (never loading the full result set), sanitises cells so
spreadsheet-formula injection (``=``/``+``/``-``/``@``) is neutralised, honours
a constance max-row cap, and writes an audit entry.
"""

from __future__ import annotations

import datetime
from collections.abc import Iterator
from typing import Any

from constance import config
from django.utils import timezone

from apps.accounts.models import User
from apps.core.models import AuditLog
from apps.core.services import record_audit

from .models import AttendanceRecord, Cleaner, DailySiteReport, Issue, Job
from .scoping import visible_sites

_DANGEROUS_PREFIXES = ("=", "+", "-", "@")


def _csv_field(value: Any) -> str:
    text = "" if value is None else str(value)
    if text and text[0] in _DANGEROUS_PREFIXES:
        text = "'" + text
    escaped = text.replace('"', '""')
    return f'"{escaped}"'


def _csv_line(fields: list[Any]) -> str:
    return ",".join(_csv_field(field) for field in fields) + "\n"


def _export_rows(queryset: Any, columns: list[str], headers: list[str], max_rows: int | None = None) -> Iterator[str]:
    cap = max_rows if max_rows is not None else int(config.EXPORT_MAX_ROWS)
    yield _csv_line(headers)
    emitted = 0
    for row in queryset.values(*columns).iterator(chunk_size=500):
        if emitted >= cap:
            break
        yield _csv_line([row.get(column) for column in columns])
        emitted += 1


def _audit_export(user: User, model_name: str) -> None:
    record_audit(
        action=AuditLog.Action.FILE_DOWNLOAD,
        actor=user,
        model_name=f"site_management.{model_name}",
        object_id="",
        object_repr=f"CSV export: {model_name}",
        summary=f"Exported {model_name} data",
    )


def _scoped(model: Any, user: User, site_path: str = "site") -> Any:
    if user.is_system_admin:
        return model.objects.all()
    qs = model.objects.filter(**{f"{site_path}__in": visible_sites(user)})
    return qs.distinct() if site_path != "site" else qs


def attendance_export_rows(
    user: User,
    day: datetime.date | None = None,
    date_from: datetime.date | None = None,
    date_to: datetime.date | None = None,
) -> tuple[str, Iterator[str]]:
    qs = _scoped(AttendanceRecord, user).select_related("site", "cleaner", "shift")
    if date_from:
        qs = qs.filter(attendance_date__gte=date_from)
    if date_to:
        qs = qs.filter(attendance_date__lte=date_to)
    if day:
        qs = qs.filter(attendance_date=day)
    columns = [
        "attendance_date",
        "site__name",
        "cleaner__last_name",
        "cleaner__first_name",
        "status",
        "check_in_time",
        "check_out_time",
    ]
    headers = ["date", "site", "last_name", "first_name", "status", "check_in", "check_out"]
    _audit_export(user, "attendancerecord")
    return f"attendance-{date_from or day or timezone.localdate()}.csv", _export_rows(qs, columns, headers)


def cleaner_export_rows(user: User) -> tuple[str, Iterator[str]]:
    qs = _scoped(Cleaner, user, site_path="site_assignments__site")
    columns = ["first_name", "last_name", "gender", "status", "registration_date", "living_location"]
    headers = ["first_name", "last_name", "gender", "status", "registration_date", "living_location"]
    _audit_export(user, "cleaner")
    return f"cleaners-{timezone.localdate()}.csv", _export_rows(qs, columns, headers)


def issue_export_rows(user: User) -> tuple[str, Iterator[str]]:
    qs = _scoped(Issue, user)
    columns = ["id", "title", "site__name", "issue_category", "priority", "status", "created_at"]
    headers = ["id", "title", "site", "category", "priority", "status", "created_at"]
    _audit_export(user, "issue")
    return f"issues-{timezone.localdate()}.csv", _export_rows(qs, columns, headers)


def job_export_rows(user: User) -> tuple[str, Iterator[str]]:
    qs = _scoped(Job, user)
    columns = ["job_title", "site__name", "priority", "status", "due_date", "assigned_to_user__email"]
    headers = ["job_title", "site", "priority", "status", "due_date", "assignee_email"]
    _audit_export(user, "job")
    return f"jobs-{timezone.localdate()}.csv", _export_rows(qs, columns, headers)


def report_export_rows(user: User, report_date: datetime.date | None = None) -> tuple[str, Iterator[str]]:
    qs = _scoped(DailySiteReport, user)
    if report_date:
        qs = qs.filter(report_date=report_date)
    columns = ["report_date", "site__name", "status", "submitted_at", "attendance_summary", "issues_summary"]
    headers = ["report_date", "site", "status", "submitted_at", "attendance_summary", "issues_summary"]
    _audit_export(user, "dailysitereport")
    return f"reports-{report_date or timezone.localdate()}.csv", _export_rows(qs, columns, headers)
