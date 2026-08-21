"""Monthly remuneration preparation with attendance-derived rows and controlled payment-contact updates."""

from __future__ import annotations

from calendar import monthrange
from datetime import date
from typing import Any

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import RoleCode, User
from apps.core.models import AuditLog
from apps.core.services import model_data, record_audit

from .models import (
    AttendanceRecord,
    AttendanceStatus,
    CleanerPaymentProfile,
    CleanerSiteAssignment,
    CleanerAssignmentStatus,
    MonthlyRemunerationLine,
    MonthlyRemunerationReport,
    PaymentChangeStatus,
    RemunerationWorkflowStatus,
    Site,
)
from .scoping import site_in_user_scope


def month_bounds(period: date) -> tuple[date, date]:
    month_start = period.replace(day=1)
    return month_start, month_start.replace(day=monthrange(month_start.year, month_start.month)[1])


def remuneration_window_is_open(*, today: date | None = None) -> bool:
    """The paper form is prepared between Tanzania-local days 15 and 25 inclusive."""
    effective_today = today or timezone.localdate()
    return 15 <= effective_today.day <= 25


def _assert_site_supervisor_scope(*, actor: User, site_id: int) -> None:
    if actor.role != RoleCode.SITE_SUPERVISOR:
        raise PermissionDenied("Only a Site Supervisor can prepare this remuneration form.")
    if not site_in_user_scope(actor, site_id):
        raise PermissionDenied("The remuneration site is outside your authorized supervisor scope.")


def _masked(value: str, visible: int = 3) -> str:
    raw = value.strip()
    if not raw:
        return ""
    if len(raw) <= visible:
        return "•" * len(raw)
    return f"{'•' * max(4, len(raw) - visible)}{raw[-visible:]}"


def _monthly_counts(*, site_id: int, cleaner_id: int, period: date) -> tuple[int, int]:
    starts, ends = month_bounds(period)
    records = AttendanceRecord.objects.filter(site_id=site_id, cleaner_id=cleaner_id, attendance_date__range=(starts, ends))
    present = records.filter(status__in=[AttendanceStatus.PRESENT, AttendanceStatus.LATE]).count()
    absent = records.filter(status=AttendanceStatus.ABSENT).count()
    return present, absent


def _assignment_rows(*, site: Site, period: date) -> list[CleanerSiteAssignment]:
    starts, ends = month_bounds(period)
    return list(
        CleanerSiteAssignment.objects.filter(
            site=site,
            status=CleanerAssignmentStatus.ACTIVE,
            start_date__lte=ends,
        )
        .filter(end_date__isnull=True) | CleanerSiteAssignment.objects.filter(
            site=site,
            status=CleanerAssignmentStatus.ACTIVE,
            start_date__lte=ends,
            end_date__gte=starts,
        )
    )


def _refresh_report_lines(report: MonthlyRemunerationReport) -> None:
    starts, ends = month_bounds(report.period)
    assignments = CleanerSiteAssignment.objects.filter(
        site=report.site,
        status=CleanerAssignmentStatus.ACTIVE,
        start_date__lte=ends,
    ).filter(end_date__isnull=True) | CleanerSiteAssignment.objects.filter(
        site=report.site,
        status=CleanerAssignmentStatus.ACTIVE,
        start_date__lte=ends,
        end_date__gte=starts,
    )
    for assignment in assignments.select_related("cleaner"):
        present, absent = _monthly_counts(site_id=report.site_id, cleaner_id=assignment.cleaner_id, period=report.period)
        start_work_date = assignment.start_date if starts <= assignment.start_date <= ends else None
        line, created = MonthlyRemunerationLine.objects.get_or_create(
            report=report,
            cleaner=assignment.cleaner,
            defaults={
                "assignment": assignment,
                "present_days": present,
                "absent_days": absent,
                "start_work_date": start_work_date,
            },
        )
        if not created and report.is_editable:
            line.assignment = assignment
            line.present_days = present
            line.absent_days = absent
            line.start_work_date = start_work_date
            line.full_clean()
            line.save(update_fields=["assignment", "present_days", "absent_days", "start_work_date", "updated_at"])


