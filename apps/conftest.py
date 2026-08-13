"""Shared pytest fixtures for the White Bird test suite."""

from __future__ import annotations

import shutil
from collections.abc import Iterator
from pathlib import Path
from typing import Any, cast

import pytest
from django.conf import settings
from django.core.cache import cache
from django.test import Client

from apps.accounts.factories import UserFactory
from apps.accounts.models import RoleCode, User
from apps.accounts.services import issue_api_token
from apps.site_management.factories import (
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


@pytest.fixture(autouse=True)
def _clean_media() -> Iterator[None]:
    """Remove any files written to the private media root during a test."""
    media_root = Path(settings.PRIVATE_MEDIA_ROOT)
    yield
    if media_root.exists():
        shutil.rmtree(media_root, ignore_errors=True)
        media_root.mkdir(parents=True, exist_ok=True)


@pytest.fixture
def admin_user(db: Any) -> User:
    return cast(
        User,
        UserFactory(
            email="admin@whitebird.test",
            password="admin-password-1",
            role=RoleCode.SYSTEM_ADMIN,
            is_superuser=True,
            is_staff=True,
        ),
    )


@pytest.fixture
def general_user(db: Any) -> User:
    return cast(
        User,
        UserFactory(
            email="general@whitebird.test",
            password="general-password-1",
            role=RoleCode.GENERAL_SUPERVISOR,
        ),
    )


@pytest.fixture
def zone_user(db: Any) -> User:
    return cast(
        User,
        UserFactory(
            email="zone@whitebird.test",
            password="zone-password-1",
            role=RoleCode.ZONE_SUPERVISOR,
        ),
    )


@pytest.fixture
def site_supervisor_user(db: Any) -> User:
    return cast(
        User,
        UserFactory(
            email="site-supervisor@whitebird.test",
            password="site-password-1",
            role=RoleCode.SITE_SUPERVISOR,
        ),
    )


@pytest.fixture
def viewer_user(db: Any) -> User:
    return cast(
        User,
        UserFactory(
            email="viewer@whitebird.test",
            password="viewer-password-1",
            role=RoleCode.MANAGEMENT_VIEWER,
        ),
    )


# Legacy aliases used by site-scoped tests: "staff" is the read-only viewer and
# "manager" is a zone supervisor with write capacity on assigned sites.
@pytest.fixture
def staff_user(viewer_user: User) -> User:
    return viewer_user


@pytest.fixture
def manager_user(zone_user: User) -> User:
    return zone_user


def _authed_client(user: User) -> Client:
    token = issue_api_token(user=user, name="test")
    return Client(HTTP_AUTHORIZATION=f"Bearer {token.key}")


@pytest.fixture
def admin_client(admin_user: User) -> Client:
    return _authed_client(admin_user)


@pytest.fixture
def general_client(general_user: User) -> Client:
    return _authed_client(general_user)


@pytest.fixture
def zone_client(zone_user: User) -> Client:
    return _authed_client(zone_user)


@pytest.fixture
def site_supervisor_client(site_supervisor_user: User) -> Client:
    return _authed_client(site_supervisor_user)


@pytest.fixture
def viewer_client(viewer_user: User) -> Client:
    return _authed_client(viewer_user)


@pytest.fixture
def staff_client(viewer_user: User) -> Client:
    return _authed_client(viewer_user)


@pytest.fixture
def manager_client(zone_user: User) -> Client:
    return _authed_client(zone_user)


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
