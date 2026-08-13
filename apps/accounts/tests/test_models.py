"""Tests for account models and token lifecycle."""

from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.accounts.models import ApiToken, Role
from apps.accounts.services import create_user, issue_api_token, revoke_api_token


@pytest.mark.django_db
def test_create_user_assigns_role():
    user = create_user(username="juma", password="strong-pass-1", role=Role.MANAGER)
    assert user.role == Role.MANAGER
    assert user.check_password("strong-pass-1")


@pytest.mark.django_db
def test_create_user_rejects_empty_password():
    with pytest.raises(ValidationError):
        create_user(username="nopass", password="")


@pytest.mark.django_db
def test_token_key_is_generated_and_unique(admin_user):
    token = issue_api_token(user=admin_user, name="ci")
    assert token.key
    assert ApiToken.objects.filter(key=token.key).count() == 1


@pytest.mark.django_db
def test_token_usable_flag(admin_user):
    token = issue_api_token(user=admin_user, expires_at=None)
    assert token.usable is True
    revoke_api_token(token=token)
    token.refresh_from_db()
    assert token.usable is False


@pytest.mark.django_db
def test_issue_token_rejects_past_expiry(admin_user):
    with pytest.raises(ValidationError):
        issue_api_token(user=admin_user, expires_at=timezone.now() - timedelta(days=1))


@pytest.mark.django_db
def test_user_is_admin_property(staff_user, admin_user):
    assert admin_user.is_admin is True
    assert staff_user.is_admin is False