def prepare_monthly_remuneration(*, actor: User, site: Site, period: date, today: date | None = None) -> MonthlyRemunerationReport:
    _assert_site_supervisor_scope(actor=actor, site_id=site.pk)
    if period.day != 1:
        raise ValidationError("The selected remuneration month must use its first calendar day.")
    current = (today or timezone.localdate()).replace(day=1)
    if period != current:
        raise ValidationError("Site Supervisors can prepare only the current remuneration month.")
    if not remuneration_window_is_open(today=today):
        raise ValidationError("The remuneration form is open only from the 15th through the 25th of the month.")
    with transaction.atomic():
        report, created = MonthlyRemunerationReport.objects.get_or_create(
            site=site,
            period=period,
            defaults={"prepared_by": actor, "created_by": actor, "updated_by": actor},
        )
        if report.prepared_by_id != actor.pk:
            raise PermissionDenied("This site-month remuneration form belongs to its original Site Supervisor.")
        _refresh_report_lines(report)
        if created:
            record_audit(
                action=AuditLog.Action.CREATE,
                actor=actor,
                entity=report,
                summary=f"Prepared remuneration form for {site.name} / {period:%Y-%m}",
                after_data=model_data(report),
            )
    return report


def remuneration_line_view(line: MonthlyRemunerationLine) -> dict[str, Any]:
    profile = getattr(line.cleaner, "payment_profile", None)
    return {
        "id": line.pk,
        "cleaner_id": line.cleaner_id,
        "cleaner_name": line.cleaner.full_name,
        "present_days": line.present_days,
        "absent_days": line.absent_days,
        "start_work_date": line.start_work_date,
        "last_phone_masked": _masked(profile.yas_zantel_phone) if profile else "",
        "last_account_masked": _masked(profile.pbz_account_number) if profile else "",
        "last_payment_account_holder_name": profile.payment_account_holder_name if profile else "",
        "proposed_yas_zantel_phone": line.proposed_yas_zantel_phone,
        "proposed_pbz_account_number": line.proposed_pbz_account_number,
        "proposed_payment_account_holder_name": line.proposed_payment_account_holder_name,
        "phone_change_status": line.phone_change_status,
        "account_change_status": line.account_change_status,
    }


def save_payment_contact_decision(
    *,
    report: MonthlyRemunerationReport,
    line: MonthlyRemunerationLine,
    actor: User,
    phone: str,
    account: str,
    account_holder_name: str,
) -> MonthlyRemunerationLine:
    _assert_site_supervisor_scope(actor=actor, site_id=report.site_id)
    if report.prepared_by_id != actor.pk or not report.is_editable:
        raise PermissionDenied("This remuneration form can no longer be changed by the current supervisor.")
    if line.report_id != report.pk:
        raise ValidationError("The remuneration row does not belong to this form.")
    with transaction.atomic():
        before = model_data(line)
        profile = getattr(line.cleaner, "payment_profile", None)
        line.previous_yas_zantel_phone = profile.yas_zantel_phone if profile else ""
        line.previous_pbz_account_number = profile.pbz_account_number if profile else ""
        line.previous_payment_account_holder_name = profile.payment_account_holder_name if profile else ""
        line.proposed_yas_zantel_phone = phone.strip()
        line.proposed_pbz_account_number = account.strip()
        line.proposed_payment_account_holder_name = account_holder_name.strip()
        line.phone_change_status = PaymentChangeStatus.PENDING
        line.account_change_status = PaymentChangeStatus.PENDING
        line.payment_saved_by = actor
        line.payment_saved_at = timezone.now()
        line.full_clean()
        line.save()
        record_audit(
            action=AuditLog.Action.UPDATE,
            actor=actor,
            entity=line,
            summary=f"Recorded payment-contact decision for {line.cleaner.full_name} in {report.site.name}",
            before_data=before,
            after_data=model_data(line),
        )
    return line


