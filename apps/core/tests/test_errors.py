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


def test_domain_error_defaults() -> None:
    assert ConflictError("x").status_code == 409
    assert ConflictError("x").code == "conflict"
    assert NotFoundError("x").status_code == 404
    assert ForbiddenActionError("x").status_code == 403
    error = BusinessRuleError("x", status_code=409)
    assert error.status_code == 409
    assert error.code == "business_rule"
