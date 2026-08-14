"""API contract tests: schema, pagination, sorting, errors, auth, throttling."""

from typing import cast

import pytest
from django.core.cache import cache
from django.test import Client, override_settings

from apps.accounts.factories import UserFactory
from apps.accounts.models import RoleCode, User
from apps.accounts.services import issue_api_token
from apps.core.pagination import apply_ordering
from apps.site_management.factories import ZoneFactory


@pytest.fixture(autouse=True)
def rbac_seeded(db: None) -> None:
    from django.core.management import call_command

    call_command("seed_rbac")


def _authed(user: User) -> Client:
    return Client(HTTP_AUTHORIZATION=f"Bearer {issue_api_token(user=user, name='test').key}")


# --------------------------------------------------------------------------- #
# OpenAPI
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
def test_openapi_schema_generation() -> None:
    spec = Client().get("/api/site-management/v1/openapi.json").json()
    assert spec["info"]["title"] == "White Bird Zanzibar — Site Management API"
    assert "securitySchemes" in spec["components"]
    assert spec["components"]["securitySchemes"]["TokenAuth"]["scheme"] == "bearer"
    assert len(spec["paths"]) >= 130


@pytest.mark.django_db
def test_openapi_all_operations_have_tags_and_responses() -> None:
    spec = Client().get("/api/site-management/v1/openapi.json").json()
    for path, methods in spec["paths"].items():
        for method, operation in methods.items():
            if method in {"parameters"}:
                continue
            assert operation.get("tags"), f"{method.upper()} {path} missing tags"
            assert operation.get("responses"), f"{method.upper()} {path} missing responses"


@pytest.mark.django_db
def test_docs_page_available() -> None:
    response = Client().get("/api/site-management/v1/docs")
    assert response.status_code == 200
    assert b"swagger" in response.content.lower() or b"openapi" in response.content.lower()


# --------------------------------------------------------------------------- #
# Pagination
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
def test_pagination_envelope(admin_user) -> None:
    for _ in range(4):
        ZoneFactory()
    client = _authed(admin_user)
    response = client.get("/api/site-management/v1/zones", {"page": 1, "page_size": 2})
    assert response.status_code == 200
    payload = response.json()
    assert {"count", "next", "previous", "results"} <= set(payload)
    assert payload["count"] == 4
    assert len(payload["results"]) == 2
    assert payload["next"] is not None

    page2 = client.get("/api/site-management/v1/zones", {"page": 2, "page_size": 2})
    assert page2.json()["previous"] is not None


@pytest.mark.django_db
def test_pagination_page_size_capped() -> None:
    for _ in range(10):
        ZoneFactory()
    client = _authed(admin_user())
    response = client.get("/api/site-management/v1/zones", {"page_size": 5000})
    assert len(response.json()["results"]) <= 100


def admin_user() -> User:
    return cast(User, UserFactory(role=RoleCode.SYSTEM_ADMIN))


# --------------------------------------------------------------------------- #
# Sorting
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
def test_ordering_whitelist() -> None:
    from apps.site_management.models import Zone

    for name in ["Beta", "Alpha", "Gamma"]:
        ZoneFactory(name=name)
    qs = apply_ordering(Zone.objects.all(), "name", ["name", "code"])
    assert list(qs.values_list("name", flat=True)) == ["Alpha", "Beta", "Gamma"]
    # Unknown fields are ignored (no injection, no error).
    qs2 = apply_ordering(Zone.objects.all(), "-code;DROP TABLE zone", ["name"])
    assert qs2.count() == 3
    # Descending.
    qs3 = apply_ordering(Zone.objects.all(), "-name", ["name"])
    assert list(qs3.values_list("name", flat=True)) == ["Gamma", "Beta", "Alpha"]


@pytest.mark.django_db
def test_ordering_param_accepted_by_api(site, admin_user) -> None:
    from apps.site_management.models import Issue

    Issue.objects.create(
        title="B", site=site, source="manual", issue_category="other", priority="high", raised_by=admin_user
    )
    Issue.objects.create(
        title="A", site=site, source="manual", issue_category="other", priority="low", raised_by=admin_user
    )
    client = _authed(admin_user)
    response = client.get("/api/site-management/v1/issues", {"ordering": "-created_at"})
    assert response.status_code == 200
    assert response.json()["count"] == 2
    # Unknown ordering is ignored safely.
    assert client.get("/api/site-management/v1/issues", {"ordering": "id;drop"}).status_code == 200


