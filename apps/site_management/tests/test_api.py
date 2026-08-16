"""End-to-end API tests for the site management module."""

from typing import Any

import pytest
from django.test import Client

from apps.accounts.models import User
from apps.accounts.services import issue_api_token
from apps.site_management.models import Asset
from apps.site_management.services import SiteDraft, assign_staff, create_site

JSON = "application/json"


def _post(client: Client, url: str, payload: Any = None, **kwargs: Any) -> Any:
    return client.post(url, data=payload or {}, content_type=JSON, **kwargs)


@pytest.mark.django_db
def test_health_endpoint_is_public(anon_client):
    response = anon_client.get("/api/site-management/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.django_db
def test_site_list_admin_sees_all(admin_client, site):
    create_site(draft=SiteDraft(name="Second"), actor=site.created_by)
    response = admin_client.get("/api/site-management/v1/sites")
    assert response.status_code == 200
    assert response.json()["count"] == 2
    assert len(response.json()["results"]) == 2


@pytest.mark.django_db
def test_site_list_site_supervisor_sees_only_assigned(admin_client, site_supervisor_client, site_supervisor_user, site):
    create_site(draft=SiteDraft(name="Hidden"), actor=site.created_by)
    from apps.site_management.factories import SiteSupervisorAssignmentFactory

    SiteSupervisorAssignmentFactory(site=site, user=site_supervisor_user)
    response = site_supervisor_client.get("/api/site-management/v1/sites")
    assert response.status_code == 200
    assert [s["name"] for s in response.json()["results"]] == [site.name]


@pytest.mark.django_db
def test_site_list_filters(admin_client, site, site_status, site_type):
    response = admin_client.get("/api/site-management/v1/sites", {"status": "active", "region": "Unguja North"})
    assert response.status_code == 200
    assert response.json()["count"] == 1


@pytest.mark.django_db
def test_site_create_requires_privileged_role(staff_client, manager_client, admin_client):
    payload = {"name": "New Site"}
    assert _post(staff_client, "/api/site-management/v1/sites", payload).status_code == 403
    assert _post(manager_client, "/api/site-management/v1/sites", payload).status_code == 403
    assert _post(admin_client, "/api/site-management/v1/sites", payload).status_code == 200


@pytest.mark.django_db
def test_site_detail_and_update(admin_client, site, site_status):
    detail = admin_client.get(f"/api/site-management/v1/sites/{site.pk}")
    assert detail.status_code == 200
    assert detail.json()["capacity"] == 100

    updated = admin_client.patch(
        f"/api/site-management/v1/sites/{site.pk}",
        data={"capacity": 150, "status_id": site_status.pk},
        content_type=JSON,
    )
    assert updated.status_code == 200
    assert updated.json()["capacity"] == 150


@pytest.mark.django_db
def test_site_detail_404_for_missing(admin_client):
    assert admin_client.get("/api/site-management/v1/sites/999999").status_code == 404


@pytest.mark.django_db
def test_site_archive_and_restore(admin_client, site):
    assert admin_client.delete(f"/api/site-management/v1/sites/{site.pk}").status_code == 200
    assert admin_client.get(f"/api/site-management/v1/sites/{site.pk}").status_code == 404
    restored = admin_client.post(f"/api/site-management/v1/sites/{site.pk}/restore")
    assert restored.status_code == 200


@pytest.mark.django_db
def test_staff_cannot_archive_site(staff_client, site):
    staff = User.objects.get(email="viewer@whitebird.test")
    assign_staff(site=site, user=staff, actor=site.created_by)
    assert staff_client.delete(f"/api/site-management/v1/sites/{site.pk}").status_code == 403


@pytest.mark.django_db
def test_department_crud(admin_client, site):
    created = _post(admin_client, f"/api/site-management/v1/sites/{site.pk}/departments", {"name": "Housekeeping"})
    assert created.status_code == 200
    dept_id = created.json()["id"]

    listed = admin_client.get(f"/api/site-management/v1/sites/{site.pk}/departments")
    assert [d["name"] for d in listed.json()] == ["Housekeeping"]

    updated = admin_client.patch(
        f"/api/site-management/v1/sites/{site.pk}/departments/{dept_id}",
        data={"description": "Rooms and public areas"},
        content_type=JSON,
    )
    assert updated.status_code == 200

    assert admin_client.delete(f"/api/site-management/v1/sites/{site.pk}/departments/{dept_id}").status_code == 200


@pytest.mark.django_db
def test_asset_crud(admin_client, site, asset_category):
    created = _post(
        admin_client,
        f"/api/site-management/v1/sites/{site.pk}/assets",
        {"name": "Land Cruiser", "category_id": asset_category.pk, "serial_number": "WB-9"},
    )
    assert created.status_code == 200
    asset_id = created.json()["id"]

    updated = admin_client.patch(
        f"/api/site-management/v1/sites/{site.pk}/assets/{asset_id}",
        data={"condition": "under_maintenance"},
        content_type=JSON,
    )
    assert updated.status_code == 200
    assert updated.json()["condition"] == "under_maintenance"

    assert admin_client.delete(f"/api/site-management/v1/sites/{site.pk}/assets/{asset_id}").status_code == 200
    assert Asset.objects.count() == 0


@pytest.mark.django_db
def test_assignment_flow(admin_client, staff_user, site):
    created = _post(
        admin_client,
        f"/api/site-management/v1/sites/{site.pk}/assignments",
        {"user_id": staff_user.pk, "role": "staff"},
    )
    assert created.status_code == 200
    assignment_id = created.json()["id"]

    assert admin_client.get(f"/api/site-management/v1/sites/{site.pk}/assignments").status_code == 200
    primary = admin_client.post(f"/api/site-management/v1/sites/{site.pk}/assignments/{assignment_id}/primary")
    assert primary.status_code == 200
    removed = admin_client.delete(f"/api/site-management/v1/sites/{site.pk}/assignments/{assignment_id}")
    assert removed.status_code == 200


@pytest.mark.django_db
def test_stats_endpoints(admin_client, site):
    stats = admin_client.get(f"/api/site-management/v1/sites/{site.pk}/stats")
    assert stats.status_code == 200
    assert stats.json()["site_id"] == site.pk

    overview = admin_client.get("/api/site-management/v1/stats/overview")
    assert overview.status_code == 200
    assert overview.json()["site_count"] == 1


@pytest.mark.django_db
def test_catalog_endpoints(admin_client, site_type, site_status, asset_category):
    assert admin_client.get("/api/site-management/v1/catalog/types").status_code == 200
    assert admin_client.get("/api/site-management/v1/catalog/statuses").status_code == 200
    assert admin_client.get("/api/site-management/v1/catalog/categories").status_code == 200


@pytest.mark.django_db
def test_staff_cannot_view_overview_stats(staff_client):
    assert staff_client.get("/api/site-management/v1/stats/overview").status_code == 403


@pytest.mark.django_db
def test_notifications_flow(admin_client, site, staff_user, admin_user):
    assign_staff(site=site, user=staff_user, actor=admin_user)
    count = admin_client.get("/api/site-management/v1/notifications/unread-count")
    assert count.status_code == 200

    listed = admin_client.get("/api/site-management/v1/notifications")
    assert listed.status_code == 200
    if listed.json():
        ids = [n["id"] for n in listed.json()]
        marked = _post(admin_client, "/api/site-management/v1/notifications/mark-read", ids)
        assert marked.status_code == 200


@pytest.mark.django_db
def test_audit_logs_require_privilege(staff_client, admin_client):
    assert staff_client.get("/api/site-management/v1/audit-logs").status_code == 403
    response = admin_client.get("/api/site-management/v1/audit-logs")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.django_db
def test_openapi_schema_available(anon_client):
    assert anon_client.get("/api/site-management/v1/openapi.json").status_code == 200


# --------------------------------------------------------------------------- #
# Branch coverage: denial and not-found paths
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
def test_site_supervisor_cannot_read_unassigned_site(site_supervisor_client, site):
    assert site_supervisor_client.get(f"/api/site-management/v1/sites/{site.pk}").status_code == 403


@pytest.mark.django_db
def test_assigned_staff_cannot_write_unless_manager(admin_client, staff_user, site):
    staff = User.objects.get(email="viewer@whitebird.test")
    assign_staff(site=site, user=staff, actor=site.created_by)
    denied = Client(HTTP_AUTHORIZATION=f"Bearer {issue_api_token(user=staff_user).key}")
    response = denied.patch(
        f"/api/site-management/v1/sites/{site.pk}",
        data={"capacity": 999},
        content_type=JSON,
    )
    assert response.status_code == 403


@pytest.mark.django_db
def test_department_update_and_delete_404_for_unknown(admin_client, site):
    url = f"/api/site-management/v1/sites/{site.pk}/departments/999999"
    assert admin_client.patch(url, data={"name": "X"}, content_type=JSON).status_code == 404
    assert admin_client.delete(url).status_code == 404


@pytest.mark.django_db
def test_asset_update_and_delete_404_for_unknown(admin_client, site):
    url = f"/api/site-management/v1/sites/{site.pk}/assets/999999"
    assert admin_client.patch(url, data={"name": "X"}, content_type=JSON).status_code == 404
    assert admin_client.delete(url).status_code == 404


@pytest.mark.django_db
def test_assignment_creation_404_for_missing_user(admin_client, site):
    response = _post(
        admin_client,
        f"/api/site-management/v1/sites/{site.pk}/assignments",
        {"user_id": 999999, "role": "staff"},
    )
    assert response.status_code == 404


@pytest.mark.django_db
def test_assignment_delete_and_primary_404_for_unknown(admin_client, site):
    url = f"/api/site-management/v1/sites/{site.pk}/assignments/999999"
    assert admin_client.delete(url).status_code == 404
    assert admin_client.post(f"{url}/primary").status_code == 404


@pytest.mark.django_db
def test_site_restore_404_for_unknown(admin_client):
    assert admin_client.post("/api/site-management/v1/sites/999999/restore").status_code == 404


@pytest.mark.django_db
def test_site_stats_404_for_unknown(admin_client):
    assert admin_client.get("/api/site-management/v1/sites/999999/stats").status_code == 404


@pytest.mark.django_db
def test_mark_read_with_no_matching_notifications(admin_client):
    response = _post(admin_client, "/api/site-management/v1/notifications/mark-read", [1, 2])
    assert response.status_code == 200
    assert response.json()["updated"] == 0


@pytest.mark.django_db
def test_department_unique_violation_returns_422(admin_client, site):
    _post(admin_client, f"/api/site-management/v1/sites/{site.pk}/departments", {"name": "Housekeeping"})
    duplicate = _post(admin_client, f"/api/site-management/v1/sites/{site.pk}/departments", {"name": "Housekeeping"})
    assert duplicate.status_code in (422, 409)
