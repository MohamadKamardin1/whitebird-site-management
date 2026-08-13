"""Tests for security configuration: axes lockout and password validators."""

from datetime import timedelta
from typing import Any, cast

import pytest
from django.conf import settings
from django.core.exceptions import ValidationError
from django.test import Client, override_settings

from apps.accounts.factories import UserFactory
from apps.accounts.services import create_user


@pytest.mark.django_db
@override_settings(
    AXES_ENABLED=True,
    AXES_FAILURE_LIMIT=3,
    AXES_COOLOFF_TIME=timedelta(hours=1),
    AXES_LOCKOUT_PARAMETERS=[["username", "ip_address"]],
)
def test_axes_locks_account_after_repeated_failures() -> None:
    user = UserFactory(email="axes@whitebird.test", password="correct-horse-1")
    client = Client()

    for _ in range(3):
        client.post(
            "/api/site-management/v1/auth/login",
            data={"email": user.email, "password": "wrong-password"},
            content_type="application/json",
        )

    # Even correct credentials are rejected while locked out.
    locked = client.post(
        "/api/site-management/v1/auth/login",
        data={"email": user.email, "password": "correct-horse-1"},
        content_type="application/json",
    )
    assert locked.status_code in (401, 403, 429)


@pytest.mark.django_db
def test_axes_disabled_by_default_in_tests() -> None:
    assert settings.AXES_ENABLED is False


def test_password_validators_require_minimum_12() -> None:
    validators = cast(list[dict[str, Any]], settings.AUTH_PASSWORD_VALIDATORS)
    min_length = 0
    for validator in validators:
        if "MinimumLengthValidator" in validator["NAME"]:
            options = cast(dict[str, Any], validator.get("OPTIONS") or {})
            min_length = int(options.get("min_length", 0))
    assert min_length == 12
    names = {v["NAME"] for v in validators}
    assert "django.contrib.auth.password_validation.NumericPasswordValidator" in names
    assert "django.contrib.auth.password_validation.CommonPasswordValidator" in names


@pytest.mark.django_db
def test_password_validator_enforced_on_service_creation() -> None:
    with pytest.raises(ValidationError):
        create_user(email="weak@whitebird.test", password="short")
