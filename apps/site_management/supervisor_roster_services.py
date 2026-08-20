"""Audited personal roster and PDF-derived supervisor checklist write services."""

from __future__ import annotations

from datetime import date
from typing import Any

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import RoleCode, User
from apps.core.models import AuditLog
from apps.core.services import model_data, record_audit

from .models import (
    SupervisorChecklistKind,
    SupervisorChecklistStatus,
    SupervisorChecklistSubmission,
    SupervisorTimetableEntry,
)
from .scoping import site_in_user_scope

PDF_TABLE_LABELS = {
    SupervisorChecklistKind.SITE_ZILIZO_TEMBELEWA: "SITE ZILIZO TEMBELEWA",
    SupervisorChecklistKind.MAENEO_YALIYOKAGULIWA: "MAENEO YALIYOKAGULIWA",
    SupervisorChecklistKind.KAZI_ZILIZOFANYIKA: "KAZI ZILIZOFANYIKA",
    SupervisorChecklistKind.TAARIFA_ZA_VITENDEA_KAZI: "TAARIFA ZA VITENDEA KAZI",
}


def create_timetable_entry(*, actor: User, **values: Any) -> SupervisorTimetableEntry:
    if not actor.is_system_admin:
        raise PermissionDenied("Only a system administrator can manage supervisor timetables.")
    with transaction.atomic():
        entry = SupervisorTimetableEntry(created_by=actor, updated_by=actor, **values)
        if entry.supervisor.role not in {RoleCode.ZONE_SUPERVISOR, RoleCode.ASSISTANT_GENERAL_SUPERVISOR}:
            raise ValidationError("A personal timetable can only be assigned to a Zone or Assistant General Supervisor.")
        if not site_in_user_scope(entry.supervisor, entry.site_id):
            raise ValidationError("The timetable site must be within the supervisor's current authorized assignment scope.")
        entry.full_clean()
        entry.save()
        record_audit(
            action=AuditLog.Action.CREATE,
            actor=actor,
            entity=entry,
            summary=f"Created personal timetable entry for {entry.supervisor.email} at {entry.site.name}",
            after_data=model_data(entry),
        )
    return entry


def update_timetable_entry(*, entry: SupervisorTimetableEntry, actor: User, **values: Any) -> SupervisorTimetableEntry:
    if not actor.is_system_admin:
        raise PermissionDenied("Only a system administrator can manage supervisor timetables.")
    with transaction.atomic():
        before = model_data(entry)
        for field, value in values.items():
            setattr(entry, field, value)
        if not site_in_user_scope(entry.supervisor, entry.site_id):
            raise ValidationError("The timetable site must be within the supervisor's current authorized assignment scope.")
        entry.updated_by = actor
        entry.full_clean()
        entry.save()
        record_audit(
            action=AuditLog.Action.UPDATE,
            actor=actor,
            entity=entry,
            summary=f"Updated personal timetable entry for {entry.supervisor.email}",
            before_data=before,
            after_data=model_data(entry),
        )
    return entry


def deactivate_timetable_entry(*, entry: SupervisorTimetableEntry, actor: User) -> SupervisorTimetableEntry:
    if not actor.is_system_admin:
        raise PermissionDenied("Only a system administrator can manage supervisor timetables.")
    with transaction.atomic():
        if not entry.is_active:
            return entry
        before = model_data(entry)
        entry.is_active = False
        entry.updated_by = actor
        entry.save(update_fields=["is_active", "updated_by", "updated_at"])
        record_audit(
            action=AuditLog.Action.STATUS_CHANGE,
            actor=actor,
            entity=entry,
            summary=f"Deactivated personal timetable entry for {entry.supervisor.email}",
            before_data=before,
            after_data=model_data(entry),
        )
    return entry


def delete_timetable_entry(*, entry: SupervisorTimetableEntry, actor: User) -> tuple[bool, SupervisorTimetableEntry | None]:
    """Delete a timetable only when it has no checklist evidence.

    Checklist submissions are protected operational records.  An attempted delete
    against a timetable with submissions is therefore retained as an inactive
    entry, preserving the immutable checklist-to-roster relationship.
    """
    if not actor.is_system_admin:
        raise PermissionDenied("Only a system administrator can manage supervisor timetables.")
    with transaction.atomic():
        if entry.checklist_submissions.exists():
            retained = deactivate_timetable_entry(entry=entry, actor=actor)
            return True, retained
        before = model_data(entry)
        supervisor_email = entry.supervisor.email
        site_name = entry.site.name
        record_audit(
            action=AuditLog.Action.DELETE,
            actor=actor,
            entity=entry,
            summary=f"Deleted unused personal timetable entry for {supervisor_email} at {site_name}",
            before_data=before,
        )
        entry.delete()
    return False, None


