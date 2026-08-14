"""Reporting chain services.

Implements the Site Supervisor → Zone → Assistant General → General → Management
report pipeline. Site reports aggregate real operational data (attendance,
store, inspections, trainees, issues); every submission stores an immutable
snapshot. All writes are transactional, audited and invalidate report caches;
each submission emits a domain event.
"""

from __future__ import annotations

import datetime
from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Avg, Count, QuerySet
from django.utils import timezone

from apps.accounts.models import User
from apps.core.cache import invalidate_prefix
from apps.core.models import AuditLog
from apps.core.services import model_data, publish_domain_event, record_audit

from .models import (
    AssistantGeneralSummaryReport,
    AssistantReportStatus,
    AttendanceRecord,
    DailySiteReport,
    GeneralManagementReport,
    GeneralReportStatus,
    Inspection,
    Issue,
    SiteReportStatus,
    StockMovement,
    StockMovementType,
    TraineeProgram,
    TraineeProgramStatus,
    Zone,
    ZoneReportStatus,
    ZoneSummaryReport,
)
from .policies import (
    can_review_assistant_report,
    can_review_site_report,
    can_review_zone_report,
    can_submit_general_report,
    can_submit_site_report,
    ensure,
)

EVENT_SITE_REPORT_SUBMITTED = "SiteReportSubmitted"
EVENT_ZONE_REPORT_SUBMITTED = "ZoneReportSubmitted"
EVENT_ASSISTANT_REPORT_SUBMITTED = "AssistantReportSubmitted"
EVENT_GENERAL_REPORT_SUBMITTED = "GeneralReportSubmitted"

REPORT_CACHE_PREFIX = "report"


def _emit(event_type: str, entity: Any, actor: User) -> None:
    publish_domain_event(
        event_type=event_type,
        aggregate_type=f"site_management.{entity._meta.model_name}",
        aggregate_id=entity.pk,
        payload={"id": entity.pk, "report_date": entity.report_date.isoformat()},
        created_by=actor,
    )


def _audit(action: AuditLog.Action, entity: Any, actor: User, summary: str) -> None:
    record_audit(
        action=action,
        actor=actor,
        entity=entity,
        summary=summary,
        after_data=model_data(entity),
    )


def _invalidate_reports() -> None:
    invalidate_prefix(REPORT_CACHE_PREFIX)


def _decimal(value: Any) -> float:
    return float(value) if value is not None else 0.0


def _date_bounds(day: datetime.date) -> tuple[datetime.datetime, datetime.datetime]:
    start = timezone.make_aware(datetime.datetime.combine(day, datetime.time.min))
    end = timezone.make_aware(datetime.datetime.combine(day, datetime.time.max))
    return start, end


def _attendance_data(site_id: int, day: datetime.date) -> dict[str, Any]:
    records = AttendanceRecord.objects.filter(site_id=site_id, attendance_date=day)
    statuses = {row["status"]: row["n"] for row in records.values("status").order_by().annotate(n=Count("pk"))}
    review = {
        row["review_status"]: row["n"] for row in records.values("review_status").order_by().annotate(n=Count("pk"))
    }
    attended = statuses.get("present", 0) + statuses.get("late", 0)
    denominator = attended + statuses.get("absent", 0)
    return {
        "total": sum(statuses.values()),
        "present": statuses.get("present", 0),
        "late": statuses.get("late", 0),
        "absent": statuses.get("absent", 0),
        "sick": statuses.get("sick", 0),
        "leave": statuses.get("leave", 0),
        "permission": statuses.get("permission", 0),
        "off": statuses.get("off", 0),
        "attendance_rate": round((attended / denominator) * 100, 2) if denominator else 0.0,
        "review": review,
    }


def _store_data(site_id: int, day: datetime.date) -> dict[str, Any]:
    movements = StockMovement.objects.filter(store_item__store__site_id=site_id, movement_date=day)
    by_type = {
        row["movement_type"]: row["total"]
        for row in movements.values("movement_type").order_by().annotate(total=Count("pk"))
    }
    return {
        "movements": sum(by_type.values()),
        "received": by_type.get(StockMovementType.RECEIVED, 0),
        "issued": by_type.get(StockMovementType.ISSUED, 0),
        "damaged_lost": by_type.get(StockMovementType.DAMAGED, 0) + by_type.get(StockMovementType.LOST, 0),
        "low_stock_items": _low_stock_queryset(site_id).count(),
    }


def _low_stock_queryset(site_id: int) -> QuerySet[Any]:
    from django.db.models import F

    from .models import StoreItem

    return StoreItem.objects.filter(store__site_id=site_id, current_stock__lte=F("minimum_stock_level"))


