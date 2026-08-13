"""Tests for the token auth scheme and permission predicates."""

from datetime import timedelta

import pytest
from django.test import Client
from django.utils import timezone

from apps.accounts.factories import ApiTokenFactory, UserFactory
from apps.accounts.models import ApiToken, RoleCode
from apps.accounts.permissions import management_required, role_required, user_can_manage_site
from apps.site_management.factories import SiteFactory
from apps.site_management.models import AssignmentRole, StaffAssignment


def _client_with_token(token: ApiToken | str) -> Client:
    return Client(HTTP_AUTHORIZATION=f"Bearer {token if isinstance(token, str) else token.key}")


@pytest.mark.django_db
def test_expired_refresh_token_is_rejected() -> None:
    user = UserFactory()
    token = ApiTokenFactory(user=user, expires_at=timezone.now() - timedelta(minutes=1))
    assert _client_with_token(token).get("/api/site-management/v1/auth/me").status_code == 401


@pytest.mark.django_db
def test_revoked_refresh_token_is_rejected() -> None:
    user = UserFactory()
    token = ApiTokenFactory(user=user)
    token.is_active = False
    token.save(update_fields=["is_active"])
    assert _client_with_token(token).get("/api/site-management/v1/auth/me").status_code == 401


@pytest.mark.django_db
def test_inactive_user_token_is_rejected() -> None:
    user = UserFactory(is_active=False)
    token = ApiTokenFactory(user=user)
    assert _client_with_token(token).get("/api/site-management/v1/auth/me").status_code == 401


@pytest.mark.django_db
def test_unknown_token_is_rejected() -> None:
    assert _client_with_token("not-a-real-token").get("/api/site-management/v1/auth/me").status_code == 401


@pytest.mark.django_db
def test_usage_refreshes_last_used_at() -> None:
    user = UserFactory()
    token = ApiTokenFactory(user=user)
    assert token.last_used_at is None
    assert _client_with_token(token).get("/api/site-management/v1/auth/me").status_code == 200
    token.refresh_from_db()
    assert token.last_used_at is not None


# --------------------------------------------------------------------------- #
# Permissions
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
def test_role_required_allows_matching_roles_and_superusers() -> None:
    predicate = role_required(RoleCode.ZONE_SUPERVISOR)
    assert predicate(UserFactory(role=RoleCode.ZONE_SUPERVISOR)) is True
    assert predicate(UserFactory(role=RoleCode.SITE_SUPERVISOR)) is False
    assert predicate(UserFactory(role=RoleCode.MANAGEMENT_VIEWER)) is False
    superuser = UserFactory(role=RoleCode.MANAGEMENT_VIEWER, is_superuser=True)
    assert predicate(superuser) is True


@pytest.mark.django_db
def test_management_required() -> None:
    assert management_required(UserFactory(role=RoleCode.SYSTEM_ADMIN)) is True
    assert management_required(UserFactory(role=RoleCode.ZONE_SUPERVISOR)) is True
    assert management_required(UserFactory(role=RoleCode.MANAGEMENT_VIEWER)) is False


@pytest.mark.django_db
def test_user_can_manage_site_rules() -> None:
    admin = UserFactory(role=RoleCode.SYSTEM_ADMIN)
    general = UserFactory(role=RoleCode.GENERAL_SUPERVISOR)
    zone = UserFactory(role=RoleCode.ZONE_SUPERVISOR)
    site_supervisor = UserFactory(role=RoleCode.SITE_SUPERVISOR)
    viewer = UserFactory(role=RoleCode.MANAGEMENT_VIEWER)
    outsider = UserFactory(role=RoleCode.ZONE_SUPERVISOR)
    site = SiteFactory()

    assert user_can_manage_site(admin, site.pk) is True
    assert user_can_manage_site(outsider, site.pk) is False

    StaffAssignment.objects.create(site=site, user=zone, role=AssignmentRole.STAFF)
    assert user_can_manage_site(zone, site.pk) is True

    StaffAssignment.objects.create(site=site, user=viewer, role=AssignmentRole.STAFF)
    assert user_can_manage_site(viewer, site.pk) is False

    StaffAssignment.objects.create(site=site, user=site_supervisor, role=AssignmentRole.STAFF)
    assert user_can_manage_site(site_supervisor, site.pk) is True

    StaffAssignment.objects.create(site=site, user=general, role=AssignmentRole.STAFF)
    assert user_can_manage_site(general, site.pk) is True
