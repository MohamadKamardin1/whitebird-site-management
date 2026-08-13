"""Celery tasks for the site management module.

Tasks are deliberately thin: they call service/selector functions and never
duplicate domain logic.
"""

from __future__ import annotations

import logging
from typing import Any

from celery import shared_task

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
