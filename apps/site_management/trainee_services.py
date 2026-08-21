"""Trainee lifecycle services.

The program is the single source of truth for cleaner conversion: a cleaner
becomes TRAINEE on program start and ACTIVE only via ``pass_trainee`` after a
final evaluation and verified identity. Fail/drop return the cleaner to a
non-active state. All transitions are transactional and audited.
"""

from __future__ import annotations

import datetime
from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.accounts.models import User
from apps.core.models import AuditLog
from apps.core.services import model_data, publish_domain_event, record_audit

from .models import (
    Cleaner,
    CleanerStatus,
    Site,
    TraineeEvaluation,
    TraineeProgram,
    TraineeProgramStatus,
)

EVENT_TRAINEE_STARTED = "TraineeStarted"
EVENT_TRAINEE_EXTENDED = "TraineeExtended"
EVENT_TRAINEE_PASSED = "TraineePassed"
EVENT_TRAINEE_FAILED = "TraineeFailed"
EVENT_TRAINEE_DROPPED = "TraineeDropped"


def _emit(event_type: str, program: TraineeProgram, actor: User, payload: dict[str, Any] | None = None) -> None:
    publish_domain_event(
        event_type=event_type,
        aggregate_type="site_management.traineeprogram",
        aggregate_id=program.pk,
        payload=payload or {"program_id": program.pk, "cleaner_id": program.cleaner_id, "site_id": program.site_id},
        created_by=actor,
    )


def _audit(
    action: AuditLog.Action, program: TraineeProgram, actor: User, summary: str, *, before: dict[str, Any] | None = None
) -> None:
    record_audit(
        action=action,
        actor=actor,
        entity=program,
        summary=summary,
        before_data=before,
        after_data=model_data(program),
    )


def _set_cleaner_status(cleaner: Cleaner, status: CleanerStatus) -> None:
    if cleaner.status != status:
        cleaner.status = status
        cleaner.save(update_fields=["status", "updated_at"])


def start_trainee_program(
    *,
    cleaner: Cleaner,
    site: Site,
    expected_end_date: datetime.date,
    start_date: datetime.date | None = None,
    assigned_site_supervisor: User | None = None,
    notes: str = "",
    actor: User,
) -> TraineeProgram:
    """Start a training program and move the cleaner to TRAINEE."""
    with transaction.atomic():
        if cleaner.status == CleanerStatus.ACTIVE:
            raise ValidationError("An active cleaner does not need a training program.", code="already_active")
        program = TraineeProgram(
            cleaner=cleaner,
            site=site,
            assigned_site_supervisor=assigned_site_supervisor,
            start_date=start_date or datetime.date.today(),
            expected_end_date=expected_end_date,
            status=TraineeProgramStatus.IN_TRAINING,
            notes=notes,
            created_by=actor,
            updated_by=actor,
        )
        program.full_clean()
        program.save()
        _set_cleaner_status(cleaner, CleanerStatus.TRAINEE)
        _audit(AuditLog.Action.CREATE, program, actor, f"Started training for {cleaner.full_name}")
        _emit(EVENT_TRAINEE_STARTED, program, actor)
    return program


def update_trainee_program(
    *,
    program: TraineeProgram,
    actor: User,
    assigned_site_supervisor: User | None = None,
    notes: str | None = None,
) -> TraineeProgram:
    """Update supervisor/notes on an active program."""
    with transaction.atomic():
        if not program.is_active_program:
            raise ValidationError("Completed programs cannot be edited.", code="program_completed")
        before = model_data(program)
        if assigned_site_supervisor is not None:
            program.assigned_site_supervisor = assigned_site_supervisor
        if notes is not None:
            program.notes = notes
        program.updated_by = actor
        program.save()
        _audit(
            AuditLog.Action.UPDATE,
            program,
            actor,
            f"Updated trainee program for {program.cleaner.full_name}",
            before=before,
        )
    return program


def transfer_trainee_program(
    *,
    program: TraineeProgram,
    destination_site: Site,
    effective_date: datetime.date,
    reason: str,
    actor: User,
) -> TraineeProgram:
    """Move an active programme while retaining its evaluations and full history."""
    if not program.is_active_program:
        raise ValidationError("Only an active trainee programme can be transferred.", code="program_completed")
    if not reason.strip():
        raise ValidationError("A transfer reason is required.", code="reason_required")
    with transaction.atomic():
        before = model_data(program)
        previous_site_name = program.site.name
        program.site = destination_site
        program.assigned_site_supervisor = None
        movement_note = f"Transferred from {previous_site_name} to {destination_site.name} on {effective_date}: {reason.strip()}"
        program.notes = f"{program.notes}\n{movement_note}".strip()
        program.updated_by = actor
        program.full_clean()
        program.save(update_fields=["site", "assigned_site_supervisor", "notes", "updated_by", "updated_at"])
        _audit(
            AuditLog.Action.UPDATE,
            program,
            actor,
            f"Transferred trainee programme for {program.cleaner.full_name} to {destination_site.name}",
            before=before,
        )
    return program


