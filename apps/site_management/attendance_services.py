"""Attendance engine services.

Generation, bulk entry, submission workflow and locking. All writes are
transactional and audited; submissions emit an ``AttendanceSubmitted`` domain
event through the outbox.
"""

from __future__ import annotations

import datetime
from typing import Any

from constance import config
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.accounts.models import User
from apps.core.models import AuditLog
from apps.core.services import model_data, publish_domain_event, record_audit

from .models import (
    AttendanceRecord,
    AttendanceReviewStatus,
    AttendanceStatus,
    Cleaner,
    CleanerAssignmentStatus,
    CleanerShiftAssignment,
    CleanerSiteAssignment,
    CleanerStatus,
    Site,
    WorkMode,
)

EVENT_ATTENDANCE_SUBMITTED = "AttendanceSubmitted"


def _assignment_date_cover_filter(day: datetime.date) -> Q:
    return Q(start_date__lte=day) & (Q(end_date__isnull=True) | Q(end_date__gte=day))


def _scheduled_pairs(site: Site, day: datetime.date, shift_id: int | None = None) -> list[tuple[int, int | None]]:
    """(cleaner_id, shift_id|None) pairs scheduled for a site on a day."""
    assignments = CleanerSiteAssignment.objects.filter(
        site=site,
        status=CleanerAssignmentStatus.ACTIVE,
        cleaner__status=CleanerStatus.ACTIVE,
    ).filter(_assignment_date_cover_filter(day))
    pairs: list[tuple[int, int | None]] = []

    full_time_assignments = assignments.filter(assignment_type="full_time")
    if site.work_mode != WorkMode.SHIFT:
        pairs.extend((a.cleaner_id, None) for a in full_time_assignments)

    shift_assignments = assignments.filter(assignment_type="shift")
    if site.work_mode != WorkMode.FULL_TIME:
        bindings = CleanerShiftAssignment.objects.filter(
            assignment__in=shift_assignments,
            is_active=True,
            effective_from__lte=day,
        ).filter(Q(effective_to__isnull=True) | Q(effective_to__gte=day))
        if shift_id:
            bindings = bindings.filter(shift_id=shift_id)
        pairs.extend((b.assignment.cleaner_id, b.shift_id) for b in bindings.select_related("assignment"))

    return pairs


def generate_daily_attendance_sheet(
    *,
    site_id: int,
    day: datetime.date,
    shift_id: int | None = None,
    actor: User | None = None,
) -> list[AttendanceRecord]:
    """Create DRAFT placeholders for every scheduled cleaner/shift for a day.

    Idempotent — existing records are never duplicated. Returns the day's
    records.
    """
    site = Site.objects.filter(pk=site_id).first()
    if site is None:
        raise ValidationError("Site not found.")
    with transaction.atomic():
        pairs = _scheduled_pairs(site, day, shift_id)
        existing = AttendanceRecord.objects.filter(site_id=site_id, attendance_date=day)
        if shift_id:
            existing = existing.filter(shift_id=shift_id)
        existing_keys = {(row["cleaner_id"], row["shift_id"]) for row in existing.values("cleaner_id", "shift_id")}
        to_create = [
            AttendanceRecord(
                cleaner_id=cleaner_id,
                site=site,
                shift_id=shift_id,
                attendance_date=day,
                status=AttendanceStatus.SCHEDULED,
                review_status=AttendanceReviewStatus.DRAFT,
                recorded_by=actor,
                created_by=actor,
                updated_by=actor,
            )
            for cleaner_id, shift_id in pairs
            if (cleaner_id, shift_id) not in existing_keys
        ]
        if to_create:
            AttendanceRecord.objects.bulk_create(to_create)
        if actor:
            record_audit(
                action=AuditLog.Action.CREATE,
                actor=actor,
                entity=site,
                summary=f"Generated attendance sheet for {day}",
            )
    return _day_records(site_id, day, shift_id)


