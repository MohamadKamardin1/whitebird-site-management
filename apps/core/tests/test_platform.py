"""Tests for the platform backbone: events, notifications, tasks, exports."""

import datetime
from decimal import Decimal
from typing import Any

import pytest
from django.core.cache import cache
from django.test import Client

from apps.accounts.factories import UserFactory
from apps.accounts.models import RoleCode
from apps.accounts.services import issue_api_token
from apps.core.models import DomainEvent
from apps.core.tasks import (
    check_low_stock,
    check_missing_site_reports,
    check_overdue_jobs,
    cleanup_old_notifications,
    publish_domain_events,
    warm_dashboard_cache,
)
from apps.site_management.factories import (
    CleanerFactory,
    SiteStoreFactory,
    SiteSupervisorAssignmentFactory,
)
from apps.site_management.models import (
    CleanerStatus,
    Job,
    Notification,
    StoreItem,
)
from apps.site_management.services import notify


@pytest.fixture(autouse=True)
def rbac_seeded(db: None) -> None:
    from django.core.management import call_command

    call_command("seed_rbac")


def _authed(user: Any) -> Client:
    return Client(HTTP_AUTHORIZATION=f"Bearer {issue_api_token(user=user, name='test').key}")


# --------------------------------------------------------------------------- #
# Domain events
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
def test_publish_domain_events_task(admin_user) -> None:
    DomainEvent.objects.create(
        event_type="CleanerRegistered", aggregate_type="site_management.cleaner", aggregate_id="1"
    )
    DomainEvent.objects.create(event_type="JobAssigned", aggregate_type="site_management.job", aggregate_id="2")
    published = publish_domain_events(batch_size=10)
    assert published == 2
    assert DomainEvent.objects.filter(status=DomainEvent.Status.PUBLISHED).count() == 2
    # Idempotent — nothing left to publish.
    assert publish_domain_events() == 0


# --------------------------------------------------------------------------- #
# Notifications
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
def test_notify_and_deduplication(admin_user) -> None:
    first = notify(
        recipient=admin_user,
        verb="job_overdue",
        title="Overdue job",
        object_type="site_management.job",
        object_id="5",
        dedup_key="job-overdue:5",
    )
    second = notify(
        recipient=admin_user,
        verb="job_overdue",
        title="Overdue job (again)",
        object_type="site_management.job",
        object_id="5",
        dedup_key="job-overdue:5",
    )
    assert second.pk == first.pk
    assert Notification.objects.count() == 1


@pytest.mark.django_db
def test_unread_count_and_read_all_endpoints(admin_user) -> None:
    notify(recipient=admin_user, verb="job_assigned", title="Job", object_id="1")
    notify(recipient=admin_user, verb="report_returned", title="Report", object_id="2")
    client = _authed(admin_user)
    count = client.get("/api/site-management/v1/notifications/unread-count").json()
    assert count["count"] == 2

    listed = client.get("/api/site-management/v1/notifications").json()
    assert len(listed) == 2

    read_one = client.post("/api/site-management/v1/notifications/{0}/read".format(listed[0]["id"]))
    assert read_one.status_code == 200

    read_all = client.post("/api/site-management/v1/notifications/read-all")
    assert read_all.status_code == 200
    assert client.get("/api/site-management/v1/notifications/unread-count").json()["count"] == 0


# --------------------------------------------------------------------------- #
# Scheduled checks
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
def test_check_missing_site_reports_notifies(site, admin_user) -> None:
    supervisor = UserFactory(role=RoleCode.SITE_SUPERVISOR)
    SiteSupervisorAssignmentFactory(site=site, user=supervisor)
    alerted = check_missing_site_reports()
    assert alerted == 1
    assert supervisor.notifications.filter(verb="missing_site_report").count() == 1
    # Dedup: a second run does not add another notification.
    check_missing_site_reports()
    assert supervisor.notifications.filter(verb="missing_site_report").count() == 1


