"""Regression coverage for persisted administrator site coordinates."""

from __future__ import annotations

import json

import pytest
from django.test import Client

from apps.accounts.factories import UserFactory
from apps.accounts.models import RoleCode
from apps.accounts.services import issue_api_token
from apps.site_management.factories import SiteFactory


def _client_for(user: object) -> Client:
    return Client(HTTP_AUTHORIZATION=f"Bearer {issue_api_token(user=user, name='site-coordinate-test').key}")


@pytest.mark.django_db
def test_persisted_site_coordinates_are_returned_by_the_authorised_site_list() -> None:
    from django.core.management import call_command

    call_command("seed_rbac")
    admin = UserFactory(role=RoleCode.SYSTEM_ADMIN)
    site = SiteFactory(latitude=None, longitude=None)
    client = _client_for(admin)

    update = client.patch(
        f"/api/site-management/v1/sites/{site.pk}",
        data=json.dumps({"latitude": -6.164817, "longitude": 39.201233}),
        content_type="application/json",
    )
    assert update.status_code == 200
    assert update.json()["latitude"] == pytest.approx(-6.164817)
    assert update.json()["longitude"] == pytest.approx(39.201233)

    listing = client.get("/api/site-management/v1/sites?page_size=100")
    assert listing.status_code == 200
    payload = listing.json()
    rows = payload["results"] if isinstance(payload, dict) and "results" in payload else payload
    persisted = next(row for row in rows if row["id"] == site.pk)
    assert persisted["latitude"] == pytest.approx(-6.164817)
    assert persisted["longitude"] == pytest.approx(39.201233)
