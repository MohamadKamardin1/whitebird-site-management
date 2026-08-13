"""Tests for the Celery beat schedule bootstrap."""

import pytest
from django_celery_beat.models import IntervalSchedule, PeriodicTask


@pytest.mark.django_db
def test_periodic_stats_task_is_registered_on_migrate() -> None:
    task = PeriodicTask.objects.filter(name="Recompute site statistics").first()
    assert task is not None
    assert task.task == "apps.site_management.tasks.recompute_site_statistics"
    assert task.enabled is True
    assert isinstance(task.interval, IntervalSchedule)
    assert task.interval.period == IntervalSchedule.SECONDS