def extend_trainee_program(
    *,
    program: TraineeProgram,
    new_expected_end_date: datetime.date,
    reason: str,
    actor: User,
) -> TraineeProgram:
    """Extend a training program with a new expected end date."""
    with transaction.atomic():
        if not program.is_active_program:
            raise ValidationError("Only active programs can be extended.", code="program_completed")
        if not reason.strip():
            raise ValidationError("A reason is required to extend a program.", code="reason_required")
        before = model_data(program)
        program.expected_end_date = new_expected_end_date
        program.status = TraineeProgramStatus.EXTENDED
        program.notes = (program.notes + "\n" if program.notes else "") + f"Extended: {reason}"
        program.updated_by = actor
        program.full_clean()
        program.save()
        _audit(
            AuditLog.Action.UPDATE,
            program,
            actor,
            f"Extended trainee program for {program.cleaner.full_name}",
            before=before,
        )
        _emit(
            EVENT_TRAINEE_EXTENDED,
            program,
            actor,
            {"reason": reason, "new_expected_end_date": new_expected_end_date.isoformat()},
        )
    return program


def record_trainee_evaluation(
    *,
    program: TraineeProgram,
    evaluation_date: datetime.date,
    actor: User,
    attendance_score: int = 0,
    performance_score: int = 0,
    behavior_score: int = 0,
    skill_score: int = 0,
    total_score: int | None = None,
    comments: str = "",
    is_final: bool = False,
) -> TraineeEvaluation:
    """Record an evaluation; total_score is computed when not provided."""
    with transaction.atomic():
        evaluation = TraineeEvaluation(
            trainee_program=program,
            evaluation_date=evaluation_date,
            attendance_score=attendance_score,
            performance_score=performance_score,
            behavior_score=behavior_score,
            skill_score=skill_score,
            total_score=total_score,
            comments=comments,
            is_final=is_final,
            evaluated_by=actor,
        )
        evaluation.full_clean()
        evaluation.save()
        record_audit(
            action=AuditLog.Action.CREATE,
            actor=actor,
            entity=evaluation,
            summary=f"Evaluation recorded for {program.cleaner.full_name} (total {evaluation.total_score})",
            after_data=model_data(evaluation),
        )
    return evaluation


def _complete_program(
    *,
    program: TraineeProgram,
    status: TraineeProgramStatus,
    cleaner_status: CleanerStatus,
    actor: User,
    reason: str,
    event: str,
    actual_end_date: datetime.date | None = None,
) -> TraineeProgram:
    with transaction.atomic():
        if not program.is_active_program:
            raise ValidationError("Program is already completed.", code="program_completed")
        before = model_data(program)
        program.status = status
        program.actual_end_date = actual_end_date or datetime.date.today()
        program.notes = (program.notes + "\n" if program.notes else "") + f"{status.label}: {reason}"
        program.updated_by = actor
        program.full_clean()
        program.save()
        _set_cleaner_status(program.cleaner, cleaner_status)
        _audit(
            AuditLog.Action.STATUS_CHANGE,
            program,
            actor,
            f"Trainee program {status.value} for {program.cleaner.full_name}: {reason}",
            before=before,
        )
        _emit(event, program, actor, {"reason": reason})
    return program


def pass_trainee(
    *,
    program: TraineeProgram,
    actor: User,
    actual_end_date: datetime.date | None = None,
    reason: str = "Completed training",
) -> TraineeProgram:
    """Pass a trainee: requires a final evaluation and a verified identity."""
    if not program.evaluations.filter(is_final=True).exists():
        raise ValidationError(
            "A final evaluation is required before a trainee can pass.", code="final_evaluation_required"
        )
    if not program.cleaner.has_verified_id:
        raise ValidationError(
            "Trainee must have at least one verified identity document to pass.", code="verified_id_required"
        )
    return _complete_program(
        program=program,
        status=TraineeProgramStatus.PASSED,
        cleaner_status=CleanerStatus.ACTIVE,
        actor=actor,
        reason=reason,
        event=EVENT_TRAINEE_PASSED,
        actual_end_date=actual_end_date,
    )


def fail_trainee(*, program: TraineeProgram, actor: User, reason: str) -> TraineeProgram:
    """Fail a trainee (cleaner becomes inactive; no active assignment possible)."""
    if not reason.strip():
        raise ValidationError("A reason is required to fail a trainee.", code="reason_required")
    return _complete_program(
        program=program,
        status=TraineeProgramStatus.FAILED,
        cleaner_status=CleanerStatus.INACTIVE,
        actor=actor,
        reason=reason,
        event=EVENT_TRAINEE_FAILED,
    )


def drop_trainee(*, program: TraineeProgram, actor: User, reason: str) -> TraineeProgram:
    """Drop a trainee (cleaner becomes inactive)."""
    if not reason.strip():
        raise ValidationError("A reason is required to drop a trainee.", code="reason_required")
    return _complete_program(
        program=program,
        status=TraineeProgramStatus.DROPPED,
        cleaner_status=CleanerStatus.INACTIVE,
        actor=actor,
        reason=reason,
        event=EVENT_TRAINEE_DROPPED,
    )
