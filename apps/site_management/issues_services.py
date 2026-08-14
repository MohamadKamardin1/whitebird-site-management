"""Issue tracking and job/work order services.

The issue lifecycle (OPEN → UNDER_REVIEW → ASSIGNED → ... → CLOSED, with
escalation) and the job lifecycle (OPEN → ASSIGNED → IN_PROGRESS → COMPLETED →
VERIFIED → CLOSED, with REOPENED preserving history) are controlled here.
All writes are transactional and audited; every transition emits the matching
domain event. Closing a job requires prior verification.
"""

from __future__ import annotations

import datetime
from typing import Any

from constance import config
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import RoleCode, User
from apps.core.files import validate_file_extension, validate_file_size
from apps.core.models import AuditLog
from apps.core.services import model_data, publish_domain_event, record_audit

from .models import (
    Cleaner,
    Inspection,
    Issue,
    IssueCategory,
    IssuePriority,
    IssueSource,
    IssueStatus,
    Job,
    JobStatus,
    Site,
    SiteArea,
)
from .policies import can_assign_job, can_verify_job, ensure
from .services import notify_role

EVENT_ISSUE_CREATED = "IssueCreated"
EVENT_ISSUE_ESCALATED = "IssueEscalated"
EVENT_JOB_ASSIGNED = "JobAssigned"
EVENT_JOB_COMPLETED = "JobCompleted"
EVENT_JOB_VERIFIED = "JobVerified"


def _emit(event_type: str, entity: Any, actor: User, payload: dict[str, Any] | None = None) -> None:
    publish_domain_event(
        event_type=event_type,
        aggregate_type=f"site_management.{entity._meta.model_name}",
        aggregate_id=entity.pk,
        payload=payload or {"id": entity.pk, "site_id": getattr(entity, "site_id", None)},
        created_by=actor,
    )


def _audit(
    action: AuditLog.Action,
    entity: Any,
    actor: User,
    summary: str,
    *,
    before: dict[str, Any] | None = None,
) -> None:
    record_audit(
        action=action,
        actor=actor,
        entity=entity,
        summary=summary,
        before_data=before,
        after_data=model_data(entity),
    )


# --------------------------------------------------------------------------- #
# Issues
# --------------------------------------------------------------------------- #


def create_issue(
    *,
    title: str,
    site: Site,
    raised_by: User,
    actor: User,
    description: str = "",
    source: str = IssueSource.MANUAL,
    issue_category: str = IssueCategory.OTHER,
    priority: str = IssuePriority.MEDIUM,
    area: SiteArea | None = None,
    cleaner: Cleaner | None = None,
    inspection: Inspection | None = None,
    due_date: datetime.date | None = None,
) -> Issue:
    """Raise an issue at a site (manual or auto-generated from inspections)."""
    with transaction.atomic():
        issue = Issue(
            title=title,
            description=description,
            source=source,
            site=site,
            area=area,
            cleaner=cleaner,
            inspection=inspection,
            issue_category=issue_category,
            priority=priority,
            status=IssueStatus.OPEN,
            raised_by=raised_by,
            due_date=due_date,
            created_by=actor,
            updated_by=actor,
        )
        issue.full_clean()
        issue.save()
        _audit(AuditLog.Action.CREATE, issue, actor, f"Raised issue: {title}")
        _emit(EVENT_ISSUE_CREATED, issue, actor)
    return issue


def update_issue(
    *,
    issue: Issue,
    actor: User,
    title: str | None = None,
    description: str | None = None,
    issue_category: str | None = None,
    priority: str | None = None,
    area: SiteArea | None = None,
    cleaner: Cleaner | None = None,
    due_date: datetime.date | None = None,
) -> Issue:
    """Update an open issue's metadata."""
    with transaction.atomic():
        if issue.is_terminal:
            raise ValidationError("Closed issues cannot be edited.", code="issue_closed")
        before = model_data(issue)
        if title is not None:
            issue.title = title
        if description is not None:
            issue.description = description
        if issue_category is not None:
            issue.issue_category = issue_category
        if priority is not None:
            issue.priority = priority
        if area is not None:
            issue.area = area
        if cleaner is not None:
            issue.cleaner = cleaner
        if due_date is not None:
            issue.due_date = due_date
        issue.updated_by = actor
        issue.save()
        _audit(AuditLog.Action.UPDATE, issue, actor, f"Updated issue: {issue.title}", before=before)
    return issue