def _inspection_data(site_id: int, day: datetime.date) -> dict[str, Any]:
    inspections = Inspection.objects.filter(site_id=site_id, inspection_date=day).exclude(status="draft")
    overall = {
        row["overall_status"]: row["n"]
        for row in inspections.values("overall_status").order_by().annotate(n=Count("pk"))
    }
    avg = inspections.aggregate(avg_score=Avg("score"))["avg_score"]
    return {
        "total": sum(overall.values()),
        "passed": overall.get("passed", 0),
        "failed": overall.get("failed", 0),
        "needs_attention": overall.get("needs_attention", 0),
        "average_score": _decimal(avg),
    }


def _trainee_data(site_id: int, day: datetime.date) -> dict[str, Any]:
    programs = TraineeProgram.objects.filter(site_id=site_id, start_date__lte=day)
    grouped = {row["status"]: row["n"] for row in programs.values("status").order_by().annotate(n=Count("pk"))}
    active = programs.filter(status__in=[TraineeProgramStatus.IN_TRAINING, TraineeProgramStatus.EXTENDED])
    return {
        "in_training": grouped.get(TraineeProgramStatus.IN_TRAINING.value, 0),
        "extended": grouped.get(TraineeProgramStatus.EXTENDED.value, 0),
        "passed": grouped.get(TraineeProgramStatus.PASSED.value, 0),
        "failed": grouped.get(TraineeProgramStatus.FAILED.value, 0),
        "dropped": grouped.get(TraineeProgramStatus.DROPPED.value, 0),
        "active_today": active.count(),
    }


def _issue_data(site_id: int, day: datetime.date) -> dict[str, Any]:
    start, end = _date_bounds(day)
    issues = Issue.objects.filter(site_id=site_id)
    raised_today = issues.filter(created_at__range=(start, end)).count()
    open_count = issues.exclude(status="closed").count()
    escalated = issues.filter(is_escalated=True).count()
    urgent = issues.filter(priority="urgent").exclude(status="closed").count()
    return {
        "raised_today": raised_today,
        "open": open_count,
        "escalated": escalated,
        "urgent": urgent,
    }


def site_data_snapshot(site_id: int, day: datetime.date) -> dict[str, Any]:
    """Aggregate real operational data for a site on a day."""
    return {
        "attendance": _attendance_data(site_id, day),
        "store": _store_data(site_id, day),
        "inspections": _inspection_data(site_id, day),
        "trainees": _trainee_data(site_id, day),
        "issues": _issue_data(site_id, day),
        "generated_at": timezone.now().isoformat(),
    }


def _apply_snapshot(report: DailySiteReport, snapshot: dict[str, Any]) -> None:
    report.attendance_summary = snapshot["attendance"]
    report.store_summary = snapshot["store"]
    report.inspection_summary = snapshot["inspections"]
    report.trainee_summary = snapshot["trainees"]
    report.issues_summary = snapshot["issues"]


# --------------------------------------------------------------------------- #
# Site reports
# --------------------------------------------------------------------------- #


def generate_site_report(*, site_id: int, day: datetime.date, user: User) -> DailySiteReport:
    """Create (or refresh) the DRAFT site report with live aggregated data."""
    from .models import Site

    site = Site._base_manager.filter(pk=site_id).first()
    if site is None:
        from django.core.exceptions import ValidationError

        raise ValidationError("Site not found.")
    with transaction.atomic():
        report, created = DailySiteReport.objects.get_or_create(
            site_id=site_id,
            report_date=day,
            defaults={"created_by": user, "updated_by": user},
        )
        if created:
            report.created_by = user
        if report.status != SiteReportStatus.DRAFT:
            raise _invalid("Only draft reports can be regenerated.", "report_not_draft")
        snapshot = site_data_snapshot(site_id, day)
        _apply_snapshot(report, snapshot)
        report.snapshot = {}
        report.updated_by = user
        report.save()
        _audit(AuditLog.Action.UPDATE, report, user, f"Generated site report {day}")
        _invalidate_reports()
    return report


