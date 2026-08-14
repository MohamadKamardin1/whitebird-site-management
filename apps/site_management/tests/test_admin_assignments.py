"""Tests for the assignment admin screens."""

import pytest
from django.test import Client

from apps.accounts.factories import UserFactory
from apps.accounts.models import RoleCode
from apps.site_management.assignment_services import assign_cleaner_to_site
from apps.site_management.factories import (
    CleanerAreaScheduleFactory,
    CleanerFactory,
    CleanerSiteAssignmentFactory,
    SiteAreaFactory,
    SiteFactory,
)
from apps.site_management.models import (
    CleanerAssignmentStatus,
    CleanerAssignmentType,
    CleanerSiteAssignment,
    CleanerStatus,
)


@pytest.fixture
def admin_client(db: None) -> Client:
    admin = UserFactory(role=RoleCode.SYSTEM_ADMIN, is_staff=True, is_superuser=True)
    client = Client()
    client.force_login(admin)
    return client


@pytest.mark.django_db
def test_assignment_changelist_renders(admin_client: Client) -> None:
    cleaner = CleanerFactory(status=CleanerStatus.ACTIVE)
    site = SiteFactory()
    CleanerSiteAssignmentFactory(cleaner=cleaner, site=site, status=CleanerAssignmentStatus.ACTIVE)
    response = admin_client.get("/admin/site_management/cleanersiteassignment/")
    assert response.status_code == 200


@pytest.mark.django_db
def test_assignment_admin_actions(admin_client: Client, admin_user) -> None:
    cleaner = CleanerFactory(status=CleanerStatus.ACTIVE)
    site = SiteFactory()
    assignment = assign_cleaner_to_site(
        cleaner=cleaner,
        site=site,
        assignment_type=CleanerAssignmentType.FULL_TIME,
        start_date="2026-01-01",
        actor=admin_user,
    )

    response = admin_client.post(
        "/admin/site_management/cleanersiteassignment/",
        data={"action": "suspend_assignments", "_selected_action": [assignment.pk]},
    )
    assert response.status_code == 302
    assignment.refresh_from_db()
    assert assignment.status == CleanerAssignmentStatus.SUSPENDED

    response = admin_client.post(
        "/admin/site_management/cleanersiteassignment/",
        data={"action": "activate_assignments", "_selected_action": [assignment.pk]},
    )
    assert response.status_code == 302
    assignment.refresh_from_db()
    assert assignment.status == CleanerAssignmentStatus.ACTIVE

    response = admin_client.post(
        "/admin/site_management/cleanersiteassignment/",
        data={"action": "end_assignments", "_selected_action": [assignment.pk]},
    )
    assert response.status_code == 302
    assignment.refresh_from_db()
    assert assignment.status == CleanerAssignmentStatus.ENDED


@pytest.mark.django_db
def test_assignment_delete_guard(admin_user) -> None:
    from apps.site_management.admin import CleanerSiteAssignmentAdmin

    cleaner = CleanerFactory(status=CleanerStatus.ACTIVE)
    site = SiteFactory()
    assignment = assign_cleaner_to_site(
        cleaner=cleaner,
        site=site,
        assignment_type=CleanerAssignmentType.FULL_TIME,
        start_date="2026-01-01",
        actor=admin_user,
    )
    admin = CleanerSiteAssignmentAdmin(model=CleanerSiteAssignment, admin_site=None)
    assert admin.has_delete_permission(request=None, obj=assignment) is True  # no history

    area = SiteAreaFactory(site=site)
    from apps.site_management.factories import OperationalRoleFactory

    CleanerAreaScheduleFactory(
        assignment=assignment,
        site_area=area,
        operational_role=OperationalRoleFactory(),
    )
    assert admin.has_delete_permission(request=None, obj=assignment) is False


@pytest.mark.django_db
def test_shift_and_schedule_admin_changelists_render(admin_client: Client, admin_user) -> None:
    cleaner = CleanerFactory(status=CleanerStatus.ACTIVE)
    site = SiteFactory()
    assignment = assign_cleaner_to_site(
        cleaner=cleaner,
        site=site,
        assignment_type=CleanerAssignmentType.FULL_TIME,
        start_date="2026-01-01",
        actor=admin_user,
    )
    area = SiteAreaFactory(site=site)
    CleanerAreaScheduleFactory(
        assignment=assignment,
        site_area=area,
        operational_role=__import__(
            "apps.site_management.factories", fromlist=["OperationalRoleFactory"]
        ).OperationalRoleFactory(),
    )

    assert admin_client.get("/admin/site_management/cleanershiftassignment/").status_code == 200
    assert admin_client.get("/admin/site_management/cleanerareaschedule/").status_code == 200


@pytest.mark.django_db
def test_zone_and_site_admin_actions(admin_client: Client) -> None:
    from apps.site_management.factories import SiteFactory, ZoneFactory

    zone = ZoneFactory()
    response = admin_client.post(
        "/admin/site_management/zone/",
        data={"action": "deactivate_zones", "_selected_action": [zone.pk]},
    )
    assert response.status_code == 302
    zone.refresh_from_db()
    assert zone.is_active is False
    response = admin_client.post(
        "/admin/site_management/zone/",
        data={"action": "activate_zones", "_selected_action": [zone.pk]},
    )
    assert response.status_code == 302

    site = SiteFactory()
    response = admin_client.post(
        "/admin/site_management/site/",
        data={"action": "archive", "_selected_action": [site.pk]},
    )
    assert response.status_code == 302
    site.refresh_from_db()
    assert site.is_active is False
    response = admin_client.post(
        "/admin/site_management/site/",
        data={"action": "restore", "_selected_action": [site.pk]},
    )
    assert response.status_code == 302
