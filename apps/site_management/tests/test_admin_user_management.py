from __future__ import annotations

from datetime import timedelta

import pytest
from django.test import Client
from django.utils import timezone

from apps.accounts.factories import UserFactory
from apps.accounts.models import RoleCode
from apps.accounts.services import issue_api_token
from apps.site_management.factories import SiteFactory


def _client(user):
    return Client(HTTP_AUTHORIZATION=f"Bearer {issue_api_token(user=user, name='admin-management').key}")


@pytest.mark.django_db
def test_system_administrator_can_manage_user_lifecycle_and_site_supervisor_transfer() -> None:
    admin = UserFactory(role=RoleCode.SYSTEM_ADMIN)
    client = _client(admin)
    created = client.post(
        "/api/site-management/v1/auth/staff",
        data={
            "email": "new.supervisor@example.com",
            "password": "Safe-password-2026!",
            "first_name": "New",
            "last_name": "Supervisor",
            "phone": "0777000000",
            "role": RoleCode.MANAGEMENT_VIEWER,
        },
        content_type="application/json",
    )
    assert created.status_code == 200, created.content
    user_id = created.json()["id"]
    updated = client.patch(f"/api/site-management/v1/auth/users/{user_id}", data={"role": RoleCode.SITE_SUPERVISOR}, content_type="application/json")
    assert updated.status_code == 200, updated.content
    assert updated.json()["role"] == RoleCode.SITE_SUPERVISOR
    assert client.post(f"/api/site-management/v1/auth/users/{user_id}/password-reset", data={"new_password": "New-safe-password-2026!"}, content_type="application/json").status_code == 200
    assert client.post(f"/api/site-management/v1/auth/users/{user_id}/disable").status_code == 200
    assert client.post(f"/api/site-management/v1/auth/users/{user_id}/activate").status_code == 200

    first_site, second_site = SiteFactory(), SiteFactory()
    start = timezone.localdate()
    assignment = client.post(
        "/api/site-management/v1/admin/supervisor-assignments/site_supervisor",
        data={"user_id": user_id, "site_id": first_site.pk, "assigned_from": start.isoformat(), "is_primary": True},
        content_type="application/json",
    )
    assert assignment.status_code == 200, assignment.content
    transferred = client.post(
        f"/api/site-management/v1/admin/supervisor-assignments/site_supervisor/{assignment.json()['id']}/transfer",
        data={"site_id": second_site.pk, "assigned_from": (start + timedelta(days=1)).isoformat(), "is_primary": True},
        content_type="application/json",
    )
    assert transferred.status_code == 200, transferred.content
    assert transferred.json()["site_id"] == second_site.pk
    history = client.get(f"/api/site-management/v1/admin/supervisor-assignments?user_id={user_id}")
    assert history.status_code == 200, history.content
    assert len(history.json()) == 2
    assert any(not item["is_active"] and item["site_id"] == first_site.pk for item in history.json())
    assert client.get(f"/api/site-management/v1/auth/users/{user_id}/audit").status_code == 200


@pytest.mark.django_db
def test_non_administrator_cannot_read_administrator_user_or_assignment_management() -> None:
    supervisor = UserFactory(role=RoleCode.SITE_SUPERVISOR)
    client = _client(supervisor)
    assert client.get("/api/site-management/v1/auth/users/1/audit").status_code == 403
    assert client.get("/api/site-management/v1/admin/supervisor-assignments").status_code == 403