def submit_site_report(*, report: DailySiteReport, user: User) -> DailySiteReport:
    """Submit a site report, storing its immutable snapshot."""
    with transaction.atomic():
        ensure(user, can_submit_site_report(user, report), "You cannot submit this site report.")
        if report.status not in {SiteReportStatus.DRAFT, SiteReportStatus.RETURNED}:
            raise _invalid("Only draft reports can be submitted.", "invalid_status")
        snapshot = site_data_snapshot(report.site_id, report.report_date)
        report.attendance_summary = snapshot["attendance"]
        report.store_summary = snapshot["store"]
        report.inspection_summary = snapshot["inspections"]
        report.trainee_summary = snapshot["trainees"]
        report.issues_summary = snapshot["issues"]
        report.snapshot = snapshot
        report.status = SiteReportStatus.SUBMITTED
        report.submitted_at = timezone.now()
        report.returned_reason = ""
        report.updated_by = user
        report.save()
        _audit(AuditLog.Action.STATUS_CHANGE, report, user, f"Submitted site report {report.report_date}")
        _emit(EVENT_SITE_REPORT_SUBMITTED, report, user)
        _invalidate_reports()
    return report


def return_site_report(*, report: DailySiteReport, user: User, reason: str) -> DailySiteReport:
    """Return a submitted site report for correction; history is preserved."""
    with transaction.atomic():
        ensure(user, can_review_site_report(user, report), "You cannot return this site report.")
        if report.status not in {SiteReportStatus.SUBMITTED, SiteReportStatus.ZONE_REVIEWED}:
            raise _invalid("This report cannot be returned.", "invalid_status")
        if not reason.strip():
            raise _invalid("A reason is required to return a report.", "reason_required")
        report.status = SiteReportStatus.RETURNED
        report.returned_reason = reason
        report.updated_by = user
        report.save()
        _audit(AuditLog.Action.STATUS_CHANGE, report, user, f"Returned site report {report.report_date}: {reason}")
        _invalidate_reports()
    created_by = report.created_by
    if created_by is not None:
        from .services import notify

        notify(
            recipient=created_by,
            verb="report_returned",
            title="Site report returned",
            body=f"{report.site.name} report for {report.report_date} was returned: {reason}",
            actor=user,
            object_type="site_management.dailysitereport",
            object_id=report.pk,
            link=f"/admin/site_management/dailysitereport/{report.pk}/change/",
            dedup_key=f"report-returned:{report.pk}",
        )
    return report


def review_site_report_by_zone(*, report: DailySiteReport, user: User) -> DailySiteReport:
    """Zone supervisor reviews a submitted site report."""
    ensure(user, can_review_site_report(user, report), "You cannot review this site report.")
    return _advance_site_report(report, user, SiteReportStatus.ZONE_REVIEWED)


def _advance_site_report(report: DailySiteReport, user: User, target: str) -> DailySiteReport:
    with transaction.atomic():
        allowed: dict[str, str] = {
            SiteReportStatus.SUBMITTED.value: SiteReportStatus.ZONE_REVIEWED.value,
            SiteReportStatus.ZONE_REVIEWED.value: SiteReportStatus.ASSISTANT_REVIEWED.value,
            SiteReportStatus.ASSISTANT_REVIEWED.value: SiteReportStatus.GENERAL_APPROVED.value,
            SiteReportStatus.GENERAL_APPROVED.value: SiteReportStatus.MANAGEMENT_SUBMITTED.value,
        }
        if report.status not in allowed or allowed[report.status] != target:
            raise _invalid("Invalid status transition.", "invalid_status")
        report.status = target
        report.updated_by = user
        report.save()
        _audit(AuditLog.Action.STATUS_CHANGE, report, user, f"Site report {report.pk} -> {target}")
        _invalidate_reports()
    return report


def _invalid(message: str, code: str) -> ValidationError:
    return ValidationError(message, code=code)


# --------------------------------------------------------------------------- #
# Zone summaries
# --------------------------------------------------------------------------- #


def generate_zone_summary(*, zone_id: int, day: datetime.date, user: User) -> ZoneSummaryReport:
    """Build a zone summary from that zone's submitted site reports."""
    with transaction.atomic():
        report, created = ZoneSummaryReport.objects.get_or_create(
            zone_id=zone_id,
            report_date=day,
            defaults={"zone_supervisor": user, "created_by": user},
        )
        if created:
            report.zone_supervisor = user
        if report.status != ZoneReportStatus.DRAFT:
            raise _invalid("Only draft zone summaries can be regenerated.", "report_not_draft")
        site_reports = list(
            DailySiteReport.objects.filter(
                site__zone_id=zone_id,
                report_date=day,
                status__in=[SiteReportStatus.SUBMITTED, SiteReportStatus.ZONE_REVIEWED],
            ).select_related("site")
        )
        report.site_reports = [
            {
                "site_id": sr.site_id,
                "site_name": sr.site.name,
                "status": sr.status,
                "attendance_rate": sr.attendance_summary.get("attendance_rate", 0),
                "issues": sr.issues_summary,
                "inspections": sr.inspection_summary,
            }
            for sr in site_reports
        ]
        report.issues_extracted = [
            {
                "site_id": sr.site_id,
                "site_name": sr.site.name,
                "urgent": sr.issues_summary.get("urgent", 0),
                "escalated": sr.issues_summary.get("escalated", 0),
                "open": sr.issues_summary.get("open", 0),
            }
            for sr in site_reports
            if sr.issues_summary.get("urgent", 0) or sr.issues_summary.get("escalated", 0)
        ]
        report.summary = f"Zone report for {report.report_date}: {len(site_reports)} site report(s)."
        report.updated_by = user
        report.save()
        _audit(AuditLog.Action.UPDATE, report, user, f"Generated zone summary {day}")
        _invalidate_reports()
    return report


