"""Tests for the role-aware dashboards, KPI/chart APIs and caching."""

import datetime
from decimal import Decimal
from typing import Any

import pytest
from django.core.cache import cache
from django.test import Client

from apps.accounts.factories import UserFactory
from apps.accounts.models import RoleCode
from apps.accounts.services import issue_api_token
from apps.site_management.factories import (
    CleanerFactory,
    SiteFactory,
    SiteStoreFactory,
    SiteSupervisorAssignmentFactory,
    ZoneSupervisorAssignmentFactory,
)
from apps.site_management.models import (
    AttendanceRecord,
    AttendanceStatus,
    CleanerAssignmentStatus,
    CleanerSiteAssignment,
    CleanerStatus,
    Issue,
    IssueSource,
    StoreItem,
)


@pytest.fixture(autouse=True)
def rbac_seeded(db: None) -> None:
    from django.core.management import call_command

    call_command("seed_rbac")


def _authed(user: Any) -> Client:
    return Client(HTTP_AUTHORIZATION=f"Bearer {issue_api_token(user=user, name='test').key}")


@pytest.fixture
def site_a(db: Any) -> Any:
    return SiteFactory(name="Site A")


@pytest.fixture
def site_b(db: Any) -> Any:
    return SiteFactory(name="Site B")


def _seed_domain(site: Any, admin: Any, day: datetime.date) -> None:
    for _ in range(2):
        cleaner = CleanerFactory(status=CleanerStatus.ACTIVE)
        CleanerSiteAssignment.objects.create(
            cleaner=cleaner,
            site=site,
            assignment_type="full_time",
            start_date=day - datetime.timedelta(days=10),
            status=CleanerAssignmentStatus.ACTIVE,
            assigned_by=admin,
        )
    cleaners = list(CleanerSiteAssignment.objects.filter(site=site).values_list("cleaner_id", flat=True))
    AttendanceRecord.objects.create(
        cleaner_id=cleaners[0], site=site, attendance_date=day, status=AttendanceStatus.PRESENT
    )
    AttendanceRecord.objects.create(
        cleaner_id=cleaners[1], site=site, attendance_date=day, status=AttendanceStatus.ABSENT
    )
    Issue.objects.create(
        title="Open",
        site=site,
        source=IssueSource.MANUAL,
        issue_category="maintenance",
        priority="high",
        raised_by=admin,
    )
    store = SiteStoreFactory(site=site)
    item = StoreItem.objects.create(
        store=store, item_name="Soap", current_stock=Decimal("1"), minimum_stock_level=Decimal("5")
    )


# --------------------------------------------------------------------------- #
# Page access
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
def test_dashboard_requires_login() -> None:
    response = Client().get("/dashboard/")
    assert response.status_code == 302
    assert "/login" in response["Location"]


@pytest.mark.django_db
def test_dashboard_requires_staff_or_role(site_a, admin_user) -> None:
    client = Client()
    client.force_login(admin_user)
    assert client.get("/dashboard/").status_code == 200


@pytest.mark.django_db
def test_role_specific_templates(site_a, admin_user) -> None:
    from apps.accounts.models import RoleCode as RC

    cases = [
        (RC.SITE_SUPERVISOR, "Site Supervisor Dashboard"),
        (RC.ZONE_SUPERVISOR, "Zone Supervisor Dashboard"),
        (RC.ASSISTANT_GENERAL_SUPERVISOR, "Assistant General Dashboard"),
        (RC.GENERAL_SUPERVISOR, "General Supervisor Dashboard"),
        (RC.MANAGEMENT_VIEWER, "Management Dashboard"),
        (RC.SYSTEM_ADMIN, "General Supervisor Dashboard"),
    ]
    for role, label in cases:
        user = UserFactory(role=role)
        if role == RC.SITE_SUPERVISOR:
            SiteSupervisorAssignmentFactory(site=site_a, user=user)
        client = Client()
        client.force_login(user)
        response = client.get("/dashboard/")
        assert response.status_code == 200
        assert label.encode() in response.content


