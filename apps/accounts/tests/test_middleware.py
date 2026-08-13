"""Tests for the user timezone middleware."""

from typing import cast

import pytest
from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.http import HttpResponse
from django.test import RequestFactory
from django.utils import timezone

from apps.accounts.factories import UserFactory
from apps.accounts.middleware import UserTimezoneMiddleware
from apps.accounts.models import User


@pytest.mark.django_db
def test_middleware_activates_user_timezone_during_request() -> None:
    user = cast(User, UserFactory(timezone="America/New_York"))
    request = RequestFactory().get("/healthz")
    request.user = user
    captured: list[str] = []

    def get_response(req) -> HttpResponse:
        captured.append(str(timezone.get_current_timezone()))
        return HttpResponse("ok")

    UserTimezoneMiddleware(get_response)(request)

    assert captured == ["America/New_York"]
    # The zone must not leak past the request.
    assert timezone.get_current_timezone().key in {"UTC", "Africa/Dar_es_Salaam"}


@pytest.mark.django_db
def test_middleware_falls_back_to_utc_for_invalid_zone() -> None:
    user = cast(User, UserFactory(timezone="Africa/Dar_es_Salaam"))
    request = RequestFactory().get("/healthz")
    request.user = user
    captured: list[str] = []

    def get_response(req) -> HttpResponse:
        captured.append(str(timezone.get_current_timezone()))
        return HttpResponse("ok")

    User.objects.filter(pk=user.pk).update(timezone="Invalid/Zone")
    user.refresh_from_db()

    UserTimezoneMiddleware(get_response)(request)
    assert captured == ["UTC"]


@pytest.mark.django_db
def test_middleware_ignores_anonymous_users() -> None:
    request = RequestFactory().get("/healthz")
    request.user = AnonymousUser()
    captured: list[str] = []

    def get_response(req) -> HttpResponse:
        captured.append(str(timezone.get_current_timezone()))
        return HttpResponse("ok")

    UserTimezoneMiddleware(get_response)(request)
    assert captured == [settings.TIME_ZONE]
