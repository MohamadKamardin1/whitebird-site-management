"""Cleaner assignment and scheduling services.

All mutations are transactional and audited. Assignment status changes and
schedule overlaps are enforced here; the models validate field-level rules.
"""

from __future__ import annotations

from datetime import date, time
from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.accounts.models import User
from apps.core.models import AuditLog
from apps.core.services import model_data, publish_domain_event, record_audit

from .models import (
    Cleaner,
    CleanerAreaSchedule,
    CleanerAssignmentStatus,
    CleanerAssignmentType,
    CleanerShiftAssignment,
    CleanerSiteAssignment,
    CleanerStatus,
    OperationalRole,
    Site,
    SiteArea,
    SiteShift,
)

EVENT_CLEANER_ASSIGNED = "CleanerAssigned"
EVENT_CLEANER_UNASSIGNED = "CleanerUnassigned"


def _emit_event(event_type: str, assignment: CleanerSiteAssignment, actor: User) -> None:
    publish_domain_event(
        event_type=event_type,
        aggregate_type="site_management.cleanersiteassignment",
        aggregate_id=assignment.pk,
        payload={"assignment_id": assignment.pk, "cleaner_id": assignment.cleaner_id, "site_id": assignment.site_id},
        created_by=actor,
    )


def _assignment_audit(
    action: AuditLog.Action,
    assignment: CleanerSiteAssignment,
    actor: User,
    summary: str,
    *,
    before: dict[str, Any] | None = None,
) -> None:
    record_audit(
        action=action,
        actor=actor,
        entity=assignment,
        summary=summary,
        before_data=before,
        after_data=model_data(assignment),
    )


def assign_cleaner_to_site(
    *,
    cleaner: Cleaner,
    site: Site,
    assignment_type: CleanerAssignmentType,
    start_date: date,
    end_date: date | None = None,
    notes: str = "",
    actor: User,
) -> CleanerSiteAssignment:
    """Create an official site assignment for a cleaner.

    ACTIVE cleaners get an ACTIVE assignment; applicants/trainees are captured
    as DRAFT; inactive cleaners cannot be assigned.
    """
    with transaction.atomic():
        if cleaner.status == CleanerStatus.INACTIVE:
            raise ValidationError("An inactive cleaner cannot be assigned.", code="cleaner_inactive")
        if cleaner.status == CleanerStatus.ACTIVE:
            status = CleanerAssignmentStatus.ACTIVE
        else:
            status = CleanerAssignmentStatus.DRAFT
        assignment = CleanerSiteAssignment(
            cleaner=cleaner,
            site=site,
            assignment_type=assignment_type,
            start_date=start_date,
            end_date=end_date,
            status=status,
            assigned_by=actor,
            notes=notes,
            created_by=actor,
            updated_by=actor,
        )
        assignment.full_clean()
        assignment.save()
        _assignment_audit(
            AuditLog.Action.CREATE,
            assignment,
            actor,
            f"Assigned {cleaner.full_name} to {site.name}",
        )
        if status == CleanerAssignmentStatus.ACTIVE:
            _emit_event(EVENT_CLEANER_ASSIGNED, assignment, actor)
    return assignment


def update_assignment(
    *,
    assignment: CleanerSiteAssignment,
    actor: User,
    end_date: date | None = None,
    notes: str | None = None,
) -> CleanerSiteAssignment:
    """Update non-status fields of an assignment."""
    with transaction.atomic():
        before = model_data(assignment)
        if end_date is not None:
            assignment.end_date = end_date
        if notes is not None:
            assignment.notes = notes
        assignment.updated_by = actor
        assignment.full_clean()
        assignment.save()
        _assignment_audit(
            AuditLog.Action.UPDATE,
            assignment,
            actor,
            f"Updated assignment for {assignment.cleaner.full_name}",
            before=before,
        )
    return assignment


def end_assignment(
    *, assignment: CleanerSiteAssignment, actor: User, end_date: date | None = None
) -> CleanerSiteAssignment:
    """End an assignment; history is preserved (never hard-deleted)."""
    with transaction.atomic():
        before = model_data(assignment)
        assignment.status = CleanerAssignmentStatus.ENDED
        if not assignment.end_date:
            assignment.end_date = end_date or date.today()
        assignment.updated_by = actor
        assignment.save(update_fields=["status", "end_date", "updated_by", "updated_at"])
        _assignment_audit(
            AuditLog.Action.UNASSIGN,
            assignment,
            actor,
            f"Ended assignment for {assignment.cleaner.full_name}",
            before=before,
        )
        _emit_event(EVENT_CLEANER_UNASSIGNED, assignment, actor)
    return assignment


