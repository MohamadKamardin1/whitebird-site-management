"""Tests for the session-auth views (login + password reset/change foundation)."""

from typing import Any

import pytest
from django.test import Client

from apps.accounts.models import User


@pytest.mark.django_db
def test_login_view_accepts_email() -> None:
    user = User.objects.create_user(email="session@whitebird.test", password="correct-horse-1", is_staff=True)
    response = Client().post(
        "/accounts/login/",
        data={"username": user.email, "password": "correct-horse-1"},
    )
    assert response.status_code == 302


@pytest.mark.django_db
def test_password_reset_view_sends_email(admin_user: User, mailoutbox: Any) -> None:
    response = Client().post("/accounts/password_reset/", data={"email": admin_user.email})
    assert response.status_code == 302
    assert len(mailoutbox) == 1
    assert admin_user.email in mailoutbox[0].to


@pytest.mark.django_db
def test_password_reset_view_renders_for_unknown_email(mailoutbox: Any) -> None:
    # The view must not leak whether an email exists.
    response = Client().post("/accounts/password_reset/", data={"email": "nobody@whitebird.test"})
    assert response.status_code == 302
    assert len(mailoutbox) == 0


@pytest.mark.django_db
def test_password_change_view_requires_login(admin_user: User) -> None:
    client = Client()
    client.force_login(admin_user)
    response = client.get("/accounts/password_change/")
    assert response.status_code == 200
