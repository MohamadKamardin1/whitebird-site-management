"""Tests for the accounts service layer."""

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.accounts.factories import ApiTokenFactory, UserFactory
from apps.accounts.models import ApiToken, RoleCode
from apps.accounts.services import (
    activate_user,
    create_user,
    deactivate_user,
    issue_api_token,
    refresh_access_token,
    set_password,
    update_user,
)

User = get_user_model()


@pytest.mark.django_db
def test_create_user_requires_password() -> None:
    with pytest.raises(ValidationError):
        create_user(email="x@whitebird.test", password="")


@pytest.mark.django_db
def test_create_user_rejects_weak_password() -> None:
    with pytest.raises(ValidationError):
        create_user(email="x@whitebird.test", password="short")


@pytest.mark.django_db
def test_create_user_with_role_and_audit() -> None:
    from apps.core.models import AuditLog

    actor = UserFactory()
    user = create_user(
        email="service@whitebird.test",
        password="a-strong-pass-1",
        role=RoleCode.ZONE_SUPERVISOR,
        actor=actor,
    )
    assert user.role == RoleCode.ZONE_SUPERVISOR
    assert AuditLog.objects.filter(model_name="accounts.user", object_id=str(user.pk)).exists()


@pytest.mark.django_db
def test_update_user_records_changes() -> None:
    user = UserFactory(first_name="Old")
    updated = update_user(user=user, actor=user, first_name="New", phone="+255700000000")
    assert updated.first_name == "New"
    assert updated.phone == "+255700000000"
    # No-op update returns without touching audit.
    unchanged = update_user(user=user, actor=user)
    assert unchanged.first_name == "New"


@pytest.mark.django_db
def test_set_password_validates_and_changes() -> None:
    user = UserFactory(password="original-pass-1")
    set_password(user=user, new_password="new-pass-12345", actor=user)
    assert user.check_password("new-pass-12345")
    with pytest.raises(ValidationError):
        set_password(user=user, new_password="short", actor=user)


@pytest.mark.django_db
def test_activate_and_deactivate() -> None:
    user = UserFactory(is_active=False)
    activate_user(user=user, actor=user)
    assert user.is_active is True
    deactivate_user(user=user, actor=user)
    assert user.is_active is False


@pytest.mark.django_db
def test_refresh_access_token_lifecycle() -> None:
    user = UserFactory()
    token = ApiTokenFactory(user=user)
    access = refresh_access_token(refresh_token_key=token.key)
    assert access

    token.is_active = False
    token.save(update_fields=["is_active"])
    with pytest.raises(ValidationError):
        refresh_access_token(refresh_token_key=token.key)

    with pytest.raises(ValidationError):
        refresh_access_token(refresh_token_key="does-not-exist")


@pytest.mark.django_db
def test_refresh_rejects_inactive_user() -> None:
    user = UserFactory(is_active=False)
    token = ApiTokenFactory(user=user)
    with pytest.raises(ValidationError):
        refresh_access_token(refresh_token_key=token.key)


@pytest.mark.django_db
def test_issue_api_token_rejects_past_expiry(admin_user) -> None:
    with pytest.raises(ValidationError):
        issue_api_token(user=admin_user, expires_at=timezone.now() - timedelta(days=1))


@pytest.mark.django_db
def test_issue_api_token_audits() -> None:
    from apps.core.models import AuditLog

    user = UserFactory()
    token = issue_api_token(user=user, name="ci")
    assert ApiToken.objects.filter(key=token.key).count() == 1
    assert AuditLog.objects.filter(action=AuditLog.Action.TOKEN_CREATE).count() == 1
