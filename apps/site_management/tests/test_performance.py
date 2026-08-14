"""Performance regression tests: query counts, caching, pagination sanity."""

from datetime import date

import pytest
from django.core.cache import cache

from apps.site_management.factories import CleanerFactory, ZoneFactory
from apps.site_management.inspection_selectors import inspection_summary
from apps.site_management.issues_selectors import IssueFilter, issue_list
from apps.site_management.selectors import get_kpi_overview
from apps.site_management.store_selectors import StoreFilter, store_list


@pytest.mark.django_db
def test_cleaner_list_single_query(django_assert_num_queries, admin_user) -> None:
    from apps.site_management.cleaner_selectors import cleaner_list_queryset, cleaner_serialize
    from apps.site_management.factories import CleanerDocumentFactory
    from apps.site_management.models import Cleaner, CleanerDocumentStatus

    cleaner = CleanerFactory()
    CleanerDocumentFactory(cleaner=cleaner, status=CleanerDocumentStatus.VERIFIED)
    spec = type("S", (), {"search": None, "status": None, "id_type": None, "gender": None})()
    with django_assert_num_queries(2):
        rows = list(cleaner_list_queryset(admin_user, spec))
        assert len(rows) == Cleaner.objects.count()
        for c in rows:
            cleaner_serialize(c, admin_user)


@pytest.mark.django_db
def test_issue_list_single_query(django_assert_num_queries, site, admin_user) -> None:
    from apps.site_management.issues_services import create_job
    from apps.site_management.models import Issue, IssueSource

    issue = Issue.objects.create(
        title="X",
        site=site,
        source=IssueSource.MANUAL,
        issue_category="other",
        priority="high",
        raised_by=admin_user,
    )
    create_job(job_title="J", site=site, assigned_by=admin_user, actor=admin_user, issue=issue)
    with django_assert_num_queries(1):
        rows = list(issue_list(admin_user, IssueFilter()))
        assert len(rows) == 1
        assert rows[0].job_count == 1


@pytest.mark.django_db
def test_store_list_single_query(django_assert_num_queries, site, admin_user) -> None:
    from apps.site_management.factories import SiteStoreFactory

    SiteStoreFactory(site=site)
    with django_assert_num_queries(1):
        assert store_list(admin_user, StoreFilter()).count() == 1


@pytest.mark.django_db
def test_inspection_summary_single_grouped_query(django_assert_num_queries, site, admin_user) -> None:
    from apps.site_management.factories import SiteAreaFactory
    from apps.site_management.inspection_services import create_template, start_inspection

    template = create_template(
        template_name="A",
        actor=admin_user,
        site=site,
        items=[{"item_label": "C", "item_type": "pass_fail", "sequence": 1}],
    )
    area = SiteAreaFactory(site=site)
    start_inspection(site=site, area=area, template=template, inspected_by=admin_user, actor=admin_user)
    with django_assert_num_queries(3):
        summary = inspection_summary(admin_user)
        assert summary["total_inspections"] == 1


# --------------------------------------------------------------------------- #
# Caching
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
def test_kpi_overview_cached_and_invalidated(django_assert_num_queries, admin_user) -> None:
    from apps.site_management.selectors import KPI_PREFIX, invalidate

    cache.clear()
    with django_assert_num_queries(1):
        first = get_kpi_overview()
    assert first["site_count"] == 0
    # Second call is a cache hit — zero queries.
    with django_assert_num_queries(0):
        second = get_kpi_overview()
    assert second == first
    # Invalidation forces a recompute.
    invalidate(KPI_PREFIX, "overview")
    with django_assert_num_queries(1):
        get_kpi_overview()
    cache.clear()


@pytest.mark.django_db
def test_report_dashboard_cached(django_assert_num_queries, site, admin_user) -> None:
    from apps.site_management.reporting_selectors import reporting_status_dashboard
    from apps.site_management.reporting_services import generate_site_report

    cache.clear()
    generate_site_report(site_id=site.pk, day=date.today(), user=admin_user)
    reporting_status_dashboard(admin_user, date.today())  # populate cache
    with django_assert_num_queries(0):
        cached = reporting_status_dashboard(admin_user, date.today())
        assert cached["site_reports"][0]["status"] == "draft"
    cache.clear()


@pytest.mark.django_db
def test_theme_cached(django_assert_num_queries, admin_user) -> None:
    from django.test import Client

    from apps.accounts.services import issue_api_token

    cache.clear()
    client = Client(HTTP_AUTHORIZATION=f"Bearer {issue_api_token(user=admin_user, name='t').key}")
    assert client.get("/api/site-management/v1/theme").status_code == 200
    # The theme payload is cached under a namespaced key.
    assert cache.get("wbz_site:theme") is not None
    assert client.get("/api/site-management/v1/theme").status_code == 200
    cache.clear()


# --------------------------------------------------------------------------- #
# Pagination sanity
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
def test_pagination_never_unbounded(admin_user) -> None:
    from django.test import Client

    from apps.accounts.services import issue_api_token

    for _ in range(8):
        ZoneFactory()
    client = Client(HTTP_AUTHORIZATION=f"Bearer {issue_api_token(user=admin_user, name='t').key}")
    response = client.get("/api/site-management/v1/zones", {"page": 1, "page_size": 100})
    payload = response.json()
    assert len(payload["results"]) <= 100
    assert payload["count"] == 8


@pytest.mark.django_db
def test_issues_export_streams_csv(site, admin_user) -> None:
    from django.test import Client

    from apps.accounts.services import issue_api_token
    from apps.site_management.models import Issue, IssueSource

    Issue.objects.create(
        title="Export me",
        site=site,
        source=IssueSource.MANUAL,
        issue_category="other",
        priority="high",
        raised_by=admin_user,
    )
    client = Client(HTTP_AUTHORIZATION=f"Bearer {issue_api_token(user=admin_user, name='t').key}")
    response = client.get("/api/site-management/v1/issues/export")
    assert response.status_code == 200
    assert "text/csv" in response["Content-Type"]
    body = b"".join(response.streaming_content).decode()
    assert body.startswith('"id"')
    assert "Export me" in body


@pytest.mark.django_db
def test_seed_volume_command() -> None:
    from django.core.management import call_command

    from apps.site_management.models import AttendanceRecord, Issue, Site

    call_command(
        "seed_volume",
        zones=1,
        sites_per_zone=2,
        cleaners_per_site=2,
        days=3,
        items_per_store=2,
        run_tag="perftest",
    )
    assert Site.objects.filter(name__startswith="[perftest]").count() == 2
    assert AttendanceRecord.objects.count() >= 4
    assert Issue.objects.count() >= 1
    # Idempotent per run tag.
    call_command(
        "seed_volume",
        zones=1,
        sites_per_zone=2,
        cleaners_per_site=2,
        days=3,
        run_tag="perftest",
    )
    assert Site.objects.filter(name__startswith="[perftest]").count() == 2
