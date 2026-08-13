"""Tests for the custom user model and managers."""

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from apps.accounts.factories import UserFactory
from apps.accounts.models import RoleCode, User
from apps.core.models import AuditLog
from apps.site_management.factories import SiteFactory


@pytest.mark.django_db
def test_create_user_requires_email() -> None:
    with pytest.raises(ValueError):
        User.objects.create_user(email="", password="x")


@pytest.mark.django_db
def test_create_user_normalises_email_lowercase() -> None:
    user = User.objects.create_user(email="  Admin@WhiteBird.test ", password="a-strong-pass-1")
    assert user.email == "admin@whitebird.test"


@pytest.mark.django_db
def test_email_is_unique_case_insensitively() -> None:
    User.objects.create_user(email="admin@whitebird.test", password="a-strong-pass-1")
    with pytest.raises(IntegrityError):
        User.objects.create_user(email="ADMIN@whitebird.test", password="a-strong-pass-2")


@pytest.mark.django_db
def test_create_superuser_gets_staff_and_role() -> None:
    user = User.objects.create_superuser(email="root@whitebird.test", password="a-strong-pass-1")
    assert user.is_staff is True
    assert user.is_superuser is True
    assert user.role == RoleCode.SYSTEM_ADMIN


@pytest.mark.django_db
def test_full_name_property() -> None:
    user = UserFactory(first_name="Juma", last_name="Hassan")
    assert user.full_name == "Juma Hassan"
    anonymous = UserFactory(first_name="", last_name="")
    assert anonymous.full_name == anonymous.email


@pytest.mark.django_db
def test_str_representation_uses_email() -> None:
    user = UserFactory(email="rep@whitebird.test")
    assert str(user) == "rep@whitebird.test"


@pytest.mark.django_db
def test_phone_validation() -> None:
    UserFactory(phone="+255712345678")  # valid international
    UserFactory(phone="0712345678")  # valid local
    with pytest.raises(ValidationError):
        UserFactory(phone="not-a-phone").clean_fields()


@pytest.mark.django_db
def test_timezone_validation() -> None:
    UserFactory(timezone="Africa/Dar_es_Salaam")
    with pytest.raises(ValidationError):
        UserFactory(timezone="Not/AZone").clean_fields()


@pytest.mark.django_db
def test_role_helpers() -> None:
    assert UserFactory(role=RoleCode.SYSTEM_ADMIN).is_system_admin is True
    assert UserFactory(role=RoleCode.SITE_SUPERVISOR).is_site_supervisor is True
    assert UserFactory(role=RoleCode.ZONE_SUPERVISOR).is_zone_supervisor is True
    assert UserFactory(role=RoleCode.ASSISTANT_GENERAL_SUPERVISOR).is_assistant_general_supervisor is True
    assert UserFactory(role=RoleCode.GENERAL_SUPERVISOR).is_general_supervisor is True
    assert UserFactory(role=RoleCode.MANAGEMENT_VIEWER).is_management_viewer is True

    supervisor = UserFactory(role=RoleCode.ZONE_SUPERVISOR)
    assert supervisor.is_supervisor is True
    assert supervisor.is_management_role is True
    viewer = UserFactory(role=RoleCode.MANAGEMENT_VIEWER)
    assert viewer.is_supervisor is False
    assert viewer.is_management_role is False

    superuser = UserFactory(role=RoleCode.MANAGEMENT_VIEWER, is_superuser=True)
    assert superuser.is_system_admin is True


@pytest.mark.django_db
def test_has_operational_history() -> None:
    fresh = UserFactory()
    assert fresh.has_operational_history is False
    SiteFactory(created_by=fresh)  # still no history (created sites are not reverse FK history)
    AuditLog.objects.create(actor=fresh, action="create", entity_type="accounts.user", entity_id=str(fresh.pk))
    assert fresh.has_operational_history is True
