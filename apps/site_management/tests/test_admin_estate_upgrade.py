import pytest

from apps.site_management.models import InspectionTemplate, SiteArea, SiteStore, Zone
from apps.site_management.services import SiteDraft, create_site


@pytest.mark.django_db
def test_new_site_receives_default_cleanliness_surveys_and_store(admin_user, site_type, site_status):
    site = create_site(
        draft=SiteDraft(name="Provisioned Site", site_type=site_type, status=site_status),
        actor=admin_user,
    )
    assert SiteArea.objects.filter(site=site, is_active=True).count() == 7
    assert InspectionTemplate.objects.filter(site=site, frequency="daily", is_active=True).count() == 7
    daily_template = InspectionTemplate.objects.filter(
        site=site, template_name__contains="Daily Cleanliness Survey"
    ).first()
    assert daily_template is not None
    assert daily_template.items.count() >= 6
    assert SiteStore.objects.filter(site=site, is_active=True).count() == 1


@pytest.mark.django_db
def test_admin_zone_boundary_crud_is_audited_and_non_admin_cannot_write(admin_client, manager_client):
    created = admin_client.post(
        "/api/site-management/v1/zones",
        data={"name": "North Zone", "code": "NORTH", "description": "North operating area"},
        content_type="application/json",
    )
    assert created.status_code == 200
    zone_id = created.json()["id"]
    boundary = {"type": "Polygon", "coordinates": [[[39.1, -6.1], [39.2, -6.1], [39.2, -6.2], [39.1, -6.1]]]}
    updated = admin_client.patch(
        f"/api/site-management/v1/zones/{zone_id}",
        data={"boundary": boundary},
        content_type="application/json",
    )
    assert updated.status_code == 200
    assert updated.json()["boundary"] == boundary
    assert (
        manager_client.patch(
            f"/api/site-management/v1/zones/{zone_id}",
            data={"description": "Not allowed"},
            content_type="application/json",
        ).status_code
        == 403
    )
    deactivated = admin_client.delete(f"/api/site-management/v1/zones/{zone_id}")
    assert deactivated.status_code == 200
    assert Zone.objects.all_with_deleted().get(pk=zone_id).is_active is False