def suspend_assignment(*, assignment: CleanerSiteAssignment, actor: User) -> CleanerSiteAssignment:
    """Suspend an assignment (temporary pause)."""
    with transaction.atomic():
        before = model_data(assignment)
        assignment.status = CleanerAssignmentStatus.SUSPENDED
        assignment.updated_by = actor
        assignment.save(update_fields=["status", "updated_by", "updated_at"])
        _assignment_audit(
            AuditLog.Action.STATUS_CHANGE,
            assignment,
            actor,
            f"Suspended assignment for {assignment.cleaner.full_name}",
            before=before,
        )
    return assignment


def activate_assignment(*, assignment: CleanerSiteAssignment, actor: User) -> CleanerSiteAssignment:
    """Activate an assignment; requires an ACTIVE cleaner."""
    with transaction.atomic():
        if assignment.cleaner.status != CleanerStatus.ACTIVE:
            raise ValidationError("Only ACTIVE cleaners can hold ACTIVE assignments.", code="cleaner_not_active")
        before = model_data(assignment)
        assignment.status = CleanerAssignmentStatus.ACTIVE
        assignment.updated_by = actor
        assignment.full_clean()
        assignment.save()
        _assignment_audit(
            AuditLog.Action.STATUS_CHANGE,
            assignment,
            actor,
            f"Activated assignment for {assignment.cleaner.full_name}",
            before=before,
        )
        _emit_event(EVENT_CLEANER_ASSIGNED, assignment, actor)
    return assignment


def assign_cleaner_shift(
    *,
    assignment: CleanerSiteAssignment,
    shift: SiteShift,
    effective_from: date,
    effective_to: date | None = None,
    actor: User,
) -> CleanerShiftAssignment:
    """Bind a shift to a shift-type assignment."""
    with transaction.atomic():
        shift_assignment = CleanerShiftAssignment(
            assignment=assignment,
            shift=shift,
            effective_from=effective_from,
            effective_to=effective_to,
            is_active=True,
            created_by=actor,
            updated_by=actor,
        )
        shift_assignment.full_clean()
        shift_assignment.save()
        record_audit(
            action=AuditLog.Action.ASSIGN,
            actor=actor,
            entity=shift_assignment,
            summary=f"Assigned shift {shift.shift_name} to {assignment.cleaner.full_name}",
            after_data=model_data(shift_assignment),
        )
    return shift_assignment


def remove_cleaner_shift(*, shift_assignment: CleanerShiftAssignment, actor: User) -> CleanerShiftAssignment:
    """Deactivate a shift binding (history preserved)."""
    with transaction.atomic():
        shift_assignment.is_active = False
        shift_assignment.updated_by = actor
        shift_assignment.save(update_fields=["is_active", "updated_by", "updated_at"])
        record_audit(
            action=AuditLog.Action.UNASSIGN,
            actor=actor,
            entity=shift_assignment,
            summary=(
                f"Removed shift {shift_assignment.shift.shift_name} from "
                f"{shift_assignment.assignment.cleaner.full_name}"
            ),
            before_data=model_data(shift_assignment),
        )
    return shift_assignment


def _minutes(value: time) -> int:
    return value.hour * 60 + value.minute


def _spans_overlap(start1: time, end1: time, start2: time, end2: time) -> bool:
    """Detect overlap between two time ranges, supporting overnight wraps."""

    def contains(s: time, e: time, point: int) -> bool:
        duration = _minutes(e) - _minutes(s)
        if duration <= 0:
            duration += 1440
        return (point - _minutes(s)) % 1440 < duration

    return contains(start1, end1, _minutes(start2)) or contains(start2, end2, _minutes(start1))


def _validate_no_schedule_overlap(*, cleaner: Cleaner, day: date, schedule: CleanerAreaSchedule) -> None:
    existing = CleanerAreaSchedule.objects.filter(assignment__cleaner=cleaner, date=day, is_active=True).exclude(
        pk=schedule.pk
    )
    for other in existing:
        if _spans_overlap(schedule.start_time, schedule.end_time, other.start_time, other.end_time):
            raise ValidationError(
                f"Schedule overlaps with '{other.site_area.area_name}' at {other.start_time} on {day}.",
                code="overlapping_schedule",
            )