def _day_records(site_id: int, day: datetime.date, shift_id: int | None) -> list[AttendanceRecord]:
    qs = AttendanceRecord.objects.filter(site_id=site_id, attendance_date=day).select_related(
        "cleaner", "site", "shift"
    )
    if shift_id:
        qs = qs.filter(shift_id=shift_id)
    return list(qs.order_by("cleaner__last_name", "shift__shift_name"))


def _validate_future(day: datetime.date, *, allow_future: bool, reason: str = "") -> None:
    if day > timezone.localdate() and not allow_future:
        raise ValidationError(
            "attendance_date cannot be in the future (unless an admin override is provided).",
            code="future_date",
        )


def _entry_record(*, site: Site, day: datetime.date, entry: dict[str, Any], actor: User) -> AttendanceRecord | None:
    """Resolve/validate a bulk entry to an existing editable record or a new one."""
    status = entry.get("status") or AttendanceStatus.SCHEDULED
    check_in = entry.get("check_in_time")
    check_out = entry.get("check_out_time")
    record_id = entry.get("record_id")
    cleaner_id = entry.get("cleaner_id")
    entry_shift_id = entry.get("shift_id")

    if record_id:
        record = AttendanceRecord.objects.filter(pk=record_id, site=site, attendance_date=day).first()
        if record is None:
            raise ValidationError(f"Attendance record {record_id} does not exist for this site/date.")
        if not record.is_editable:
            raise ValidationError(
                f"Record {record.pk} is {record.review_status} and cannot be edited.", code="not_editable"
            )
    else:
        if not cleaner_id:
            raise ValidationError("Each entry needs record_id or cleaner_id.")
        cleaner = Cleaner.objects.filter(pk=cleaner_id).first()
        if cleaner is None:
            raise ValidationError(f"Cleaner {cleaner_id} not found.")
        record = AttendanceRecord.objects.filter(
            site=site, cleaner=cleaner, attendance_date=day, shift_id=entry_shift_id
        ).first()
        if record is not None and not record.is_editable:
            raise ValidationError(
                f"Record for {cleaner.full_name} is {record.review_status} and cannot be edited.",
                code="not_editable",
            )
        if record is None:
            record = AttendanceRecord(
                site=site,
                cleaner=cleaner,
                shift_id=entry_shift_id,
                attendance_date=day,
                status=AttendanceStatus.SCHEDULED,
                review_status=AttendanceReviewStatus.DRAFT,
                recorded_by=actor,
                created_by=actor,
                updated_by=actor,
            )

    record.status = AttendanceStatus(status)
    record.check_in_time = check_in
    record.check_out_time = check_out
    if entry.get("notes") is not None:
        record.notes = entry["notes"]
    record.recorded_by = actor
    record.updated_by = actor
    return record


def _validate_work_mode_entry(site: Site, entry: dict[str, Any]) -> None:
    entry_shift_id = entry.get("shift_id")
    if site.work_mode == WorkMode.FULL_TIME and entry_shift_id is not None:
        raise ValidationError("Full-time sites cannot record attendance against a shift.", code="shift_not_allowed")
    if site.work_mode == WorkMode.SHIFT and entry_shift_id is None:
        raise ValidationError("Shift sites require a shift on every attendance record.", code="shift_required")


def bulk_upsert_attendance(
    *,
    site_id: int,
    day: datetime.date,
    entries: list[dict[str, Any]],
    user: User,
    shift_id: int | None = None,
    allow_future: bool = False,
) -> list[AttendanceRecord]:
    """Create/update many attendance records in one request (bulk entry).

    Entries reference an existing ``record_id`` or a ``cleaner_id`` (plus
    optional ``shift_id``). Only DRAFT/RETURNED records are edited.
    """
    _validate_future(day, allow_future=allow_future)
    site = Site.objects.filter(pk=site_id).first()
    if site is None:
        raise ValidationError("Site not found.")
    with transaction.atomic():
        records = []
        for entry in entries:
            _validate_work_mode_entry(site, entry)
            record = _entry_record(site=site, day=day, entry=entry, actor=user)
            if record is not None:
                records.append(record)
        if records:
            AttendanceRecord.objects.bulk_create([r for r in records if r.pk is None])
            AttendanceRecord.objects.bulk_update(
                [r for r in records if r.pk is not None],
                ["status", "check_in_time", "check_out_time", "notes", "recorded_by", "updated_by", "updated_at"],
            )
            record_audit(
                action=AuditLog.Action.UPDATE,
                actor=user,
                entity=site,
                summary=f"Bulk attendance entry for {day} ({len(records)} records)",
            )
    return _day_records(site_id, day, shift_id)


