"""Celery tasks for external provider integrations.

All tasks are idempotent and degrade gracefully when a provider is disabled —
they return ``None`` instead of failing the queue.
"""

from __future__ import annotations

import logging
from typing import Any

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=2, default_retry_delay=30)  # type: ignore[untyped-decorator]
def summarize_site_report(self: Any, report_id: int, instruction: str = "") -> str | None:
    """Asynchronously summarise a daily site report with DeepSeek."""
    from apps.site_management.models import DailySiteReport

    report = DailySiteReport.objects.select_related("site").filter(pk=report_id).first()
    if report is None:
        logger.warning("summarize_site_report: report %s not found", report_id)
        return None
    from .services import summarize_site_report as run_summary

    try:
        summary = run_summary(report, instruction=instruction)
    except Exception as exc:
        logger.warning("summarize_site_report: report %s failed: %s", report_id, exc)
        raise self.retry(exc=exc)
    logger.info("summarize_site_report: report %s -> %s chars", report_id, len(summary) if summary else 0)
    return summary


@shared_task(bind=True, max_retries=2, default_retry_delay=30)  # type: ignore[untyped-decorator]
def geocode_site(self: Any, site_id: int) -> dict[str, Any] | None:
    """Asynchronously geocode a site and persist its coordinates."""
    from apps.site_management.models import Site

    site = Site._base_manager.filter(pk=site_id).first()
    if site is None:
        logger.warning("geocode_site: site %s not found", site_id)
        return None
    from .services import geocode_site as run_geocode

    try:
        feature = run_geocode(site)
    except Exception as exc:
        logger.warning("geocode_site: site %s failed: %s", site_id, exc)
        raise self.retry(exc=exc)
    logger.info("geocode_site: site %s -> %s", site_id, feature)
    return feature
