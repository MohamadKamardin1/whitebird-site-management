"""Tests for the core health and audit-log API endpoints."""

from unittest import mock

import pytest
from django.test import Client

from apps.accounts.factories import UserFactory
from apps.accounts.models import User
from apps.accounts.services import issue_api_token


@pytest.mark.django_db
def test_health_reports_degraded_when_database_down(admin_client: Client) -> None:
    broken = mock.Mock()
    broken.cursor.side_effect = ConnectionError("db down")

    with mock.patch("apps.core.api.connection", broken):
        response = admin_client.get("/api/site-management/v1/health")

    assert response.status_code == 200
    assert response.json()["database"] is False


@pytest.mark.django_db
def test_health_reports_degraded_when_cache_down(admin_client: Client) -> None:
    broken = mock.Mock()
    broken.set.side_effect = ConnectionError("cache down")

    with mock.patch("apps.core.api.cache", broken):
        response = admin_client.get("/api/site-management/v1/health")

    assert response.status_code == 200
    assert response.json()["cache"] is False
    assert response.json()["status"] == "degraded"


@pytest.mark.django_db
def test_audit_logs_allows_manager_role() -> None:
    manager = UserFactory(role="manager")
    token = _token_for(manager)
    response = Client(HTTP_AUTHORIZATION=f"Bearer {token}").get("/api/site-management/v1/audit-logs")
    assert response.status_code == 200


@pytest.mark.django_db
def test_audit_logs_denies_staff() -> None:
    staff = UserFactory(role="staff")
    token = _token_for(staff)
    response = Client(HTTP_AUTHORIZATION=f"Bearer {token}").get("/api/site-management/v1/audit-logs")
    assert response.status_code == 403


def _token_for(user: User) -> str:
    return issue_api_token(user=user, name="test").key
