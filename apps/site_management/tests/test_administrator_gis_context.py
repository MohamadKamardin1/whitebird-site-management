"""Authorization and current-supervisor coverage for the administrator GIS map."""

from __future__ import annotations

from datetime import date

import pytest
from django.test import Client

from apps.accounts.factories import UserFactory
from apps.accounts.models import RoleCode
from apps.accounts.services import issue_api_token
from apps.site_management.factories import SiteFactory, SiteSupervisorAssignmentFactory, ZoneFactory


def _client_for(user: object) -> Client:
    return Client(HTTP_AUTHORIZATION=f"Bearer {issue_api_token(user=user, name='administrator-gis-test').key}")


@pytest.mark.django_db
def test_administrator_gis_context_returns_current_supervisor_contacts_only_to_admin() -> None:
    from django.core.management import call_command

    call_command("seed_rbac")
    admin = UserFactory(role=RoleCode.SYSTEM_ADMIN)
    non_admin = UserFactory(role=RoleCode.HR)
    supervisor = UserFactory(role=RoleCode.SITE_SUPERVISOR, first_name="Asha", last_name="Juma", phone="+255777123456")
    zone = ZoneFactory(name="Unguja North", code="UN-N")
    site = SiteFactory(zone=zone, latitude=-6.164817, longitude=39.201233)
    SiteSupervisorAssignmentFactory(site=site, user=supervisor, assigned_from=date.today(), is_active=True, is_primary=True)

    forbidden = _client_for(non_admin).get("/api/site-management/v1/admin/gis/sites")
    assert forbidden.status_code == 403

    response = _client_for(admin).get("/api/site-management/v1/admin/gis/sites")
    assert response.status_code == 200
    row = next(item for item in response.json() if item["id"] == site.pk)
    assert row["zone_name"] == "Unguja North"
    assert row["latitude"] == pytest.approx(-6.164817)
    assert row["longitude"] == pytest.approx(39.201233)
    assert row["supervisors"] == [{"id": supervisor.pk, "full_name": "Asha Juma", "phone": "+255777123456"}]
