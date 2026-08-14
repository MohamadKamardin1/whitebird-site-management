"""Reporting chain read selectors (role-scoped)."""

from __future__ import annotations

import datetime
from typing import Any

from django.db.models import QuerySet
from django.utils import timezone

from apps.accounts.models import User
from apps.core.cache import cached_or

from .models import (
    AssistantGeneralSummaryReport,
    DailySiteReport,
    GeneralManagementReport,
    SiteReportStatus,
    ZoneSummaryReport,
)
from .scoping import visible_sites

REPORT_CACHE_PREFIX = "report"
_REPORT_CACHE_TTL = 600


def site_report_detail(site_id: int, day: datetime.date) -> DailySiteReport | None:
    """Single-row lookup used by write paths — always fresh (indexed)."""
    return DailySiteReport.objects.select_related("site", "created_by").filter(site_id=site_id, report_date=day).first()


def get_site_report_or_none(report_id: int) -> DailySiteReport | None:
    return DailySiteReport.objects.select_related("site", "created_by").filter(pk=report_id).first()


def zone_report_detail(zone_id: int, day: datetime.date) -> ZoneSummaryReport | None:
    return (
        ZoneSummaryReport.objects.select_related("zone", "zone_supervisor")
        .filter(zone_id=zone_id, report_date=day)
        .first()
    )


def get_zone_report_or_none(report_id: int) -> ZoneSummaryReport | None:
    return ZoneSummaryReport.objects.select_related("zone", "zone_supervisor").filter(pk=report_id).first()


def assistant_report_detail(day: datetime.date) -> AssistantGeneralSummaryReport | None:
    return (
        AssistantGeneralSummaryReport.objects.select_related("assistant_general_supervisor")
        .filter(report_date=day)
        .first()
    )


def get_assistant_report_or_none(report_id: int) -> AssistantGeneralSummaryReport | None:
    return (
        AssistantGeneralSummaryReport.objects.select_related("assistant_general_supervisor")
        .filter(pk=report_id)
        .first()
    )


def general_report_detail(day: datetime.date) -> GeneralManagementReport | None:
    return GeneralManagementReport.objects.select_related("general_supervisor").filter(report_date=day).first()


def get_general_report_or_none(report_id: int) -> GeneralManagementReport | None:
    return GeneralManagementReport.objects.select_related("general_supervisor").filter(pk=report_id).first()


def site_reports_for_day(user: User, day: datetime.date) -> QuerySet[DailySiteReport]:
    qs: QuerySet[DailySiteReport] = DailySiteReport.objects.select_related("site", "created_by").filter(report_date=day)
    if not user.is_system_admin:
        qs = qs.filter(site__in=visible_sites(user))
    return qs


def missing_site_reports(user: User, day: datetime.date) -> list[dict[str, Any]]:
    """Sites in the user's scope without a submitted site report for the day."""
    submitted_site_ids = set(DailySiteReport.objects.filter(report_date=day).values_list("site_id", flat=True))
    result: list[dict[str, Any]] = []
    for site in visible_sites(user).select_related("zone"):
        if site.pk not in submitted_site_ids:
            zone = site.zone
            result.append(
                {
                    "site_id": site.pk,
                    "site_name": site.name,
                    "zone_id": site.zone_id,
                    "zone_name": zone.name if zone else None,
                }
            )
    return result


def reporting_status_dashboard(user: User, day: datetime.date) -> dict[str, Any]:
    """Per-site report statuses plus the higher-report chain status for a day.

    Cached per user scope + date; report writes invalidate the ``report:``
    prefix family.
    """

    def _compute() -> dict[str, Any]:
        site_reports = site_reports_for_day(user, day)
        today = timezone.localdate()
        rows = [
            {
                "site_id": sr.site_id,
                "site_name": sr.site.name,
                "status": sr.status,
                "submitted_at": sr.submitted_at,
                "overdue": day < today and sr.status == SiteReportStatus.DRAFT,
            }
            for sr in site_reports
        ]
        missing = [
            {"site_id": m["site_id"], "site_name": m["site_name"], "zone_id": m["zone_id"], "zone_name": m["zone_name"]}
            for m in missing_site_reports(user, day)
        ]
        return {
            "report_date": day.isoformat(),
            "site_reports": rows,
            "missing_site_reports": missing,
            "zone_summary_status": (
                ZoneSummaryReport.objects.filter(report_date=day).values_list("status", flat=True).first()
            ),
            "assistant_summary_status": (
                AssistantGeneralSummaryReport.objects.filter(report_date=day).values_list("status", flat=True).first()
            ),
            "general_report_status": (
                GeneralManagementReport.objects.filter(report_date=day).values_list("status", flat=True).first()
            ),
        }

    return cached_or(REPORT_CACHE_PREFIX, ("status", day, user.pk), _compute, _REPORT_CACHE_TTL)