def review_issue(*, issue: Issue, actor: User, notes: str = "") -> Issue:
    """Move an open issue into UNDER_REVIEW by zone-level management."""
    with transaction.atomic():
        if issue.status not in {IssueStatus.OPEN, IssueStatus.REOPENED}:
            raise ValidationError("Only open issues can be reviewed.", code="invalid_status")
        before = model_data(issue)
        issue.status = IssueStatus.UNDER_REVIEW
        issue.description = (issue.description + "\n" if issue.description else "") + (
            f"Review: {notes}" if notes else "Under review"
        )
        issue.updated_by = actor
        issue.save()
        _audit(AuditLog.Action.STATUS_CHANGE, issue, actor, f"Issue {issue.pk} under review", before=before)
    return issue


def escalate_issue(*, issue: Issue, actor: User, reason: str = "") -> Issue:
    """Escalate an issue: raise its level and flag it for senior attention."""
    with transaction.atomic():
        if issue.is_terminal:
            raise ValidationError("Closed issues cannot be escalated.", code="issue_closed")
        if not reason.strip():
            raise ValidationError("A reason is required to escalate.", code="reason_required")
        before = model_data(issue)
        issue.escalation_level += 1
        issue.is_escalated = True
        issue.description = (
            issue.description + "\n" if issue.description else ""
        ) + f"Escalated ({issue.escalation_level}): {reason}"
        issue.updated_by = actor
        issue.save()
        _audit(
            AuditLog.Action.STATUS_CHANGE,
            issue,
            actor,
            f"Issue {issue.pk} escalated to level {issue.escalation_level}",
            before=before,
        )
        _emit(EVENT_ISSUE_ESCALATED, issue, actor, {"level": issue.escalation_level, "reason": reason})
        notify_role(
            role=RoleCode.GENERAL_SUPERVISOR,
            verb="issue_escalated",
            title=f"Issue escalated: {issue.title}",
            body=f"{issue.site.name} — {issue.title} escalated to level {issue.escalation_level}.",
            object_type="site_management.issue",
            object_id=issue.pk,
            link=f"/admin/site_management/issue/{issue.pk}/change/",
            dedup_key=f"issue-escalated:{issue.pk}",
        )
    return issue


def _set_issue_assigned(issue: Issue, actor: User) -> None:
    """Mark an issue ASSIGNED once at least one of its jobs is being worked."""
    if issue.status in {IssueStatus.OPEN, IssueStatus.UNDER_REVIEW, IssueStatus.REOPENED}:
        before = model_data(issue)
        issue.status = IssueStatus.ASSIGNED
        issue.updated_by = actor
        issue.save(update_fields=["status", "updated_by", "updated_at"])
        record_audit(
            action=AuditLog.Action.STATUS_CHANGE,
            actor=actor,
            entity=issue,
            summary=f"Issue {issue.pk} assigned",
            before_data=before,
            after_data=model_data(issue),
        )


def _close_issue_if_all_jobs_closed(issue: Issue, actor: User) -> None:
    if issue.status in {IssueStatus.CLOSED}:
        return
    jobs = issue.jobs.all()
    if not jobs.exists():
        return
    if all(job.status == JobStatus.CLOSED for job in jobs):
        before = model_data(issue)
        issue.status = IssueStatus.CLOSED
        issue.closed_at = timezone.now()
        issue.updated_by = actor
        issue.save(update_fields=["status", "closed_at", "updated_by", "updated_at"])
        record_audit(
            action=AuditLog.Action.STATUS_CHANGE,
            actor=actor,
            entity=issue,
            summary=f"Issue {issue.pk} closed (all jobs closed)",
            before_data=before,
            after_data=model_data(issue),
        )


# --------------------------------------------------------------------------- #
# Jobs
# --------------------------------------------------------------------------- #


def create_job(
    *,
    job_title: str,
    site: Site,
    assigned_by: User,
    actor: User,
    description: str = "",
    issue: Issue | None = None,
    assigned_to_user: User | None = None,
    assigned_to_cleaner: Cleaner | None = None,
    due_date: datetime.date | None = None,
    priority: str = IssuePriority.MEDIUM,
) -> Job:
    """Create a job (standalone or spawned from an issue)."""
    with transaction.atomic():
        job = Job(
            issue=issue,
            job_title=job_title,
            description=description,
            site=site,
            assigned_to_user=assigned_to_user,
            assigned_to_cleaner=assigned_to_cleaner,
            assigned_by=assigned_by,
            due_date=due_date or (datetime.date.today() + datetime.timedelta(days=3)),
            priority=priority,
            status=JobStatus.OPEN,
            created_by=actor,
            updated_by=actor,
        )
        job.full_clean()
        job.save()
        _audit(AuditLog.Action.CREATE, job, actor, f"Created job: {job_title}")
        if assigned_to_user or assigned_to_cleaner:
            _transition(job, JobStatus.ASSIGNED, actor, emit=EVENT_JOB_ASSIGNED)
        if issue is not None:
            _set_issue_assigned(issue, actor)
    return job