def administrator_monthly_remuneration_rows(*, actor: User, period: date) -> list[dict[str, Any]]:
    """Full-value payment audit evidence is available only to the system administrator."""
    if not actor.is_system_admin:
        raise PermissionDenied("Only a System Administrator can view the all-site remuneration audit table.")
    starts, ends = month_bounds(period)
    assignments = (
        CleanerSiteAssignment.objects.filter(status=CleanerAssignmentStatus.ACTIVE, start_date__lte=ends)
        .filter(end_date__isnull=True) | CleanerSiteAssignment.objects.filter(
            status=CleanerAssignmentStatus.ACTIVE, start_date__lte=ends, end_date__gte=starts
        )
    ).select_related("cleaner", "site")
    reports = {
        report.site_id: report
        for report in MonthlyRemunerationReport.objects.filter(period=period)
        .select_related("prepared_by", "reviewed_by")
        .prefetch_related("lines__cleaner", "lines__payment_saved_by")
    }
    line_map = {
        (line.report.site_id, line.cleaner_id): line
        for report in reports.values()
        for line in report.lines.select_related("payment_saved_by").all()
    }
    rows: list[dict[str, Any]] = []
    for assignment in assignments:
        profile = getattr(assignment.cleaner, "payment_profile", None)
        line = line_map.get((assignment.site_id, assignment.cleaner_id))
        present, absent = _monthly_counts(site_id=assignment.site_id, cleaner_id=assignment.cleaner_id, period=period)
        report = reports.get(assignment.site_id)
        rows.append(
            {
                "site_id": assignment.site_id,
                "site_name": assignment.site.name,
                "cleaner_id": assignment.cleaner_id,
                "cleaner_name": assignment.cleaner.full_name,
                "present_days": line.present_days if line else present,
                "absent_days": line.absent_days if line else absent,
                "start_work_date": line.start_work_date if line else (assignment.start_date if starts <= assignment.start_date <= ends else None),
                "previous_phone": line.previous_yas_zantel_phone if line and line.previous_yas_zantel_phone else (profile.yas_zantel_phone if profile else ""),
                "previous_account": line.previous_pbz_account_number if line and line.previous_pbz_account_number else (profile.pbz_account_number if profile else ""),
                "previous_payment_account_holder_name": line.previous_payment_account_holder_name if line and line.previous_payment_account_holder_name else (profile.payment_account_holder_name if profile else ""),
                "new_phone": line.proposed_yas_zantel_phone if line else "",
                "new_account": line.proposed_pbz_account_number if line else "",
                "new_payment_account_holder_name": line.proposed_payment_account_holder_name if line else "",
                "phone_change_status": line.phone_change_status if line else "not_recorded",
                "account_change_status": line.account_change_status if line else "not_recorded",
                "payment_saved_by": line.payment_saved_by.full_name if line and line.payment_saved_by else "",
                "payment_saved_at": line.payment_saved_at if line else None,
                "form_status": report.status if report else "not_prepared",
                "form_prepared_by": report.prepared_by.full_name if report else "",
                "form_submitted_at": report.submitted_at if report else None,
                "form_reviewed_by": report.reviewed_by.full_name if report and report.reviewed_by else "",
                "form_reviewed_at": report.reviewed_at if report else None,
            }
        )
    return rows


