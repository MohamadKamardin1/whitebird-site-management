"""Issue and job read selectors (role-scoped, query-efficient)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.db.models import Count, Q, QuerySet
from django.utils import timezone

from apps.accounts.models import User

from .models import Issue, IssueStatus, Job, JobStatus
from .scoping import visible_sites


@dataclass(frozen=True)
class IssueFilter:
    site_id: int | None = None
    status: str | None = None
    priority: str | None = None
    category: str | None = None
    source: str | None = None
    assigned_to_id: int | None = None
    escalated: bool | None = None


@dataclass(frozen=True)
class JobFilter:
    site_id: int | None = None
    status: str | None = None
    priority: str | None = None
    issue_id: int | None = None
    assigned_to_user_id: int | None = None


def _scoped(user: User) -> Q:
    if user.is_system_admin:
        return Q()
    return Q(site__in=visible_sites(user))


def issue_list(user: User, spec: IssueFilter) -> QuerySet[Issue]:
    """Issues in the user's scope with filters (one query)."""
    qs: QuerySet[Issue] = Issue.objects.select_related(
        "site", "area", "cleaner", "inspection", "raised_by", "assigned_to"
    ).annotate(job_count=Count("jobs", distinct=True))
    if not user.is_system_admin:
        qs = qs.filter(_scoped(user))
    if spec.site_id:
        qs = qs.filter(site_id=spec.site_id)
    if spec.status:
        qs = qs.filter(status=spec.status)
    if spec.priority:
        qs = qs.filter(priority=spec.priority)
    if spec.category:
        qs = qs.filter(issue_category=spec.category)
    if spec.source:
        qs = qs.filter(source=spec.source)
    if spec.assigned_to_id:
        qs = qs.filter(assigned_to_id=spec.assigned_to_id)
    if spec.escalated is not None:
        qs = qs.filter(is_escalated=spec.escalated)
    return qs


def get_issue_or_none(issue_id: int) -> Issue | None:
    return (
        Issue.objects.select_related("site", "area", "cleaner", "inspection", "raised_by", "assigned_to")
        .prefetch_related("jobs")
        .filter(pk=issue_id)
        .first()
    )


def issue_summary(user: User, spec: IssueFilter) -> dict[str, Any]:
    """Counts by status/priority/category plus open/escalated totals."""
    qs = issue_list(user, spec)
    statuses = {row["status"]: row["n"] for row in qs.values("status").order_by().annotate(n=Count("pk"))}
    priorities = {row["priority"]: row["n"] for row in qs.values("priority").order_by().annotate(n=Count("pk"))}
    categories = {
        row["issue_category"]: row["n"] for row in qs.values("issue_category").order_by().annotate(n=Count("pk"))
    }
    return {
        "total_issues": sum(statuses.values()),
        "open": statuses.get(IssueStatus.OPEN.value, 0),
        "under_review": statuses.get(IssueStatus.UNDER_REVIEW.value, 0),
        "assigned": statuses.get(IssueStatus.ASSIGNED.value, 0),
        "in_progress": statuses.get(IssueStatus.IN_PROGRESS.value, 0),
        "completed": statuses.get(IssueStatus.COMPLETED.value, 0),
        "verified": statuses.get(IssueStatus.VERIFIED.value, 0),
        "closed": statuses.get(IssueStatus.CLOSED.value, 0),
        "reopened": statuses.get(IssueStatus.REOPENED.value, 0),
        "escalated": qs.filter(is_escalated=True).count(),
        "high_priority": priorities.get("high", 0),
        "urgent": priorities.get("urgent", 0),
        "category_counts": categories,
    }


def job_list(user: User, spec: JobFilter) -> QuerySet[Job]:
    """Jobs in the user's scope with filters (one query)."""
    qs: QuerySet[Job] = Job.objects.select_related(
        "issue", "site", "assigned_to_user", "assigned_to_cleaner", "assigned_by", "verified_by"
    )
    if not user.is_system_admin:
        qs = qs.filter(_scoped(user))
    if spec.site_id:
        qs = qs.filter(site_id=spec.site_id)
    if spec.status:
        qs = qs.filter(status=spec.status)
    if spec.priority:
        qs = qs.filter(priority=spec.priority)
    if spec.issue_id:
        qs = qs.filter(issue_id=spec.issue_id)
    if spec.assigned_to_user_id:
        qs = qs.filter(assigned_to_user_id=spec.assigned_to_user_id)
    return qs


def get_job_or_none(job_id: int) -> Job | None:
    return (
        Job.objects.select_related(
            "issue", "site", "assigned_to_user", "assigned_to_cleaner", "assigned_by", "verified_by"
        )
        .filter(pk=job_id)
        .first()
    )


def overdue_jobs(user: User, site_id: int | None = None) -> QuerySet[Job]:
    """Jobs past due that are not done (single query)."""
    today = timezone.localdate()
    qs: QuerySet[Job] = Job.objects.select_related("issue", "site", "assigned_to_user", "assigned_to_cleaner").filter(
        due_date__lt=today,
        status__in=[JobStatus.OPEN, JobStatus.ASSIGNED, JobStatus.IN_PROGRESS, JobStatus.REOPENED],
    )
    if not user.is_system_admin:
        qs = qs.filter(_scoped(user))
    if site_id:
        qs = qs.filter(site_id=site_id)
    return qs


def job_summary(user: User, spec: JobFilter) -> dict[str, Any]:
    """Counts by status plus overdue total for the scope."""
    qs = job_list(user, spec)
    statuses = {row["status"]: row["n"] for row in qs.values("status").order_by().annotate(n=Count("pk"))}
    today = timezone.localdate()
    overdue = qs.filter(
        due_date__lt=today,
        status__in=[JobStatus.OPEN, JobStatus.ASSIGNED, JobStatus.IN_PROGRESS, JobStatus.REOPENED],
    ).count()
    return {
        "total_jobs": sum(statuses.values()),
        "open": statuses.get(JobStatus.OPEN.value, 0),
        "assigned": statuses.get(JobStatus.ASSIGNED.value, 0),
        "in_progress": statuses.get(JobStatus.IN_PROGRESS.value, 0),
        "completed": statuses.get(JobStatus.COMPLETED.value, 0),
        "verified": statuses.get(JobStatus.VERIFIED.value, 0),
        "closed": statuses.get(JobStatus.CLOSED.value, 0),
        "reopened": statuses.get(JobStatus.REOPENED.value, 0),
        "overdue": overdue,
    }