def save_supervisor_checklist(
    *,
    actor: User,
    timetable_entry: SupervisorTimetableEntry,
    work_date: date,
    checklist_kind: str,
    table_entries: list[dict[str, Any]],
    notes: str,
) -> SupervisorChecklistSubmission:
    if actor.pk != timetable_entry.supervisor_id:
        raise PermissionDenied("You can only save your own timetable checklist.")
    if actor.role not in {RoleCode.ZONE_SUPERVISOR, RoleCode.ASSISTANT_GENERAL_SUPERVISOR}:
        raise PermissionDenied("This checklist is limited to Zone and Assistant General Supervisors.")
    if not timetable_entry.is_scheduled_for(work_date):
        raise ValidationError("This timetable entry is not scheduled for the selected work date.")
    if not site_in_user_scope(actor, timetable_entry.site_id):
        raise PermissionDenied("The timetable site is outside your current authorized scope.")
    try:
        kind = SupervisorChecklistKind(checklist_kind)
    except ValueError as exc:
        raise ValidationError("Unknown PDF checklist type.") from exc
    if actor.role == RoleCode.ZONE_SUPERVISOR and kind == SupervisorChecklistKind.KAZI_ZILIZOFANYIKA:
        raise PermissionDenied("KAZI ZILIZOFANYIKA is an Assistant General Supervisor table.")
    if actor.role == RoleCode.ASSISTANT_GENERAL_SUPERVISOR and kind in {
        SupervisorChecklistKind.SITE_ZILIZO_TEMBELEWA,
        SupervisorChecklistKind.MAENEO_YALIYOKAGULIWA,
    }:
        raise PermissionDenied("This Zone Supervisor table is not available for the current role.")
    if not isinstance(table_entries, list):
        raise ValidationError("The PDF table entries must be a list.")
    with transaction.atomic():
        submission, created = SupervisorChecklistSubmission.objects.get_or_create(
            timetable_entry=timetable_entry,
            work_date=work_date,
            checklist_kind=kind,
            defaults={
                "supervisor": actor,
                "supervisor_role": actor.role,
                "site": timetable_entry.site,
                "zone": timetable_entry.zone,
                "shift_slot": timetable_entry.shift_slot,
                "table_entries": table_entries,
                "notes": notes,
                "created_by": actor,
                "updated_by": actor,
            },
        )
        if not created:
            if not submission.is_editable:
                raise ValidationError("Submitted or reviewed checklist rows cannot be changed without a return.")
            before = model_data(submission)
            submission.table_entries = table_entries
            submission.notes = notes
            submission.updated_by = actor
            submission.full_clean()
            submission.save(update_fields=["table_entries", "notes", "updated_by", "updated_at"])
            record_audit(
                action=AuditLog.Action.UPDATE,
                actor=actor,
                entity=submission,
                summary=f"Updated {PDF_TABLE_LABELS[kind]} draft for {submission.site.name}",
                before_data=before,
                after_data=model_data(submission),
            )
        else:
            submission.full_clean()
            record_audit(
                action=AuditLog.Action.CREATE,
                actor=actor,
                entity=submission,
                summary=f"Created {PDF_TABLE_LABELS[kind]} draft for {submission.site.name}",
                after_data=model_data(submission),
            )
    return submission


def submit_supervisor_checklist(*, submission: SupervisorChecklistSubmission, actor: User) -> SupervisorChecklistSubmission:
    if actor.pk != submission.supervisor_id:
        raise PermissionDenied("You can only submit your own timetable checklist.")
    if not submission.is_editable:
        raise ValidationError("Only draft or returned checklist rows can be submitted.")
    if not submission.table_entries:
        raise ValidationError("Add at least one entry to the PDF table before submission.")
    with transaction.atomic():
        before = model_data(submission)
        submission.status = SupervisorChecklistStatus.SUBMITTED
        submission.submitted_at = timezone.now()
        submission.return_reason = ""
        submission.snapshot = {
            "table_label": PDF_TABLE_LABELS[submission.checklist_kind],
            "site_name": submission.site.name,
            "zone_name": submission.zone.name,
            "work_date": submission.work_date.isoformat(),
            "shift": submission.get_shift_slot_display(),
            "supervisor": submission.supervisor.full_name,
            "role": submission.supervisor_role,
            "entries": submission.table_entries,
            "notes": submission.notes,
        }
        submission.updated_by = actor
        submission.full_clean()
        submission.save()
        record_audit(
            action=AuditLog.Action.STATUS_CHANGE,
            actor=actor,
            entity=submission,
            summary=f"Submitted {PDF_TABLE_LABELS[submission.checklist_kind]} for {submission.site.name}",
            before_data=before,
            after_data=model_data(submission),
        )
    return submission


def review_supervisor_checklist(
    *, submission: SupervisorChecklistSubmission, actor: User, action: str, reason: str = ""
) -> SupervisorChecklistSubmission:
    allowed = actor.is_system_admin or actor.role == RoleCode.GENERAL_SUPERVISOR
    allowed = allowed or (
        submission.supervisor_role == RoleCode.ZONE_SUPERVISOR
        and actor.role == RoleCode.ASSISTANT_GENERAL_SUPERVISOR
        and site_in_user_scope(actor, submission.site_id)
    )
    if not allowed:
        raise PermissionDenied("You do not have permission to review this supervisor checklist.")
    if submission.status != SupervisorChecklistStatus.SUBMITTED:
        raise ValidationError("Only submitted checklist rows can be reviewed or returned.")
    if action == SupervisorChecklistStatus.RETURNED and not reason.strip():
        raise ValidationError("A return reason is required.")
    if action not in {SupervisorChecklistStatus.REVIEWED, SupervisorChecklistStatus.RETURNED}:
        raise ValidationError("Unsupported checklist review action.")
    with transaction.atomic():
        before = model_data(submission)
        submission.status = action
        submission.reviewed_by = actor
        submission.reviewed_at = timezone.now()
        submission.return_reason = reason.strip() if action == SupervisorChecklistStatus.RETURNED else ""
        submission.updated_by = actor
        submission.save()
        record_audit(
            action=AuditLog.Action.STATUS_CHANGE,
            actor=actor,
            entity=submission,
            summary=f"{action.title()} {PDF_TABLE_LABELS[submission.checklist_kind]} for {submission.site.name}",
            before_data=before,
            after_data=model_data(submission),
        )
    return submission