def save_attendance_draft(
    *,
    site_id: int,
    day: datetime.date,
    entries: list[dict[str, Any]],
    user: User,
    shift_id: int | None = None,
) -> list[AttendanceRecord]:
    """Save a draft batch of attendance entries (thin alias of bulk upsert)."""
    return bulk_upsert_attendance(site_id=site_id, day=day, entries=entries, user=user, shift_id=shift_id)


def record_single_attendance(
    *,
    record_id: int,
    status: AttendanceStatus,
    user: User,
    check_in_time: Any = None,
    check_out_time: Any = None,
    notes: str = "",
) -> AttendanceRecord:
    """Update a single editable attendance record."""
    record = AttendanceRecord.objects.select_related("site", "cleaner").filter(pk=record_id).first()
    if record is None:
        raise ValidationError("Attendance record not found.")
    if not record.is_editable:
        raise ValidationError(f"Record is {record.review_status} and cannot be edited.", code="not_editable")
    with transaction.atomic():
        before = model_data(record)
        record.status = status
        record.check_in_time = check_in_time
        record.check_out_time = check_out_time
        if notes:
            record.notes = notes
        record.recorded_by = user
        record.updated_by = user
        record.save()
        record_audit(
            action=AuditLog.Action.UPDATE,
            actor=user,
            entity=record,
            summary=f"Attendance for {record.cleaner.full_name} marked {status.value}",
            before_data=before,
            after_data=model_data(record),
        )
    return record


def _group_records(site_id: int, day: datetime.date, shift_id: int | None) -> list[AttendanceRecord]:
    return _day_records(site_id, day, shift_id)


def submit_daily_attendance(*, site_id: int, day: datetime.date, user: User, shift_id: int | None = None) -> int:
    """Submit a day's attendance once every scheduled cleaner is marked."""
    with transaction.atomic():
        records = _group_records(site_id, day, shift_id)
        if not records:
            raise ValidationError("No attendance records exist for this day.", code="nothing_to_submit")
        still_scheduled = [r for r in records if r.status == AttendanceStatus.SCHEDULED]
        if still_scheduled:
            names = ", ".join(r.cleaner.full_name for r in still_scheduled[:5])
            raise ValidationError(
                f"All scheduled cleaners must be marked before submission. Still scheduled: {names}.",
                code="scheduled_not_marked",
            )
        now = timezone.now()
        for record in records:
            record.review_status = AttendanceReviewStatus.SUBMITTED
            record.submitted_at = now
            record.updated_by = user
            record.recorded_by = user
        AttendanceRecord.objects.bulk_update(
            records, ["review_status", "submitted_at", "updated_by", "recorded_by", "updated_at"]
        )
        record_audit(
            action=AuditLog.Action.STATUS_CHANGE,
            actor=user,
            entity=records[0].site,
            summary=f"Attendance submitted for {day} ({len(records)} records)",
        )
        for record in records:
            publish_domain_event(
                event_type=EVENT_ATTENDANCE_SUBMITTED,
                aggregate_type="site_management.attendancerecord",
                aggregate_id=record.pk,
                payload={
                    "record_id": record.pk,
                    "cleaner_id": record.cleaner_id,
                    "site_id": site_id,
                    "attendance_date": day.isoformat(),
                },
                created_by=user,
            )
    return len(records)