@pytest.mark.django_db
def test_management_viewer_read_only_banner(site_a, viewer_user) -> None:
    client = Client()
    client.force_login(viewer_user)
    html = client.get("/dashboard/").content.decode()
    assert "Read-only view" in html


@pytest.mark.django_db
def test_landing_redirects_authenticated_to_dashboard(admin_user) -> None:
    client = Client()
    client.force_login(admin_user)
    response = client.get("/")
    assert response.status_code == 302
    assert response["Location"].endswith("/dashboard/")


# --------------------------------------------------------------------------- #
# KPI API + scoping
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
def test_kpis_endpoint_shape(site_a, admin_user) -> None:
    _seed_domain(site_a, admin_user, datetime.date.today())
    response = _authed(admin_user).get("/api/site-management/v1/dashboards/kpis")
    assert response.status_code == 200
    body = response.json()
    expected = {
        "active_sites",
        "active_cleaners",
        "trainees_in_training",
        "attendance_rate",
        "absences_today",
        "late_today",
        "open_issues",
        "overdue_jobs",
        "low_stock_items",
        "inspections_pass_rate",
        "missing_site_reports",
        "pending_reports",
        "escalated_issues",
    }
    assert set(body) == expected
    assert body["active_sites"] == 1
    assert body["active_cleaners"] == 2
    assert body["open_issues"] == 1
    assert body["low_stock_items"] == 1
    assert body["attendance_rate"] == 50.0
    assert body["absences_today"] == 1


@pytest.mark.django_db
def test_kpis_scoped_by_zone(site_a, site_b, admin_user) -> None:
    _seed_domain(site_a, admin_user, datetime.date.today())
    _seed_domain(site_b, admin_user, datetime.date.today())
    zone_user = UserFactory(role=RoleCode.ZONE_SUPERVISOR)
    ZoneSupervisorAssignmentFactory(zone=site_a.zone, user=zone_user)
    body = _authed(zone_user).get("/api/site-management/v1/dashboards/kpis").json()
    assert body["active_sites"] == 1  # only zone A
    admin_body = _authed(admin_user).get("/api/site-management/v1/dashboards/kpis").json()
    assert admin_body["active_sites"] == 2


# --------------------------------------------------------------------------- #
# Chart endpoints
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
def test_chart_endpoints_shape(site_a, admin_user) -> None:
    _seed_domain(site_a, admin_user, datetime.date.today())
    client = _authed(admin_user)
    trend = client.get("/api/site-management/v1/dashboards/charts/attendance-trend", {"days": 7}).json()
    assert "labels" in trend and "present" in trend and "absent" in trend
    assert len(trend["labels"]) == 7

    by_cat = client.get("/api/site-management/v1/dashboards/charts/issues-by-category").json()
    assert by_cat["labels"] == ["maintenance"] and by_cat["values"] == [1]

    jobs = client.get("/api/site-management/v1/dashboards/charts/jobs-open-vs-closed").json()
    assert jobs["labels"] == ["Open", "Closed"]

    report = client.get("/api/site-management/v1/dashboards/charts/report-status-by-site").json()
    assert "labels" in report and "values" in report


# --------------------------------------------------------------------------- #
# Caching
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
def test_kpis_cached(site_a, admin_user) -> None:
    from apps.site_management.dashboard_selectors import dashboard_kpis

    cache.clear()
    dashboard_kpis(admin_user)  # populate
    assert (
        cache.get("wbz_site:dash:v1:kpis:" + datetime.date.today().isoformat() + ":" + str(admin_user.pk)) is not None
    )
    cache.clear()


@pytest.mark.django_db
def test_chart_cached(django_assert_num_queries, site_a, admin_user) -> None:
    from apps.site_management.dashboard_selectors import issues_by_category

    cache.clear()
    issues_by_category(admin_user)  # populate
    with django_assert_num_queries(0):
        second = issues_by_category(admin_user)
        assert second == {"labels": [], "values": []}
    cache.clear()
