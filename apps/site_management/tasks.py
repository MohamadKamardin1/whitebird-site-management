"""Celery tasks for the site management module.

Tasks are deliberately thin: they call service/selector functions and never
duplicate domain logic.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from celery import shared_task
from django.utils import timezone

from apps.accounts.models import RoleCode, User

from .models import Site, StaffAssignment
from .selectors import refresh_all_site_stats_cache
from .services import create_notification

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=30)  # type: ignore[untyped-decorator]
def notify_site_status_change(self: Any, site_id: int, status_slug: str) -> None:
    """Fan out a status-change notification to site staff and all admins."""
    try:
        site = Site.objects.get(pk=site_id)
    except Site.DoesNotExist:
        logger.warning("notify_site_status_change: site %s not found", site_id)
        return

    # Admins are always informed; staff only when assigned to the site.
    admin_ids = set(User.objects.filter(is_active=True, role=RoleCode.SYSTEM_ADMIN).values_list("pk", flat=True))
    staff_ids = set(site.staff_assignments.values_list("user_id", flat=True))
    for recipient in User.objects.filter(pk__in=admin_ids | staff_ids):
        create_notification(
            recipient=recipient,
            title=f"Site status changed: {site.name}",
            body=f"{site.name} moved to status '{status_slug}'.",
            entity_type="site_management.site",
            entity_id=str(site.pk),
        )


@shared_task(bind=True, max_retries=3, default_retry_delay=30)  # type: ignore[untyped-decorator]
def notify_staff_assigned(self: Any, assignment_id: int) -> None:
    """Notify a staff member that they have been assigned to a site."""
    try:
        assignment = StaffAssignment.objects.select_related("site", "user").get(pk=assignment_id)
    except StaffAssignment.DoesNotExist:
        logger.warning("notify_staff_assigned: assignment %s not found", assignment_id)
        return
    create_notification(
        recipient=assignment.user,
        title=f"You were assigned to {assignment.site.name}",
        body=f"You are now assigned to {assignment.site.name} as {assignment.get_role_display()}.",
        entity_type="sites.staffassignment",
        entity_id=str(assignment.pk),
    )


@shared_task  # type: ignore[untyped-decorator]
def recompute_site_statistics() -> None:
    """Periodic job: refresh cached per-site statistics."""
    refresh_all_site_stats_cache()
    logger.info("recompute_site_statistics: cache refreshed")


@shared_task(bind=True, max_retries=3, default_retry_delay=300)  # type: ignore[untyped-decorator]
def deliver_daily_report(self: Any) -> str:
    """Deliver the previous completed day to the administrator mailbox."""
    from .models import ReportDelivery
    from .report_delivery import deliver_scheduled_report

    try:
        return deliver_scheduled_report(
            ReportDelivery.ReportType.DAILY,
            as_of=timezone.localdate() - timedelta(days=1),
        )
    except Exception as exc:  # noqa: BLE001 - Celery retry boundary
        raise self.retry(exc=exc) from exc


@shared_task(bind=True, max_retries=3, default_retry_delay=600)  # type: ignore[untyped-decorator]
def deliver_weekly_report(self: Any) -> str:
    """Deliver the previous completed ISO week to the administrator mailbox."""
    from .models import ReportDelivery
    from .report_delivery import deliver_scheduled_report

    try:
        return deliver_scheduled_report(ReportDelivery.ReportType.WEEKLY)
    except Exception as exc:  # noqa: BLE001 - Celery retry boundary
        raise self.retry(exc=exc) from exc


@shared_task(bind=True, max_retries=3, default_retry_delay=900)  # type: ignore[untyped-decorator]
def deliver_monthly_report(self: Any) -> str:
    """Deliver the previous completed calendar month to the administrator mailbox."""
    from .models import ReportDelivery
    from .report_delivery import deliver_scheduled_report

    try:
        return deliver_scheduled_report(ReportDelivery.ReportType.MONTHLY)
    except Exception as exc:  # noqa: BLE001 - Celery retry boundary
        raise self.retry(exc=exc) from exc


@shared_task(bind=True, max_retries=3, default_retry_delay=600)  # type: ignore[untyped-decorator]
def generate_daily_ai_briefs(self: Any) -> str:
    """Generate one scoped daily AI brief per active leadership user."""
    from .ai_optimization import LEADERSHIP_ROLES, _scope_key, generate_optimization_brief
    from .models import AIOptimizationBrief

    day = timezone.localdate()
    created = 0
    try:
        for user in User.objects.filter(is_active=True, role__in=LEADERSHIP_ROLES).iterator():
            scope_key = _scope_key(user)
            if AIOptimizationBrief.objects.filter(
                brief_type=AIOptimizationBrief.BriefType.DAILY,
                report_date=day,
                scope_key=scope_key,
                role=user.role,
            ).exists():
                continue
            generate_optimization_brief(user=user, day=day, brief_type=AIOptimizationBrief.BriefType.DAILY)
            created += 1
        return f"Generated {created} daily AI brief(s) for {day.isoformat()}"
    except Exception as exc:  # noqa: BLE001 - Celery retry boundary
        raise self.retry(exc=exc) from exc


@shared_task(bind=True, max_retries=3, default_retry_delay=900)  # type: ignore[untyped-decorator]
def generate_friday_ai_briefs(self: Any) -> str:
    """Generate one complete Monday-Friday AI optimization brief per leader."""
    from .ai_optimization import LEADERSHIP_ROLES, _scope_key, generate_optimization_brief
    from .models import AIOptimizationBrief

    day = timezone.localdate()
    if day.weekday() != 4:
        return f"Skipped Friday AI brief generation on {day.isoformat()}"
    created = 0
    try:
        for user in User.objects.filter(is_active=True, role__in=LEADERSHIP_ROLES).iterator():
            scope_key = _scope_key(user)
            if AIOptimizationBrief.objects.filter(
                brief_type=AIOptimizationBrief.BriefType.WEEKLY,
                report_date=day,
                scope_key=scope_key,
                role=user.role,
            ).exists():
                continue
            generate_optimization_brief(user=user, day=day, brief_type=AIOptimizationBrief.BriefType.WEEKLY)
            created += 1
        return f"Generated {created} Friday AI brief(s) for {day.isoformat()}"
    except Exception as exc:  # noqa: BLE001 - Celery retry boundary
        raise self.retry(exc=exc) from exc
