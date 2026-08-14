"""Tests for the idempotent demo-data seed command."""

import pytest
from django.core.management import call_command

from apps.accounts.models import RoleCode, User
from apps.site_management.models import (
    AssetCategory,
    Site,
    SiteStatus,
    SiteSupervisorAssignment,
    SiteType,
    StaffAssignment,
    Zone,
)


@pytest.mark.django_db
def test_seed_command_creates_demo_tenant() -> None:
    call_command("seed_sites")

    assert User.objects.get(email="admin@whitebird.test").role == RoleCode.SYSTEM_ADMIN
    assert (
        User.objects.filter(
            email__in=[
                "general@whitebird.test",
                "zone@whitebird.test",
                "site-supervisor@whitebird.test",
                "viewer@whitebird.test",
            ]
        ).count()
        == 4
    )

    assert Site.objects.count() == 3
    assert SiteType.objects.filter(slug="beach-resort").exists()
    assert SiteStatus.objects.filter(slug="active").exists()
    assert AssetCategory.objects.filter(slug="vehicles").exists()

    resort = Site.objects.get(code="WBBR01")
    assert resort.departments.count() == 3
    assert StaffAssignment.objects.filter(site=resort).count() == 4
    assert Zone.objects.filter(code="ZN01").exists()
    assert resort.zone is not None
    assert SiteSupervisorAssignment.objects.filter(site=resort, is_active=True).count() == 1


@pytest.mark.django_db
def test_seed_command_is_idempotent() -> None:
    call_command("seed_sites")
    call_command("seed_sites")
    assert Site.objects.count() == 3
    assert User.objects.count() == 5
    assert StaffAssignment.objects.count() == 4