def assign_cleaner_area_schedule(
    *,
    assignment: CleanerSiteAssignment,
    site_area: SiteArea,
    operational_role: OperationalRole,
    day: date,
    start_time: time,
    end_time: time,
    shift: SiteShift | None = None,
    notes: str = "",
    actor: User,
) -> CleanerAreaSchedule:
    """Schedule a cleaner for an area/task/time on a date."""
    with transaction.atomic():
        schedule = CleanerAreaSchedule(
            assignment=assignment,
            site_area=site_area,
            operational_role=operational_role,
            date=day,
            start_time=start_time,
            end_time=end_time,
            shift=shift,
            notes=notes,
            is_active=True,
            created_by=actor,
            updated_by=actor,
        )
        schedule.full_clean()
        _validate_no_schedule_overlap(cleaner=assignment.cleaner, day=day, schedule=schedule)
        schedule.save()
        record_audit(
            action=AuditLog.Action.ASSIGN,
            actor=actor,
            entity=schedule,
            summary=f"Scheduled {assignment.cleaner.full_name} for {site_area.area_name} on {day}",
            after_data=model_data(schedule),
        )
    return schedule


def update_area_schedule(
    *,
    schedule: CleanerAreaSchedule,
    actor: User,
    site_area: SiteArea | None = None,
    operational_role: OperationalRole | None = None,
    start_time: time | None = None,
    end_time: time | None = None,
    shift: SiteShift | None = None,
    notes: str | None = None,
) -> CleanerAreaSchedule:
    """Update an area schedule, re-validating overlaps."""
    with transaction.atomic():
        before = model_data(schedule)
        if site_area is not None:
            schedule.site_area = site_area
        if operational_role is not None:
            schedule.operational_role = operational_role
        if start_time is not None:
            schedule.start_time = start_time
        if end_time is not None:
            schedule.end_time = end_time
        if shift is not None:
            schedule.shift = shift
        if notes is not None:
            schedule.notes = notes
        schedule.updated_by = actor
        schedule.full_clean()
        _validate_no_schedule_overlap(cleaner=schedule.assignment.cleaner, day=schedule.date, schedule=schedule)
        schedule.save()
        record_audit(
            action=AuditLog.Action.UPDATE,
            actor=actor,
            entity=schedule,
            summary=f"Updated area schedule for {schedule.assignment.cleaner.full_name} on {schedule.date}",
            before_data=before,
            after_data=model_data(schedule),
        )
    return schedule


def deactivate_area_schedule(*, schedule: CleanerAreaSchedule, actor: User) -> CleanerAreaSchedule:
    """Soft-remove an area schedule (history preserved)."""
    with transaction.atomic():
        schedule.is_active = False
        schedule.updated_by = actor
        schedule.save(update_fields=["is_active", "updated_by", "updated_at"])
        record_audit(
            action=AuditLog.Action.DELETE,
            actor=actor,
            entity=schedule,
            summary=f"Removed area schedule for {schedule.assignment.cleaner.full_name} on {schedule.date}",
            before_data=model_data(schedule),
        )
    return schedule


def copy_schedule_from_date(*, assignment: CleanerSiteAssignment, from_date: date, to_date: date, actor: User) -> int:
    """Copy a cleaner's active area schedules from one date to another.

    Returns the number of schedules created. Existing schedules on the target
    date are left untouched (no duplicates are created).
    """
    sources = list(CleanerAreaSchedule.objects.filter(assignment=assignment, date=from_date, is_active=True))
    if not sources:
        return 0
    with transaction.atomic():
        created = 0
        for source in sources:
            schedule = CleanerAreaSchedule(
                assignment=assignment,
                site_area=source.site_area,
                operational_role=source.operational_role,
                date=to_date,
                start_time=source.start_time,
                end_time=source.end_time,
                shift_id=source.shift_id,
                notes=source.notes,
                is_active=True,
                created_by=actor,
                updated_by=actor,
            )
            schedule.full_clean()
            try:
                _validate_no_schedule_overlap(cleaner=assignment.cleaner, day=to_date, schedule=schedule)
            except ValidationError:
                continue  # skip a copied slot that would overlap existing work
            schedule.save()
            created += 1
        record_audit(
            action=AuditLog.Action.CREATE,
            actor=actor,
            entity=assignment,
            summary=f"Copied {created} schedule(s) from {from_date} to {to_date}",
        )
    return created
