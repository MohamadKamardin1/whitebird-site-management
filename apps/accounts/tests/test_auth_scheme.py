"""Tests for the token authentication scheme and role permissions."""

from datetime import timedelta

import pytest
from django.test import Client
from django.utils import timezone

from apps.accounts.factories import ApiTokenFactory, UserFactory
from apps.accounts.models import ApiToken, Role
from apps.accounts.permissions import role_required, user_can_manage_site
from apps.site_management.factories import SiteFactory
from apps.site_management.models import AssignmentRole, StaffAssignment


def _client_with_token(token: ApiToken) -> Client:
    return Client(HTTP_AUTHORIZATION=f"Bearer {token.key}")


@pytest.mark.django_db
def test_expired_token_is_rejected() -> None:
    user = UserFactory()
    token = ApiTokenFactory(user=user, expires_at=timezone.now() - timedelta(minutes=1))
    response = _client_with_token(token).get("/api/site-management/v1/auth/me")
    assert response.status_code == 401


@pytest.mark.django_db
def test_revoked_token_is_rejected() -> None:
    user = UserFactory()
    token = ApiTokenFactory(user=user)
    token.is_active = False
    token.save(update_fields=["is_active"])
    response = _client_with_token(token).get("/api/site-management/v1/auth/me")
    assert response.status_code == 401


@pytest.mark.django_db
def test_inactive_user_token_is_rejected() -> None:
    user = UserFactory(is_active=False)
    token = ApiTokenFactory(user=user)
    response = _client_with_token(token).get("/api/site-management/v1/auth/me")
    assert response.status_code == 401


@pytest.mark.django_db
def test_unknown_token_is_rejected() -> None:
    response = Client(HTTP_AUTHORIZATION="Bearer not-a-real-token").get("/api/site-management/v1/auth/me")
    assert response.status_code == 401


@pytest.mark.django_db
def test_usage_refreshes_last_used_at() -> None:
    user = UserFactory()
    token = ApiTokenFactory(user=user)
    assert token.last_used_at is None
    response = _client_with_token(token).get("/api/site-management/v1/auth/me")
    assert response.status_code == 200
    token.refresh_from_db()
    assert token.last_used_at is not None


# --------------------------------------------------------------------------- #
# Permissions
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
def test_role_required_allows_matching_roles_and_superusers() -> None:
    predicate = role_required(Role.MANAGER)
    assert predicate(UserFactory(role=Role.MANAGER)) is True
    assert predicate(UserFactory(role=Role.STAFF)) is False
    assert predicate(UserFactory(role=Role.VIEWER)) is False
    superuser = UserFactory(role=Role.VIEWER, is_superuser=True)
    assert predicate(superuser) is True


@pytest.mark.django_db
def test_user_can_manage_site_rules() -> None:
    admin = UserFactory(role=Role.ADMIN)
    manager = UserFactory(role=Role.MANAGER)
    staff = UserFactory(role=Role.STAFF)
    site_manager = UserFactory(role=Role.STAFF)
    outsider = UserFactory(role=Role.MANAGER)
    site = SiteFactory()

    assert user_can_manage_site(admin, site.pk) is True

    StaffAssignment.objects.create(site=site, user=manager, role=AssignmentRole.STAFF)
    assert user_can_manage_site(manager, site.pk) is True

    StaffAssignment.objects.create(site=site, user=staff, role=AssignmentRole.STAFF)
    assert user_can_manage_site(staff, site.pk) is False

    StaffAssignment.objects.create(site=site, user=site_manager, role=AssignmentRole.SITE_MANAGER)
    assert user_can_manage_site(site_manager, site.pk) is True

    assert user_can_manage_site(outsider, site.pk) is False