def submit_zone_summary(*, report: ZoneSummaryReport, user: User) -> ZoneSummaryReport:
    with transaction.atomic():
        ensure(user, can_review_zone_report(user, report), "You cannot submit this zone summary.")
        if report.status != ZoneReportStatus.DRAFT:
            raise _invalid("Only draft zone summaries can be submitted.", "invalid_status")
        report.status = ZoneReportStatus.SUBMITTED
        report.submitted_at = timezone.now()
        report.updated_by = user
        report.save()
        _audit(AuditLog.Action.STATUS_CHANGE, report, user, f"Submitted zone summary {report.report_date}")
        _emit(EVENT_ZONE_REPORT_SUBMITTED, report, user)
        _invalidate_reports()
    return report


def return_zone_summary(*, report: ZoneSummaryReport, user: User, reason: str) -> ZoneSummaryReport:
    with transaction.atomic():
        if report.status != ZoneReportStatus.SUBMITTED:
            raise _invalid("Only submitted zone summaries can be returned.", "invalid_status")
        if not reason.strip():
            raise _invalid("A reason is required to return a zone summary.", "reason_required")
        report.status = ZoneReportStatus.RETURNED
        report.summary = (report.summary + "\n" if report.summary else "") + f"Returned: {reason}"
        report.updated_by = user
        report.save()
        _audit(AuditLog.Action.STATUS_CHANGE, report, user, f"Returned zone summary {report.report_date}")
        _invalidate_reports()
    return report


# --------------------------------------------------------------------------- #
# Assistant general summaries
# --------------------------------------------------------------------------- #


def generate_assistant_summary(
    *, day: datetime.date, user: User, zone_ids: list[int] | None = None
) -> AssistantGeneralSummaryReport:
    """Build the assistant summary across the given zones (or all submitted)."""
    with transaction.atomic():
        report, created = AssistantGeneralSummaryReport.objects.get_or_create(
            report_date=day,
            defaults={"assistant_general_supervisor": user, "created_by": user},
        )
        if created:
            report.assistant_general_supervisor = user
        if report.status != AssistantReportStatus.DRAFT:
            raise _invalid("Only draft assistant summaries can be regenerated.", "report_not_draft")
        zone_qs = Zone.objects.all()
        if zone_ids is not None:
            zone_qs = zone_qs.filter(pk__in=zone_ids)
        zone_ids_final = list(zone_qs.values_list("pk", flat=True))
        report.zone_ids = zone_ids_final
        zone_reports = ZoneSummaryReport.objects.filter(
            report_date=day, zone_id__in=zone_ids_final, status=ZoneReportStatus.SUBMITTED
        ).select_related("zone")
        problems: list[dict[str, Any]] = []
        for zr in zone_reports:
            for issue in zr.issues_extracted:
                problems.append({"zone_id": zr.zone_id, "zone_name": zr.zone.name, **issue})
        report.problems_extracted = problems
        report.summary = f"Assistant summary for {day} across {len(zone_ids_final)} zone(s)."
        report.updated_by = user
        report.save()
        _audit(AuditLog.Action.UPDATE, report, user, f"Generated assistant summary {day}")
        _invalidate_reports()
    return report


def submit_assistant_summary(*, report: AssistantGeneralSummaryReport, user: User) -> AssistantGeneralSummaryReport:
    with transaction.atomic():
        ensure(user, can_review_assistant_report(user, report), "You cannot submit this assistant summary.")
        if report.status != AssistantReportStatus.DRAFT:
            raise _invalid("Only draft assistant summaries can be submitted.", "invalid_status")
        report.status = AssistantReportStatus.SUBMITTED
        report.submitted_at = timezone.now()
        report.updated_by = user
        report.save()
        _audit(AuditLog.Action.STATUS_CHANGE, report, user, f"Submitted assistant summary {report.report_date}")
        _emit(EVENT_ASSISTANT_REPORT_SUBMITTED, report, user)
        _invalidate_reports()
    return report


