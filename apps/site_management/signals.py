"""Django signals for the site management app.

Registers the default periodic task in the Celery Beat database scheduler so
the platform works out of the box while remaining editable from the admin.
"""

from __future__ import annotations

from typing import Any

from django.conf import settings
from django.db.models.signals import post_migrate
from django.dispatch import receiver

from apps.site_management.tasks import recompute_site_statistics

TASK_NAME = "Recompute site statistics"


@receiver(post_migrate)
def register_default_beat_schedule(sender: Any, **kwargs: Any) -> None:
    """Idempotently seed the periodic stats refresh after migrations."""
    if sender.name != "django_celery_beat":
        return

    from django_celery_beat.models import IntervalSchedule, PeriodicTask  # noqa: PLC0415

    schedule, _ = IntervalSchedule.objects.get_or_create(
        every=int(getattr(settings, "SITE_STATS_SCHEDULE_SECONDS", 900)),
        period=IntervalSchedule.SECONDS,
    )
    PeriodicTask.objects.get_or_create(
        name=TASK_NAME,
        defaults={
            "task": f"{recompute_site_statistics.name}",
            "interval": schedule,
            "enabled": True,
        },
    )
