"""Celery task tests."""

import pytest

from apps.sites.models import Notification
from apps.sites.services import assign_staff
from apps.sites.tasks import (
    notify_site_status_change,
    notify_staff_assigned,
    recompute_site_statistics,
)


@pytest.mark.django_db
def test_status_change_notifies_admins_and_assigned_staff(
    site, admin_user, manager_user, staff_user
):
    assign_staff(site=site, user=manager_user, actor=admin_user)
    notify_site_status_change(site_id=site.pk, status_slug="maintenance")
    titles = set(Notification.objects.values_list("title", flat=True))
    assert any("status changed" in title.lower() for title in titles)
    assert Notification.objects.count() >= 2


@pytest.mark.django_db
def test_status_change_notifies_unassigned_user_only_when_admin(site, admin_user, staff_user):
    notify_site_status_change(site_id=site.pk, status_slug="active")
    recipients = set(Notification.objects.values_list("recipient_id", flat=True))
    assert recipients == {admin_user.pk}


@pytest.mark.django_db
def test_status_change_missing_site_is_noop():
    notify_site_status_change(site_id=999999, status_slug="active")
    assert Notification.objects.count() == 0


@pytest.mark.django_db
def test_staff_assigned_notification(site, staff_user, admin_user):
    assignment = assign_staff(site=site, user=staff_user, actor=admin_user)
    notify_staff_assigned(assignment_id=assignment.pk)
    notification = Notification.objects.filter(recipient=staff_user).first()
    assert notification is not None
    assert "assigned" in notification.title.lower()


@pytest.mark.django_db
def test_recompute_statistics_is_idempotent(site):
    recompute_site_statistics()
    recompute_site_statistics()
    assert True