def assign_job_from_issue(
    *,
    issue: Issue,
    actor: User,
    job_title: str | None = None,
    description: str = "",
    assigned_to_user: User | None = None,
    assigned_to_cleaner: Cleaner | None = None,
    due_date: datetime.date | None = None,
    priority: str | None = None,
) -> Job:
    """Spawn an assigned job directly from an issue."""
    return create_job(
        job_title=job_title or issue.title,
        site=issue.site,
        assigned_by=actor,
        actor=actor,
        description=description or issue.description,
        issue=issue,
        assigned_to_user=assigned_to_user,
        assigned_to_cleaner=assigned_to_cleaner,
        due_date=due_date,
        priority=priority or issue.priority,
    )


def update_job(
    *,
    job: Job,
    actor: User,
    job_title: str | None = None,
    description: str | None = None,
    due_date: datetime.date | None = None,
    priority: str | None = None,
) -> Job:
    """Update job metadata while it is not terminal."""
    with transaction.atomic():
        if job.is_terminal:
            raise ValidationError("Closed jobs cannot be edited.", code="job_closed")
        before = model_data(job)
        if job_title is not None:
            job.job_title = job_title
        if description is not None:
            job.description = description
        if due_date is not None:
            job.due_date = due_date
        if priority is not None:
            job.priority = priority
        job.updated_by = actor
        job.save()
        _audit(AuditLog.Action.UPDATE, job, actor, f"Updated job: {job.job_title}", before=before)
    return job


def _transition(job: Job, status: str, actor: User, *, emit: str | None = None, notes: str = "") -> Job:
    """Apply a job status transition with audit + optional domain event."""
    before = model_data(job)
    job.status = status
    if notes:
        job.completion_notes = (job.completion_notes + "\n" if job.completion_notes else "") + notes
    job.updated_by = actor
    job.save()
    record_audit(
        action=AuditLog.Action.STATUS_CHANGE,
        actor=actor,
        entity=job,
        summary=f"Job {job.pk} -> {status}",
        before_data=before,
        after_data=model_data(job),
    )
    if emit:
        _emit(emit, job, actor)
    return job


def assign_job(
    *,
    job: Job,
    actor: User,
    assigned_to_user: User | None = None,
    assigned_to_cleaner: Cleaner | None = None,
) -> Job:
    """Assign an open/reopened job to a user or cleaner."""
    with transaction.atomic():
        ensure(actor, can_assign_job(actor, job), "You do not have permission to assign jobs.")
        if job.status not in {JobStatus.OPEN, JobStatus.REOPENED}:
            raise ValidationError("Only open or reopened jobs can be assigned.", code="invalid_status")
        if not (assigned_to_user or assigned_to_cleaner):
            raise ValidationError("Assign the job to a user or cleaner.", code="assignee_required")
        before = model_data(job)
        job.assigned_to_user = assigned_to_user
        job.assigned_to_cleaner = assigned_to_cleaner
        job.assigned_by = actor
        job.status = JobStatus.ASSIGNED
        job.updated_by = actor
        job.save()
        record_audit(
            action=AuditLog.Action.ASSIGN,
            actor=actor,
            entity=job,
            summary=f"Job {job.pk} assigned",
            before_data=before,
            after_data=model_data(job),
        )
        _emit(
            EVENT_JOB_ASSIGNED,
            job,
            actor,
            {
                "assigned_to_user_id": getattr(assigned_to_user, "pk", None),
                "assigned_to_cleaner_id": getattr(assigned_to_cleaner, "pk", None),
            },
        )
        if job.issue_id:
            issue = job.issue
            if issue is not None:
                _set_issue_assigned(issue, actor)
    return job


def start_job(*, job: Job, actor: User) -> Job:
    """Begin work on an assigned job."""
    with transaction.atomic():
        if job.status != JobStatus.ASSIGNED:
            raise ValidationError("Only assigned jobs can be started.", code="invalid_status")
        _transition(job, JobStatus.IN_PROGRESS, actor)
        issue = job.issue
        if issue is not None:
            _set_issue_assigned(issue, actor)
    return job


