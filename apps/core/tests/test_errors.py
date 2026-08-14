"""Tests for the API error contract (handlers → error envelope)."""

import pytest
from django.test import Client

from apps.accounts.factories import UserFactory
from apps.accounts.models import RoleCode, User
from apps.accounts.services import issue_api_token
from apps.core.errors import BusinessRuleError, ConflictError, ForbiddenActionError, NotFoundError
from apps.core.handlers import error_payload


def _token_for(user: User) -> str:
    return issue_api_token(user=user, name="test").key


def _authed(user: User) -> Client:
    return Client(HTTP_AUTHORIZATION=f"Bearer {_token_for(user)}")


@pytest.mark.django_db
def test_validation_error_maps_to_422() -> None:
    user = UserFactory(role=RoleCode.SYSTEM_ADMIN)
    response = _authed(user).post(
        "/api/site-management/v1/sites",
        data={"name": ""},
        content_type="application/json",
    )
    assert response.status_code in (422, 400)


@pytest.mark.django_db
def test_duplicate_department_maps_to_conflict_or_422() -> None:
    from apps.site_management.factories import SiteFactory
    from apps.site_management.services import create_department

    user = UserFactory(role=RoleCode.SYSTEM_ADMIN)
    site = SiteFactory(created_by=user)
    create_department(site=site, name="Housekeeping", actor=user)
    response = _authed(user).post(
        f"/api/site-management/v1/sites/{site.pk}/departments",
        data={"name": "Housekeeping"},
        content_type="application/json",
    )
    assert response.status_code in (409, 422)


@pytest.mark.django_db
def test_permission_denied_maps_to_403_with_envelope() -> None:
    viewer = UserFactory(role=RoleCode.MANAGEMENT_VIEWER)
    response = _authed(viewer).get("/api/site-management/v1/audit-logs")
    assert response.status_code == 403
    body = response.json()
    assert body["error"]["code"] == "forbidden"
    assert "trace_id" in body["error"]


@pytest.mark.django_db
def test_missing_token_maps_to_401() -> None:
    response = Client().get("/api/site-management/v1/auth/me")
    assert response.status_code == 401


@pytest.mark.django_db
def test_error_payload_shape() -> None:
    payload = error_payload("conflict", "already exists", {"code": ["taken"]})
    assert payload == {
        "error": {
            "code": "conflict",
            "message": "already exists",
            "trace_id": "",
            "fields": {"code": ["taken"]},
        }
    }


@pytest.mark.django_db
def test_object_does_not_exist_maps_to_404() -> None:
    import sys
    import types

    from django.core.exceptions import ObjectDoesNotExist
    from django.test import override_settings
    from django.urls import include, path
    from ninja import NinjaAPI

    from apps.core.handlers import register_error_handlers

    api = NinjaAPI(auth=None, urls_namespace="doesnotexist")
    register_error_handlers(api)

    @api.get("/missing")
    def missing(request):
        raise ObjectDoesNotExist("gone")

    urls_module = types.ModuleType("missing_urls")
    api_urls, app_name, _ = api.urls
    urls_module.urlpatterns = [path("", include((api_urls, app_name), namespace="missing"))]
    sys.modules["missing_urls"] = urls_module

    with override_settings(ROOT_URLCONF="missing_urls"):
        response = Client().get("/missing")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


@pytest.mark.django_db
def test_validation_fields_handles_list_errors() -> None:
    from django.core.exceptions import ValidationError as DjangoValidationError

    from apps.core.handlers import _validation_fields

    exc = DjangoValidationError(["Something failed"])
    fields = _validation_fields(exc)
    assert fields["_"] == ["Something failed"]


@pytest.mark.django_db
def test_unexpected_exception_maps_to_safe_500() -> None:
    import sys
    import types

    from django.test import override_settings
    from django.urls import include, path
    from ninja import NinjaAPI

    from apps.core.handlers import register_error_handlers

    boom_api = NinjaAPI(auth=None, urls_namespace="boom")
    register_error_handlers(boom_api)

    @boom_api.get("/boom")
    def boom(request):
        raise RuntimeError("secret-boom")

    urls_module = types.ModuleType("boom_urls")
    api_urls, app_name, _ = boom_api.urls
    urls_module.urlpatterns = [path("", include((api_urls, app_name), namespace="boom"))]
    sys.modules["boom_urls"] = urls_module

    with override_settings(ROOT_URLCONF="boom_urls"):
        response = Client().get("/boom")
    assert response.status_code == 500
    body = response.json()
    assert body["error"]["code"] == "internal_error"
    assert "secret-boom" not in body["error"]["message"]  # internals never leak


@pytest.mark.django_db
def test_not_found_envelope(admin_client) -> None:
    response = admin_client.get("/api/site-management/v1/zones/999999")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_domain_error_defaults() -> None:
    assert ConflictError("x").status_code == 409
    assert ConflictError("x").code == "conflict"
    assert NotFoundError("x").status_code == 404
    assert ForbiddenActionError("x").status_code == 403
    error = BusinessRuleError("x", status_code=409)
    assert error.status_code == 409
    assert error.code == "business_rule"
