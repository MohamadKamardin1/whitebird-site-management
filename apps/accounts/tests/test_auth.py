"""API tests for authentication and token management."""

import pytest
from django.test import Client

from apps.accounts.models import ApiToken
from apps.accounts.services import issue_api_token


@pytest.mark.django_db
def test_login_exchanges_credentials_for_token(admin_user):
    client = Client()
    response = client.post(
        "/api/site-management/v1/auth/login",
        data={"username": "admin", "password": "adminpass1", "token_name": "cli"},
        content_type="application/json",
    )
    assert response.status_code == 200
    body = response.json()
    assert body["token"]
    assert body["user"]["username"] == "admin"
    assert ApiToken.objects.filter(key=body["token"]).exists()


@pytest.mark.django_db
def test_login_rejects_bad_credentials(admin_user):
    response = Client().post(
        "/api/site-management/v1/auth/login",
        data={"username": "admin", "password": "wrong"},
        content_type="application/json",
    )
    assert response.status_code in (401, 403)


@pytest.mark.django_db
def test_me_requires_token(anon_client):
    assert anon_client.get("/api/site-management/v1/auth/me").status_code == 401


@pytest.mark.django_db
def test_me_returns_authenticated_user(admin_client, admin_user):
    response = admin_client.get("/api/site-management/v1/auth/me")
    assert response.status_code == 200
    assert response.json()["username"] == "admin"


@pytest.mark.django_db
def test_token_lifecycle(admin_client, admin_user):
    created = admin_client.post(
        "/api/site-management/v1/auth/tokens",
        data={"name": "ci"},
        content_type="application/json",
    )
    assert created.status_code == 200
    token_id = created.json()["id"]

    listed = admin_client.get("/api/site-management/v1/auth/tokens")
    assert any(t["id"] == token_id for t in listed.json())

    revoked = admin_client.post(f"/api/site-management/v1/auth/tokens/{token_id}/revoke")
    assert revoked.status_code == 200
    token = ApiToken.objects.get(pk=token_id)
    assert token.is_active is False


@pytest.mark.django_db
def test_token_cannot_be_revoked_by_another_user(staff_client, admin_user):
    token = issue_api_token(user=admin_user)
    response = staff_client.post(f"/api/site-management/v1/auth/tokens/{token.pk}/revoke")
    assert response.status_code == 403


@pytest.mark.django_db
def test_staff_directory_requires_privileged_role(staff_client, manager_client, admin_client):
    assert staff_client.get("/api/site-management/v1/auth/staff").status_code == 403
    assert manager_client.get("/api/site-management/v1/auth/staff").status_code == 200


@pytest.mark.django_db
def test_create_user_requires_admin(manager_client, admin_client):
    payload = {"username": "newbie", "password": "newpass123"}
    denied = manager_client.post("/api/site-management/v1/auth/staff", data=payload, content_type="application/json")
    assert denied.status_code == 403
    response = admin_client.post("/api/site-management/v1/auth/staff", data=payload, content_type="application/json")
    assert response.status_code == 200
    assert response.json()["username"] == "newbie"