def return_attendance_record(*, record: AttendanceRecord, user: User, reason: str) -> AttendanceRecord:
    """Return a single submitted record to the site for correction."""
    with transaction.atomic():
        if record.review_status == AttendanceReviewStatus.LOCKED:
            raise ValidationError("Locked records cannot be returned.", code="locked")
        before = model_data(record)
        record.review_status = AttendanceReviewStatus.RETURNED
        record.return_reason = reason
        record.updated_by = user
        record.save(update_fields=["review_status", "return_reason", "updated_by", "updated_at"])
        record_audit(
            action=AuditLog.Action.UPDATE,
            actor=user,
            entity=record,
            summary=f"Attendance returned: {reason}",
            before_data=before,
            after_data=model_data(record),
        )
    return record


def return_attendance_group(
    *, site_id: int, day: datetime.date, user: User, reason: str, shift_id: int | None = None
) -> int:
    """Return a day's submitted/reviewed attendance group for correction."""
    with transaction.atomic():
        records = [
            r for r in _group_records(site_id, day, shift_id) if r.review_status != AttendanceReviewStatus.LOCKED
        ]
        if not records:
            raise ValidationError("No returnable records found for this day.", code="nothing_to_return")
        for record in records:
            record.review_status = AttendanceReviewStatus.RETURNED
            record.return_reason = reason
            record.updated_by = user
        AttendanceRecord.objects.bulk_update(records, ["review_status", "return_reason", "updated_by", "updated_at"])
        record_audit(
            action=AuditLog.Action.UPDATE,
            actor=user,
            entity=records[0].site,
            summary=f"Attendance group returned for {day} ({len(records)} records): {reason}",
        )
    return len(records)


def review_attendance_group(*, site_id: int, day: datetime.date, user: User, shift_id: int | None = None) -> int:
    """Review a submitted day's attendance and apply auto-lock when due."""
    with transaction.atomic():
        records = [
            r for r in _group_records(site_id, day, shift_id) if r.review_status == AttendanceReviewStatus.SUBMITTED
        ]
        if not records:
            raise ValidationError("No submitted records found for this day.", code="nothing_to_review")
        for record in records:
            record.review_status = AttendanceReviewStatus.REVIEWED
            record.updated_by = user
        AttendanceRecord.objects.bulk_update(records, ["review_status", "updated_by", "updated_at"])
        record_audit(
            action=AuditLog.Action.UPDATE,
            actor=user,
            entity=records[0].site,
            summary=f"Attendance reviewed for {day} ({len(records)} records)",
        )
    lock_attendance_if_required(site_id=site_id, day=day, shift_id=shift_id, user=user)
    return len(records)


def review_attendance_record(*, record: AttendanceRecord, user: User) -> AttendanceRecord:
    """Review a single submitted record."""
    with transaction.atomic():
        if record.review_status != AttendanceReviewStatus.SUBMITTED:
            raise ValidationError("Only submitted records can be reviewed.", code="invalid_review")
        record.review_status = AttendanceReviewStatus.REVIEWED
        record.updated_by = user
        record.save(update_fields=["review_status", "updated_by", "updated_at"])
        record_audit(
            action=AuditLog.Action.UPDATE,
            actor=user,
            entity=record,
            summary="Attendance record reviewed",
            after_data=model_data(record),
        )
    return record


def lock_attendance_if_required(*, site_id: int, day: datetime.date, shift_id: int | None = None, user: User) -> int:
    """Lock reviewed records once the auto-lock window has elapsed."""
    cutoff = timezone.localdate() - datetime.timedelta(days=int(config.ATTENDANCE_LOCK_AFTER_DAYS))
    qs = AttendanceRecord.objects.filter(
        site_id=site_id, attendance_date__lte=cutoff, review_status=AttendanceReviewStatus.REVIEWED
    )
    if shift_id:
        qs = qs.filter(shift_id=shift_id)
    locked = qs.count()
    if locked:
        qs.update(review_status=AttendanceReviewStatus.LOCKED)
        site = Site.objects.filter(pk=site_id).first()
        record_audit(
            action=AuditLog.Action.UPDATE,
            actor=user,
            entity=site,
            summary=f"Auto-locked {locked} attendance record(s) older than the lock window",
        )
    return locked