def complete_job(
    *,
    job: Job,
    actor: User,
    completion_notes: str = "",
    completion_photo: Any = None,
) -> Job:
    """Complete a job; photo evidence is enforced when configured."""
    with transaction.atomic():
        from apps.accounts.permissions import user_can_manage_site

        ensure(
            actor, actor.is_system_admin or user_can_manage_site(actor, job.site_id), "You cannot complete this job."
        )
        if job.status not in {JobStatus.ASSIGNED, JobStatus.IN_PROGRESS}:
            raise ValidationError("Only assigned or in-progress jobs can be completed.", code="invalid_status")
        if completion_photo is None and config.JOB_COMPLETION_PHOTO_REQUIRED:
            raise ValidationError("Photo evidence is required to complete this job.", code="photo_required")
        if completion_photo is not None:
            validate_file_extension(completion_photo)
            validate_file_size(completion_photo)
            job.file = completion_photo
            job.original_filename = completion_photo.name or ""
            job.content_type = getattr(completion_photo, "content_type", "")
            job.size_bytes = getattr(completion_photo, "size", 0)
        job.completed_at = timezone.now()
        _transition(job, JobStatus.COMPLETED, actor, emit=EVENT_JOB_COMPLETED, notes=completion_notes)
        issue = job.issue
        if issue is not None:
            _close_issue_if_all_jobs_closed(issue, actor)
    return job


def verify_job(*, job: Job, actor: User) -> Job:
    """Verify a completed job; the job must be verified before it can close."""
    with transaction.atomic():
        ensure(actor, can_verify_job(actor, job), "You do not have permission to verify jobs.")
        if job.status != JobStatus.COMPLETED:
            raise ValidationError("Only completed jobs can be verified.", code="invalid_status")
        before = model_data(job)
        job.status = JobStatus.VERIFIED
        job.verified_by = actor
        job.verified_at = timezone.now()
        job.updated_by = actor
        job.save()
        record_audit(
            action=AuditLog.Action.STATUS_CHANGE,
            actor=actor,
            entity=job,
            summary=f"Job {job.pk} verified by {actor}",
            before_data=before,
            after_data=model_data(job),
        )
        _emit(EVENT_JOB_VERIFIED, job, actor)
    return job


def close_job(*, job: Job, actor: User) -> Job:
    """Close a verified job (verification is required before closure)."""
    with transaction.atomic():
        if job.status != JobStatus.VERIFIED:
            raise ValidationError("Jobs must be verified before they can be closed.", code="verify_required")
        before = model_data(job)
        job.status = JobStatus.CLOSED
        job.closed_at = timezone.now()
        job.updated_by = actor
        job.save()
        record_audit(
            action=AuditLog.Action.STATUS_CHANGE,
            actor=actor,
            entity=job,
            summary=f"Job {job.pk} closed",
            before_data=before,
            after_data=model_data(job),
        )
        issue = job.issue
        if issue is not None:
            _close_issue_if_all_jobs_closed(issue, actor)
    return job


def reopen_job(*, job: Job, actor: User, reason: str) -> Job:
    """Reopen a closed/completed job; history (notes/photos) is preserved."""
    with transaction.atomic():
        if job.status not in {JobStatus.CLOSED, JobStatus.COMPLETED, JobStatus.VERIFIED}:
            raise ValidationError("Only closed, completed or verified jobs can be reopened.", code="invalid_status")
        if not reason.strip():
            raise ValidationError("A reason is required to reopen a job.", code="reason_required")
        before = model_data(job)
        job.status = JobStatus.REOPENED
        job.verified_by = None
        job.verified_at = None
        job.completed_at = None
        job.closed_at = None
        job.completion_notes = (job.completion_notes + "\n" if job.completion_notes else "") + f"Reopened: {reason}"
        job.updated_by = actor
        job.save()
        record_audit(
            action=AuditLog.Action.STATUS_CHANGE,
            actor=actor,
            entity=job,
            summary=f"Job {job.pk} reopened: {reason}",
            before_data=before,
            after_data=model_data(job),
        )
    return job


def upload_job_photo(*, job: Job, uploaded_file: Any, actor: User) -> Job:
    """Attach a private completion photo to a non-terminal job."""
    with transaction.atomic():
        if job.is_terminal:
            raise ValidationError("Closed jobs cannot be changed.", code="job_closed")
        validate_file_extension(uploaded_file)
        validate_file_size(uploaded_file)
        job.file = uploaded_file
        job.original_filename = uploaded_file.name or ""
        job.content_type = getattr(uploaded_file, "content_type", "")
        job.size_bytes = getattr(uploaded_file, "size", 0)
        job.updated_by = actor
        job.save()
        record_audit(
            action=AuditLog.Action.UPDATE,
            actor=actor,
            entity=job,
            summary=f"Completion photo uploaded for job {job.pk}",
        )
    return job