def submit_monthly_remuneration(*, report: MonthlyRemunerationReport, actor: User) -> MonthlyRemunerationReport:
    _assert_site_supervisor_scope(actor=actor, site_id=report.site_id)
    if report.prepared_by_id != actor.pk or not report.is_editable:
        raise PermissionDenied("This remuneration form can no longer be submitted by the current supervisor.")
    with transaction.atomic():
        before = model_data(report)
        report.status = RemunerationWorkflowStatus.SUBMITTED
        report.submitted_at = timezone.now()
        report.return_reason = ""
        report.snapshot = {
            "form_heading": "FOMU. TAARIFA ZA WAFANYAKAZI KWA AJILI YA MALIPO(MWEZI)",
            "site_name": report.site.name,
            "period": report.period.isoformat(),
            "prepared_by": actor.full_name,
            "lines": [
                {
                    "cleaner_name": line.cleaner.full_name,
                    "present_days": line.present_days,
                    "absent_days": line.absent_days,
                    "start_work_date": line.start_work_date.isoformat() if line.start_work_date else None,
                    "phone_change_recorded": bool(line.proposed_yas_zantel_phone),
                    "account_change_recorded": bool(line.proposed_pbz_account_number),
                    "payment_account_holder_name_recorded": bool(line.proposed_payment_account_holder_name),
                }
                for line in report.lines.select_related("cleaner").all()
            ],
        }
        report.updated_by = actor
        report.full_clean()
        report.save()
        record_audit(
            action=AuditLog.Action.STATUS_CHANGE,
            actor=actor,
            entity=report,
            summary=f"Submitted remuneration form for {report.site.name} / {report.period:%Y-%m}",
            before_data=before,
            after_data=model_data(report),
        )
    return report


def review_monthly_remuneration(*, report: MonthlyRemunerationReport, actor: User, action: str, reason: str = "") -> MonthlyRemunerationReport:
    if actor.role not in {RoleCode.HR, RoleCode.SYSTEM_ADMIN}:
        raise PermissionDenied("Only HR or a System Administrator can review remuneration forms.")
    if report.status != RemunerationWorkflowStatus.SUBMITTED:
        raise ValidationError("Only submitted remuneration forms can be reviewed or returned.")
    if action == RemunerationWorkflowStatus.RETURNED and not reason.strip():
        raise ValidationError("A return reason is required.")
    if action not in {RemunerationWorkflowStatus.REVIEWED, RemunerationWorkflowStatus.RETURNED}:
        raise ValidationError("Unsupported remuneration review action.")
    with transaction.atomic():
        before = model_data(report)
        if action == RemunerationWorkflowStatus.REVIEWED:
            for line in report.lines.select_related("cleaner").all():
                profile, _ = CleanerPaymentProfile.objects.get_or_create(cleaner=line.cleaner, defaults={"created_by": actor, "updated_by": actor})
                changed = False
                if line.proposed_yas_zantel_phone:
                    profile.yas_zantel_phone = line.proposed_yas_zantel_phone
                    line.phone_change_status = PaymentChangeStatus.APPROVED
                    changed = True
                if line.proposed_pbz_account_number:
                    profile.pbz_account_number = line.proposed_pbz_account_number
                    line.account_change_status = PaymentChangeStatus.APPROVED
                    changed = True
                if line.proposed_payment_account_holder_name:
                    profile.payment_account_holder_name = line.proposed_payment_account_holder_name
                    changed = True
                if changed:
                    profile.approved_at = timezone.now()
                    profile.approved_by = actor
                    profile.updated_by = actor
                    profile.full_clean()
                    profile.save()
                    line.save(update_fields=["phone_change_status", "account_change_status", "updated_at"])
                    record_audit(
                        action=AuditLog.Action.UPDATE,
                        actor=actor,
                        entity=profile,
                        summary=f"Approved remuneration payment-contact update for {line.cleaner.full_name}",
                        after_data=model_data(profile),
                    )
        report.status = action
        report.reviewed_by = actor
        report.reviewed_at = timezone.now()
        report.return_reason = reason.strip() if action == RemunerationWorkflowStatus.RETURNED else ""
        report.updated_by = actor
        report.save()
        record_audit(
            action=AuditLog.Action.STATUS_CHANGE,
            actor=actor,
            entity=report,
            summary=f"{action.title()} remuneration form for {report.site.name} / {report.period:%Y-%m}",
            before_data=before,
            after_data=model_data(report),
        )
    return report
