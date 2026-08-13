"""Selector and caching tests."""

import pytest

from apps.common.cache import cache_key
from apps.sites.selectors import (
    SiteFilter,
    get_all_site_stats,
    get_site_detail,
    get_site_stats,
    list_departments,
    list_sites,
)
from apps.sites.services import (
    SiteDraft,
    assign_staff,
    create_department,
    create_site,
)


@pytest.mark.django_db
def test_list_sites_applies_search_filter(admin_user, site):
    create_site(draft=SiteDraft(name="Jambiani Villa"), actor=admin_user)
    results = list_sites(SiteFilter(search="jambiani"))
    assert len(results) == 1
    assert results[0].name == "Jambiani Villa"


@pytest.mark.django_db
def test_list_sites_filters_by_capacity_min(admin_user, site):
    create_site(draft=SiteDraft(name="Large Site", capacity=300), actor=admin_user)
    results = list_sites(SiteFilter(capacity_min=200))
    assert [s.name for s in results] == ["Large Site"]


@pytest.mark.django_db
def test_site_detail_is_cached(site):
    first = get_site_detail(site.pk)
    assert first is not None
    assert first["name"] == site.name
    assert get_site_detail(site.pk) == first


@pytest.mark.django_db
def test_site_detail_returns_none_for_missing():
    assert get_site_detail(999999) is None


@pytest.mark.django_db
def test_site_stats_aggregate_counts(site, staff_user, admin_user):
    create_department(site=site, name="Front Office", actor=admin_user)
    assign_staff(site=site, user=staff_user, actor=admin_user)
    stats = get_site_stats(site.pk)
    assert stats["departments"] == 1
    assert stats["staff"] == 1


@pytest.mark.django_db
def test_all_site_stats_covers_every_site(site, admin_user):
    create_site(draft=SiteDraft(name="Second"), actor=admin_user)
    stats = get_all_site_stats()
    assert len(stats) == 2


@pytest.mark.django_db
def test_cache_key_is_stable_and_unique():
    assert cache_key("site:detail", 1) == cache_key("site:detail", 1)
    assert cache_key("site:detail", 1) != cache_key("site:detail", 2)


@pytest.mark.django_db
def test_list_departments_only_active(site, admin_user):
    create_department(site=site, name="Kitchen", actor=admin_user)
    assert [d.name for d in list_departments(site.pk)] == ["Kitchen"]
