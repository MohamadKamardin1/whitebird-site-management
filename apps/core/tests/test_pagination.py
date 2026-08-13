"""Tests for the pagination and sorting helpers."""

import pytest
from django.test import RequestFactory

from apps.core.pagination import (
    apply_ordering,
    build_page_url,
    paginate,
    paginated_response,
    resolve_page_size,
)
from apps.site_management.factories import SiteFactory


@pytest.mark.django_db
def test_resolve_page_size_defaults_from_constance() -> None:
    from constance import config

    assert resolve_page_size(None) == int(config.DEFAULT_PAGE_SIZE)
    assert resolve_page_size(25) == 25
    assert resolve_page_size(99999) == int(config.MAX_PAGE_SIZE)
    assert resolve_page_size(0) == 1


@pytest.mark.django_db
def test_resolve_page_size_with_explicit_bounds() -> None:
    assert resolve_page_size(None, default=5, maximum=50) == 5
    assert resolve_page_size(100, default=5, maximum=50) == 50


@pytest.mark.django_db
def test_paginate_slices_queryset() -> None:
    for _ in range(5):
        SiteFactory()
    from apps.site_management.models import Site

    items, count, page, page_size = paginate(Site.objects.all(), page=2, page_size=2)
    assert count == 5
    assert page == 2
    assert page_size == 2
    assert len(items) == 2


@pytest.mark.django_db
def test_build_page_url_preserves_other_params() -> None:
    request = RequestFactory().get("/api/site-management/v1/sites?status=active")
    url = build_page_url(request, 3, 10)
    assert "page=3" in url
    assert "page_size=10" in url
    assert "status=active" in url


@pytest.mark.django_db
def test_paginated_response_builds_links() -> None:
    from apps.site_management.models import Site

    request = RequestFactory().get("/api/site-management/v1/sites")
    response = paginated_response(request, Site.objects.all(), page=2, page_size=2, items=[], count=10)
    assert response.count == 10
    assert response.next is not None
    assert response.previous is not None

    first = paginated_response(request, Site.objects.all(), page=1, page_size=5, items=[], count=10)
    assert first.previous is None


@pytest.mark.django_db
def test_apply_ordering_whitelist() -> None:
    from apps.site_management.models import Site

    qs = Site.objects.all()
    ordered = apply_ordering(qs, "-name", ["name"])
    assert ordered.query.order_by == ("-name",)
    unordered = apply_ordering(qs, "-injected", ["name"])
    assert unordered.query.order_by == ()
    assert apply_ordering(qs, None, ["name"]).query.order_by == ()
