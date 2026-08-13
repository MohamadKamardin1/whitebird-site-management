"""Shared pytest fixtures for the White Bird test suite."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from django.core.cache import cache
from django.test import Client

from apps.accounts.models import Role, User
from apps.accounts.services import issue_api_token
from apps.sites.models import (
    AssetCategory,
    Site,
    SiteStatus,
    SiteType,
)


@pytest.fixture(autouse=True)
def _fresh_cache() -> Iterator[None]:
    """The local-memory cache survives transaction rollbacks, so clear it
    between tests to keep selectors deterministic."""
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def admin_user(db: Any) -> User:
    return User.objects.create_user(
        username="admin", password="adminpass1", role=Role.ADMIN, is_superuser=True, is_staff=True
    )


@pytest.fixture
def manager_user(db: Any) -> User:
    return User.objects.create_user(
        username="manager", password="managerpass1", role=Role.MANAGER
    )


@pytest.fixture
def staff_user(db: Any) -> User:
    return User.objects.create_user(
        username="staff", password="staffpass1", role=Role.STAFF
    )


@pytest.fixture
def viewer_user(db: Any) -> User:
    return User.objects.create_user(
        username="viewer", password="viewerpass1", role=Role.VIEWER
    )


def _authed_client(user: User) -> Client:
    token = issue_api_token(user=user, name="test")
    return Client(HTTP_AUTHORIZATION=f"Bearer {token.key}")


@pytest.fixture
def admin_client(admin_user: User) -> Client:
    return _authed_client(admin_user)


@pytest.fixture
def manager_client(manager_user: User) -> Client:
    return _authed_client(manager_user)


@pytest.fixture
def staff_client(staff_user: User) -> Client:
    return _authed_client(staff_user)


@pytest.fixture
def anon_client() -> Client:
    return Client()


@pytest.fixture
def site_type(db: Any) -> SiteType:
    return SiteType.objects.create(name="Beach Resort", slug="beach-resort")


@pytest.fixture
def site_status(db: Any) -> SiteStatus:
    return SiteStatus.objects.create(name="Active", slug="active", order=1, color="#10b981")


@pytest.fixture
def asset_category(db: Any) -> AssetCategory:
    return AssetCategory.objects.create(name="Vehicles", slug="vehicles")


@pytest.fixture
def site(db: Any, site_type: SiteType, site_status: SiteStatus, admin_user: User) -> Site:
    return Site.objects.create(
        name="White Bird Beach Resort",
        slug="white-bird-beach-resort",
        code="WBBR01",
        site_type=site_type,
        status=site_status,
        city="Nungwi",
        region="Unguja North",
        country="TZ",
        capacity=100,
        created_by=admin_user,
    )
