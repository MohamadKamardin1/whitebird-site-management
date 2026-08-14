"""Platform-wide Celery tasks: event publishing, alerts, cache warming, cleanup.

All tasks are idempotent and safe to run on a schedule. Tests run in eager mode
so task bodies execute synchronously and can be asserted directly.
"""

from __future__ import annotations

import datetime
import logging
from typing import Any

from celery import shared_task
from constance import config
from django.utils import timezone

from apps.accounts.models import RoleCode, User
from apps.core.models import DomainEvent
from apps.site_management.models import DailySiteReport, Job, JobStatus, Notification, Site, StoreItem
from apps.site_management.services import notify

logger = logging.getLogger(__name__)


def _active_admins() -> list[User]:
    return list(User.objects.filter(is_active=True, role=RoleCode.SYSTEM_ADMIN))


@shared_task(bind=True, max_retries=3, default_retry_delay=30)  # type: ignore[untyped-decorator]
def publish_domain_events(self: Any, batch_size: int = 500) -> int:
    """Mark pending domain events as published (idempotent).

    With no external consumer wired up yet, this simply advances the outbox;
    a future Office Management subscriber will consume ``payload`` here.
    """
    from django.db.models import Q

    pending = DomainEvent.objects.filter(Q(status=DomainEvent.Status.PENDING))[:batch_size]
    ids = list(pending.values_list("pk", flat=True))
    if not ids:
        return 0
    DomainEvent.objects.filter(pk__in=ids).update(status=DomainEvent.Status.PUBLISHED, published_at=timezone.now())
    logger.info("Published %d domain events", len(ids))
    return len(ids)


@shared_task(bind=True, max_retries=3, default_retry_delay=30)  # type: ignore[untyped-decorator]
def send_in_app_notifications(self: Any, payloads: list[dict[str, Any]]) -> int:
    """Batch-create in-app notifications from payload dicts.

    Each payload mirrors :func:`apps.site_management.services.notify` kwargs.
    Used by the scheduled checks to keep delivery off the request path.
    """
    created = 0
    for payload in payloads:
        recipient_id = payload.pop("recipient_id", None)
        if recipient_id is None:
            continue
        try:
            recipient = User.objects.get(pk=recipient_id)
        except User.DoesNotExist:
            continue
        notify(recipient=recipient, **payload)
        created += 1
    return created


@shared_task(bind=True, max_retries=2, default_retry_delay=60)  # type: ignore[untyped-decorator]
def warm_dashboard_cache(self: Any) -> int:
    """Precompute dashboard KPI/chart caches for representative scopes."""
    from apps.site_management.dashboard_selectors import all_dashboard_charts, dashboard_kpis

    today = datetime.date.today()
    warmed = 0
    users = User.objects.filter(is_active=True)[:5]
    for user in users:
        dashboard_kpis(user, today)
        all_dashboard_charts(user, days=7)
        warmed += 1
    return warmed


@shared_task(bind=True, max_retries=3, default_retry_delay=30)  # type: ignore[untyped-decorator]
def check_missing_site_reports(self: Any, day: datetime.date | None = None) -> int:
    """Alert site supervisors about sites missing today's submitted report."""
    day = day or timezone.localdate()
    submitted_ids = set(DailySiteReport.objects.filter(report_date=day).values_list("site_id", flat=True))
    alerted = 0
    for site in Site.objects.filter(is_active=True):
        if site.pk in submitted_ids:
            continue
        supervisors = site.supervisor_assignments.filter(is_active=True).select_related("user")
        for assignment in supervisors:
            notify(
                recipient=assignment.user,
                verb="missing_site_report",
                title="Site report missing",
                body=f"{site.name} has no submitted report for {day}.",
                object_type="site_management.site",
                object_id=site.pk,
                link="/admin/site_management/dailysitereport/",
                dedup_key=f"missing-report:{site.pk}:{day.isoformat()}",
            )
            alerted += 1
    return alerted


@shared_task(bind=True, max_retries=3, default_retry_delay=30)  # type: ignore[untyped-decorator]
def check_overdue_jobs(self: Any) -> int:
    """Alert job assignees about overdue jobs (deduplicated per job)."""
    today = timezone.localdate()
    jobs = Job.objects.filter(
        due_date__lt=today,
        status__in=[JobStatus.OPEN, JobStatus.ASSIGNED, JobStatus.IN_PROGRESS, JobStatus.REOPENED],
    ).select_related("assigned_to_user", "site")[:200]
    alerted = 0
    for job in jobs:
        assignee = job.assigned_to_user
        if assignee is None:
            continue
        notify(
            recipient=assignee,
            verb="job_overdue",
            title=f"Overdue job: {job.job_title}",
            body=f"{job.site.name} — job was due {job.due_date}.",
            object_type="site_management.job",
            object_id=job.pk,
            link=f"/admin/site_management/job/{job.pk}/change/",
            dedup_key=f"job-overdue:{job.pk}",
        )
        alerted += 1
    return alerted


@shared_task(bind=True, max_retries=3, default_retry_delay=30)  # type: ignore[untyped-decorator]
def check_low_stock(self: Any) -> int:
    """Alert store managers about items at/below their reorder point."""
    from django.db.models import F

    items = StoreItem.objects.filter(current_stock__lte=F("minimum_stock_level")).select_related(
        "store", "store__managed_by"
    )[:200]
    alerted = 0
    for item in items:
        manager = item.store.managed_by
        if manager is None:
            continue
        notify(
            recipient=manager,
            verb="low_stock",
            title=f"Low stock: {item.item_name}",
            body=f"{item.item_name} is at {item.current_stock} {item.unit} (min {item.minimum_stock_level}).",
            object_type="site_management.storeitem",
            object_id=item.pk,
            link=f"/admin/site_management/storeitem/{item.pk}/change/",
            dedup_key=f"low-stock:{item.pk}",
        )
        alerted += 1
    return alerted


@shared_task(bind=True, max_retries=3, default_retry_delay=30)  # type: ignore[untyped-decorator]
def cleanup_old_notifications(self: Any, days: int | None = None) -> int:
    """Purge read notifications older than a retention window."""
    days = days or int(config.NOTIFICATION_RETENTION_DAYS)
    cutoff = timezone.now() - datetime.timedelta(days=days)
    deleted, _ = Notification.objects.filter(is_read=True, read_at__lt=cutoff).delete()
    return deleted
