"""API tests for authentication, tokens, and password flows."""

from typing import Any, cast

import pytest
from django.test import Client

from apps.accounts.factories import UserFactory
from apps.accounts.models import ApiToken, User
from apps.accounts.services import issue_api_token


def _login(client: Client, email: str, password: str) -> dict[str, Any]:
    response = client.post(
        "/api/site-management/v1/auth/login",
        data={"email": email, "password": password, "token_name": "test"},
        content_type="application/json",
    )
    assert response.status_code == 200
    return cast(dict[str, Any], response.json())


@pytest.mark.django_db
def test_login_returns_access_and_refresh_tokens() -> None:
    user = UserFactory(email="login@whitebird.test", password="correct-horse-1")
    body = _login(Client(), "login@whitebird.test", "correct-horse-1")
    assert body["access_token"]
    assert body["refresh_token"]
    assert body["expires_in"] > 0
    assert body["user"]["email"] == "login@whitebird.test"
    assert ApiToken.objects.filter(user=user, key=body["refresh_token"]).exists()


@pytest.mark.django_db
def test_login_is_case_insensitive_on_email() -> None:
    UserFactory(email="case@whitebird.test", password="correct-horse-1")
    body = _login(Client(), "CASE@whitebird.test", "correct-horse-1")
    assert body["user"]["email"] == "case@whitebird.test"


@pytest.mark.django_db
def test_login_rejects_bad_credentials() -> None:
    UserFactory(email="login@whitebird.test", password="correct-horse-1")
    response = Client().post(
        "/api/site-management/v1/auth/login",
        data={"email": "login@whitebird.test", "password": "wrong"},
        content_type="application/json",
    )
    assert response.status_code in (401, 403)


@pytest.mark.django_db
def test_login_rejects_inactive_account() -> None:
    UserFactory(email="off@whitebird.test", password="correct-horse-1", is_active=False)
    response = Client().post(
        "/api/site-management/v1/auth/login",
        data={"email": "off@whitebird.test", "password": "correct-horse-1"},
        content_type="application/json",
    )
    assert response.status_code in (401, 403)


@pytest.mark.django_db
def test_access_token_authenticates_me() -> None:
    UserFactory(email="me@whitebird.test", password="correct-horse-1")
    body = _login(Client(), "me@whitebird.test", "correct-horse-1")
    response = Client(HTTP_AUTHORIZATION=f"Bearer {body['access_token']}").get("/api/site-management/v1/auth/me")
    assert response.status_code == 200
    assert response.json()["email"] == "me@whitebird.test"


@pytest.mark.django_db
def test_refresh_exchanges_for_new_access_token() -> None:
    UserFactory(email="refresh@whitebird.test", password="correct-horse-1")
    body = _login(Client(), "refresh@whitebird.test", "correct-horse-1")
    response = Client().post(
        "/api/site-management/v1/auth/refresh",
        data={"refresh_token": body["refresh_token"]},
        content_type="application/json",
    )
    assert response.status_code == 200
    assert response.json()["access_token"]


@pytest.mark.django_db
def test_refresh_rejects_unknown_token() -> None:
    response = Client().post(
        "/api/site-management/v1/auth/refresh",
        data={"refresh_token": "nope"},
        content_type="application/json",
    )
    assert response.status_code in (401, 403)


@pytest.mark.django_db
def test_logout_revokes_refresh_token() -> None:
    user = UserFactory(email="out@whitebird.test", password="correct-horse-1")
    body = _login(Client(), "out@whitebird.test", "correct-horse-1")
    response = Client().post(
        "/api/site-management/v1/auth/logout",
        data={"refresh_token": body["refresh_token"]},
        content_type="application/json",
    )
    assert response.status_code == 200
    token = ApiToken.objects.get(user=user, key=body["refresh_token"])
    assert token.is_active is False


@pytest.mark.django_db
def test_password_change_flow(admin_client: Client, admin_user: User) -> None:
    response = admin_client.post(
        "/api/site-management/v1/auth/password-change",
        data={"current_password": "admin-password-1", "new_password": "new-password-123"},
        content_type="application/json",
    )
    assert response.status_code == 200
    admin_user.refresh_from_db()
    assert admin_user.check_password("new-password-123")


@pytest.mark.django_db
def test_password_change_rejects_wrong_current(admin_client: Client) -> None:
    response = admin_client.post(
        "/api/site-management/v1/auth/password-change",
        data={"current_password": "wrong", "new_password": "new-password-123"},
        content_type="application/json",
    )
    assert response.status_code == 403


@pytest.mark.django_db
def test_token_lifecycle(admin_client: Client, admin_user: User) -> None:
    created = admin_client.post(
        "/api/site-management/v1/auth/tokens", data={"name": "ci"}, content_type="application/json"
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
def test_token_cannot_be_revoked_by_another_user(viewer_client: Client, admin_user: User) -> None:
    token = issue_api_token(user=admin_user)
    response = viewer_client.post(f"/api/site-management/v1/auth/tokens/{token.pk}/revoke")
    assert response.status_code == 403


@pytest.mark.django_db
def test_staff_directory_requires_management_role(
    viewer_client: Client, zone_client: Client, admin_client: Client
) -> None:
    assert viewer_client.get("/api/site-management/v1/auth/staff").status_code == 403
    assert zone_client.get("/api/site-management/v1/auth/staff").status_code == 200
    assert admin_client.get("/api/site-management/v1/auth/staff").status_code == 200


@pytest.mark.django_db
def test_create_user_requires_system_admin(zone_client: Client, admin_client: Client) -> None:
    payload = {"email": "newbie@whitebird.test", "password": "newpass-123456"}
    denied = zone_client.post("/api/site-management/v1/auth/staff", data=payload, content_type="application/json")
    assert denied.status_code == 403
    response = admin_client.post("/api/site-management/v1/auth/staff", data=payload, content_type="application/json")
    assert response.status_code == 200
    assert response.json()["email"] == "newbie@whitebird.test"
