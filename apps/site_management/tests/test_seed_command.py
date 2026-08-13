"""Tests for the idempotent demo-data seed command."""

import pytest
from django.core.management import call_command

from apps.accounts.models import Role, User
from apps.site_management.models import AssetCategory, Site, SiteStatus, SiteType, StaffAssignment


@pytest.mark.django_db
def test_seed_command_creates_demo_tenant() -> None:
    call_command("seed_sites")

    assert User.objects.get(username="admin").role == Role.ADMIN
    assert User.objects.filter(username__in=["juma", "amina", "viewer"]).count() == 3

    assert Site.objects.count() == 3
    assert SiteType.objects.filter(slug="beach-resort").exists()
    assert SiteStatus.objects.filter(slug="active").exists()
    assert AssetCategory.objects.filter(slug="vehicles").exists()

    resort = Site.objects.get(code="WBBR01")
    assert resort.departments.count() == 3
    assert StaffAssignment.objects.filter(site=resort).count() == 3


@pytest.mark.django_db
def test_seed_command_is_idempotent() -> None:
    call_command("seed_sites")
    call_command("seed_sites")
    assert Site.objects.count() == 3
    assert User.objects.count() == 4
    assert StaffAssignment.objects.count() == 3