def return_assistant_summary(
    *, report: AssistantGeneralSummaryReport, user: User, reason: str
) -> AssistantGeneralSummaryReport:
    with transaction.atomic():
        if report.status != AssistantReportStatus.SUBMITTED:
            raise _invalid("Only submitted assistant summaries can be returned.", "invalid_status")
        if not reason.strip():
            raise _invalid("A reason is required to return an assistant summary.", "reason_required")
        report.status = AssistantReportStatus.RETURNED
        report.recommendations = (
            report.recommendations + "\n" if report.recommendations else ""
        ) + f"Returned: {reason}"
        report.updated_by = user
        report.save()
        _audit(AuditLog.Action.STATUS_CHANGE, report, user, f"Returned assistant summary {report.report_date}")
        _invalidate_reports()
    return report


# --------------------------------------------------------------------------- #
# General management report
# --------------------------------------------------------------------------- #


def generate_general_management_report(*, day: datetime.date, user: User) -> GeneralManagementReport:
    """Compile the final management report from submitted assistant summaries."""
    with transaction.atomic():
        report, created = GeneralManagementReport.objects.get_or_create(
            report_date=day,
            defaults={"general_supervisor": user, "created_by": user},
        )
        if created:
            report.general_supervisor = user
        if report.status != GeneralReportStatus.DRAFT:
            raise _invalid("Only draft general reports can be regenerated.", "report_not_draft")
        assistants = AssistantGeneralSummaryReport.objects.filter(
            report_date=day, status=AssistantReportStatus.SUBMITTED
        )
        key_issues: list[dict[str, Any]] = []
        for a in assistants:
            key_issues.extend(a.problems_extracted)
        report.key_issues = key_issues
        report.assigned_jobs = list(_assigned_jobs_snapshot(day))
        report.recommendations = "Awaiting final review."
        report.final_summary = (
            f"Management report for {day}: {len(key_issues)} issue(s), {len(report.assigned_jobs)} job(s)."
        )
        report.updated_by = user
        report.save()
        _audit(AuditLog.Action.UPDATE, report, user, f"Generated general management report {day}")
        _invalidate_reports()
    return report


def _assigned_jobs_snapshot(day: datetime.date) -> list[dict[str, Any]]:
    from .models import Job

    jobs = Job.objects.filter(created_at__date=day).select_related("site", "assigned_to_user", "assigned_to_cleaner")
    result: list[dict[str, Any]] = []
    for j in jobs:
        assigned_user = j.assigned_to_user
        assigned_cleaner = j.assigned_to_cleaner
        result.append(
            {
                "job_id": j.pk,
                "job_title": j.job_title,
                "site_name": j.site.name,
                "status": j.status,
                "due_date": j.due_date.isoformat() if j.due_date else None,
                "assignee": (
                    assigned_user.email
                    if assigned_user is not None
                    else (assigned_cleaner.full_name if assigned_cleaner is not None else None)
                ),
            }
        )
    return result


def submit_general_management_report(*, report: GeneralManagementReport, user: User) -> GeneralManagementReport:
    with transaction.atomic():
        ensure(user, can_submit_general_report(user, report), "You cannot submit the general report.")
        if report.status != GeneralReportStatus.DRAFT:
            raise _invalid("Only draft general reports can be submitted.", "invalid_status")
        report.status = GeneralReportStatus.SUBMITTED_TO_MANAGEMENT
        report.submitted_at = timezone.now()
        report.updated_by = user
        report.save()
        _audit(AuditLog.Action.STATUS_CHANGE, report, user, f"Submitted general report {report.report_date}")
        _emit(EVENT_GENERAL_REPORT_SUBMITTED, report, user)
        _invalidate_reports()
    return report


def recalculate_report_snapshots(*, day: datetime.date, user: User) -> int:
    """Regenerate live aggregates for every draft site report on a date."""
    updated = 0
    for report in DailySiteReport.objects.filter(report_date=day, status=SiteReportStatus.DRAFT):
        snapshot = site_data_snapshot(report.site_id, day)
        _apply_snapshot(report, snapshot)
        report.updated_by = user
        report.save()
        _audit(AuditLog.Action.UPDATE, report, user, f"Recalculated site report snapshot {day}")
        updated += 1
    _invalidate_reports()
    return updated