@pytest.mark.django_db
def test_check_overdue_jobs_notifies(site, admin_user) -> None:
    assignee = UserFactory(role=RoleCode.SITE_SUPERVISOR)
    Job.objects.create(
        job_title="Overdue",
        site=site,
        assigned_by=admin_user,
        assigned_to_user=assignee,
        due_date=datetime.date.today() - datetime.timedelta(days=2),
        status="assigned",
    )
    alerted = check_overdue_jobs()
    assert alerted == 1
    assert assignee.notifications.filter(verb="job_overdue").count() == 1
    check_overdue_jobs()
    assert assignee.notifications.filter(verb="job_overdue").count() == 1


@pytest.mark.django_db
def test_check_low_stock_notifies(site, admin_user) -> None:
    manager = UserFactory(role=RoleCode.SITE_SUPERVISOR)
    store = SiteStoreFactory(site=site, managed_by=manager)
    StoreItem.objects.create(
        store=store, item_name="Soap", current_stock=Decimal("1"), minimum_stock_level=Decimal("5")
    )
    alerted = check_low_stock()
    assert alerted == 1
    assert manager.notifications.filter(verb="low_stock").count() == 1


@pytest.mark.django_db
def test_cleanup_old_notifications(admin_user) -> None:
    from django.utils import timezone

    n = notify(recipient=admin_user, verb="x", title="old")
    Notification.objects.filter(pk=n.pk).update(is_read=True, read_at=timezone.now() - datetime.timedelta(days=100))
    fresh = notify(recipient=admin_user, verb="y", title="new")
    Notification.objects.filter(pk=fresh.pk).update(is_read=True, read_at=timezone.now())
    deleted = cleanup_old_notifications(days=90)
    assert deleted == 1


@pytest.mark.django_db
def test_warm_dashboard_cache(site, admin_user) -> None:
    cache.clear()
    assert warm_dashboard_cache() >= 1
    cache.clear()


# --------------------------------------------------------------------------- #
# Exports
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
def test_export_csv_output_and_sanitization(site, admin_user) -> None:

    from apps.site_management.models import Issue, IssueSource

    CleanerFactory(first_name="=HYPERLINK(http://evil)", last_name="Normal", status=CleanerStatus.ACTIVE)
    Issue.objects.create(
        title="=1+1", site=site, source=IssueSource.MANUAL, issue_category="other", raised_by=admin_user
    )

    client = _authed(admin_user)
    response = client.get("/api/site-management/v1/exports/cleaners.csv")
    assert response.status_code == 200
    assert "text/csv" in response["Content-Type"]
    assert 'attachment; filename="cleaners-' in response["Content-Disposition"]
    body = b"".join(response.streaming_content).decode()
    assert '"first_name"' in body
    # Formula injection neutralised.
    assert "'=HYPERLINK" in body

    issues = client.get("/api/site-management/v1/exports/issues.csv")
    assert issues.status_code == 200
    assert "'=1+1" in b"".join(issues.streaming_content).decode()

    jobs = client.get("/api/site-management/v1/exports/jobs.csv")
    assert jobs.status_code == 200


@pytest.mark.django_db
def test_export_permissions(site, viewer_user, admin_user) -> None:
    client = _authed(admin_user)
    assert client.get("/api/site-management/v1/exports/attendance.csv").status_code == 200
    assert client.get("/api/site-management/v1/exports/reports.csv").status_code == 200

    # A viewer can export (read-only export permission) but stays scoped.
    v = _authed(viewer_user)
    assert v.get("/api/site-management/v1/exports/cleaners.csv").status_code == 200
    assert v.get("/api/site-management/v1/exports/jobs.csv").status_code == 200


@pytest.mark.django_db
def test_send_in_app_notifications_task(admin_user, site_supervisor_user) -> None:
    from apps.core.tasks import send_in_app_notifications

    created = send_in_app_notifications(
        [
            {"recipient_id": admin_user.pk, "verb": "job_assigned", "title": "Job A", "object_id": "1"},
            {"recipient_id": site_supervisor_user.pk, "verb": "job_assigned", "title": "Job B", "object_id": "2"},
        ]
    )
    assert created == 2
    assert admin_user.notifications.filter(verb="job_assigned").count() == 1
    assert site_supervisor_user.notifications.filter(verb="job_assigned").count() == 1