# --------------------------------------------------------------------------- #
# Error envelope
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
def test_validation_error_shape(admin_user) -> None:
    client = _authed(admin_user)
    response = client.post(
        "/api/site-management/v1/sites",
        data={"name": ""},
        content_type="application/json",
    )
    assert response.status_code == 422
    body = response.json()["error"]
    assert body["code"] == "validation_error"
    assert body["message"]
    assert body["trace_id"]
    assert "fields" in body


@pytest.mark.django_db
def test_unauthorized_error_shape() -> None:
    response = Client().get("/api/site-management/v1/sites")
    assert response.status_code == 401
    body = response.json()["error"]
    assert body["code"] == "unauthorized"
    assert body["trace_id"]


@pytest.mark.django_db
def test_not_found_error_shape(admin_user) -> None:
    response = _authed(admin_user).get("/api/site-management/v1/sites/99999")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


# --------------------------------------------------------------------------- #
# Auth
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
def test_auth_login_refresh_logout_me(site_supervisor_user) -> None:
    client = Client()
    login = client.post(
        "/api/site-management/v1/auth/login",
        data={"email": site_supervisor_user.email, "password": "site-password-1"},
        content_type="application/json",
    )
    assert login.status_code == 200
    body = login.json()
    assert body["access_token"]
    assert body["refresh_token"]
    assert body["user"]["email"] == site_supervisor_user.email

    me = client.get("/api/site-management/v1/auth/me", HTTP_AUTHORIZATION=f"Bearer {body['access_token']}")
    assert me.status_code == 200
    assert me.json()["email"] == site_supervisor_user.email

    refresh = client.post(
        "/api/site-management/v1/auth/refresh",
        data={"refresh_token": body["refresh_token"]},
        content_type="application/json",
    )
    assert refresh.status_code == 200
    assert refresh.json()["access_token"]

    logout = client.post(
        "/api/site-management/v1/auth/logout",
        data={"refresh_token": body["refresh_token"]},
        content_type="application/json",
    )
    assert logout.status_code == 200


@pytest.mark.django_db
def test_auth_me_permissions(site_supervisor_user) -> None:
    response = _authed(site_supervisor_user).get("/api/site-management/v1/auth/me/permissions")
    assert response.status_code == 200
    payload = response.json()
    assert "actions" in payload
    assert "resources" in payload
    assert isinstance(payload["actions"], list)


# --------------------------------------------------------------------------- #
# Permissions: management viewer read-only
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
def test_management_viewer_read_only(site, viewer_user) -> None:
    viewer = _authed(viewer_user)
    assert viewer.get("/api/site-management/v1/sites").status_code == 200
    assert viewer.get("/api/site-management/v1/theme").status_code == 200
    assert viewer.get("/api/site-management/v1/reports/status").status_code == 200
    denied = viewer.post(
        "/api/site-management/v1/stores",
        data={"site_id": site.pk, "store_name": "X"},
        content_type="application/json",
    )
    assert denied.status_code in (401, 403)


# --------------------------------------------------------------------------- #
# Throttling
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
@override_settings(API_THROTTLE_ENABLED=True, API_THROTTLE_AUTH_RATE="2/min", API_THROTTLE_ANON_RATE="2/min")
def test_throttle_returns_429(admin_user) -> None:
    cache.clear()
    client = _authed(admin_user)
    first = client.get("/api/site-management/v1/theme")
    assert first.status_code == 200
    second = client.get("/api/site-management/v1/theme")
    assert second.status_code == 200
    third = client.get("/api/site-management/v1/theme")
    assert third.status_code == 429
    assert third.json()["error"]["code"] == "rate_limited"
    cache.clear()


# --------------------------------------------------------------------------- #
# Theme
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
def test_theme_endpoint(admin_user) -> None:
    response = _authed(admin_user).get("/api/site-management/v1/theme")
    assert response.status_code == 200
    body = response.json()
    assert body["brand_name"] == "White Bird Zanzibar"
    assert body["brand_primary_color"].startswith("#")


# --------------------------------------------------------------------------- #
# Request ID header on responses
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
def test_request_id_header(admin_user) -> None:
    response = _authed(admin_user).get("/api/site-management/v1/theme", HTTP_X_REQUEST_ID="req-123")
    assert response["X-Request-ID"] == "req-123"
