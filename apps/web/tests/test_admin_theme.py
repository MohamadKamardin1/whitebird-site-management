"""Tests for the premium Jazzmin admin theme, login page and theme API."""

import pytest
from django.test import Client

from apps.accounts.factories import UserFactory
from apps.accounts.services import issue_api_token


@pytest.mark.django_db
def test_admin_login_renders_branded(admin_user) -> None:
    response = Client().get("/admin/login/")
    assert response.status_code == 200
    html = response.content.decode()
    assert "White Bird Zanzibar" in html
    assert "material_soft_gold.css" in html
    assert "images/logo.svg" in html
    # Material soft-gold palette variable present.
    assert "--wb-primary" in html


@pytest.mark.django_db
def test_admin_base_loads_stylesheet(admin_user) -> None:
    client = Client()
    client.force_login(admin_user)
    response = client.get("/admin/")
    assert response.status_code == 200
    html = response.content.decode()
    assert "material_soft_gold.css" in html or "whitebird_admin.css" in html
    assert "images/favicon.svg" in html


@pytest.mark.django_db
def test_admin_index_shows_essential_links(admin_user) -> None:
    client = Client()
    client.force_login(admin_user)
    html = client.get("/admin/").content.decode()
    for frag in (
        "Zones",
        "Sites",
        "Cleaners",
        "Attendance",
        "Issues",
        "Jobs",
        "Trainee program",
        "Site stores",
        "Audit logs",
        "API Docs",
        "Users",
    ):
        assert frag in html, f"missing essential link '{frag}'"


@pytest.mark.django_db
def test_admin_requires_staff() -> None:
    non_staff = UserFactory(is_active=True, is_staff=False)
    client = Client()
    client.force_login(non_staff)
    assert client.get("/admin/").status_code == 302


@pytest.mark.django_db
def test_theme_endpoint_brand_payload(admin_user) -> None:
    client = Client(HTTP_AUTHORIZATION=f"Bearer {issue_api_token(user=admin_user, name='test').key}")
    response = client.get("/api/site-management/v1/theme")
    assert response.status_code == 200
    body = response.json()
    assert body["brand_name"] == "White Bird Zanzibar"
    assert body["brand_primary_color"].startswith("#")
    assert body["brand_accent_color"].startswith("#")
    assert body["logo_url"] == "/static/images/logo.svg"
    assert body["version"]


@pytest.mark.django_db
def test_error_pages_branded() -> None:
    response = Client().get("/this-does-not-exist/")
    assert response.status_code == 404
    assert "White Bird Zanzibar" in response.content.decode()


@pytest.mark.django_db
def test_login_post_still_works(admin_user) -> None:
    response = Client().post(
        "/admin/login/",
        data={"username": admin_user.email, "password": "admin-password-1"},
    )
    assert response.status_code == 302
