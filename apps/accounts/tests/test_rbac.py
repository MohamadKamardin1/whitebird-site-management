"""Tests for the RBAC seeding command and role-group sync signal."""

import pytest
from django.contrib.auth.models import Group
from django.core.management import call_command

from apps.accounts.factories import UserFactory
from apps.accounts.models import RoleCode
from apps.accounts.rbac import ROLE_GROUP_NAMES, ROLE_PERMISSIONS


@pytest.mark.django_db
def test_seed_rbac_creates_all_groups() -> None:
    call_command("seed_rbac")
    assert Group.objects.count() == len(ROLE_GROUP_NAMES)
    for group_name in ROLE_GROUP_NAMES.values():
        assert Group.objects.filter(name=group_name).exists()


@pytest.mark.django_db
def test_seed_rbac_assigns_expected_permissions() -> None:
    call_command("seed_rbac")
    group = Group.objects.get(name=ROLE_GROUP_NAMES[RoleCode.ZONE_SUPERVISOR])
    expected = ROLE_PERMISSIONS[RoleCode.ZONE_SUPERVISOR]
    actual = {(p.content_type.app_label, p.codename) for p in group.permissions.all()}
    assert actual == expected


@pytest.mark.django_db
def test_seed_rbac_gives_system_admin_everything() -> None:
    call_command("seed_rbac")
    group = Group.objects.get(name=ROLE_GROUP_NAMES[RoleCode.SYSTEM_ADMIN])
    assert group.permissions.count() == len(ROLE_PERMISSIONS[RoleCode.SYSTEM_ADMIN])


@pytest.mark.django_db
def test_seed_rbac_is_idempotent() -> None:
    call_command("seed_rbac")
    first = Group.objects.get(name=ROLE_GROUP_NAMES[RoleCode.SITE_SUPERVISOR]).permissions.count()
    call_command("seed_rbac")
    assert Group.objects.count() == len(ROLE_GROUP_NAMES)
    assert Group.objects.get(name=ROLE_GROUP_NAMES[RoleCode.SITE_SUPERVISOR]).permissions.count() == first


@pytest.mark.django_db
def test_user_role_group_sync_on_save() -> None:
    user = UserFactory(role=RoleCode.ZONE_SUPERVISOR)
    assert user.groups.filter(name=ROLE_GROUP_NAMES[RoleCode.ZONE_SUPERVISOR]).exists()

    user.role = RoleCode.SITE_SUPERVISOR
    user.save()
    assert user.groups.filter(name=ROLE_GROUP_NAMES[RoleCode.SITE_SUPERVISOR]).exists()
    assert not user.groups.filter(name=ROLE_GROUP_NAMES[RoleCode.ZONE_SUPERVISOR]).exists()


@pytest.mark.django_db
def test_user_role_group_preserves_non_role_groups() -> None:
    user = UserFactory(role=RoleCode.SITE_SUPERVISOR)
    extra = Group.objects.create(name="Special Projects")
    user.groups.add(extra)
    user.role = RoleCode.ZONE_SUPERVISOR
    user.save()
    assert user.groups.filter(name="Special Projects").exists()


@pytest.mark.django_db
def test_group_permissions_grant_real_has_perm() -> None:
    call_command("seed_rbac")
    user = UserFactory(role=RoleCode.ZONE_SUPERVISOR)
    assert user.has_perm("site_management.add_site") is True
    viewer = UserFactory(role=RoleCode.MANAGEMENT_VIEWER)
    assert viewer.has_perm("site_management.add_site") is False
    assert viewer.has_perm("accounts.export_site_management_data") is True
