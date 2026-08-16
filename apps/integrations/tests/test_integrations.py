"""Tests for the DeepSeek + Mapbox integration engines, services, API and tasks.

Hermetic: no real network — HTTP is mocked via ``httpx.MockTransport`` and
monkeypatched ``request_json``.
"""

import datetime
from typing import Any

import httpx
import pytest
from django.core.cache import cache
from django.test import Client, override_settings

from apps.accounts.factories import UserFactory
from apps.accounts.services import issue_api_token
from apps.integrations import deepseek, mapbox
from apps.integrations.services import geocode_site, summarize_site_report
from apps.integrations.transport import ProviderError, request_json


@pytest.fixture(autouse=True)
def _clear_cache() -> Any:
    cache.clear()
    yield
    cache.clear()


def _authed(user: Any) -> Client:
    return Client(HTTP_AUTHORIZATION=f"Bearer {issue_api_token(user=user, name='test').key}")


# --------------------------------------------------------------------------- #
# Transport
# --------------------------------------------------------------------------- #


def test_request_json_success() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": True})

    result = request_json(
        provider="X", method="GET", url="http://x", headers={}, transport=httpx.MockTransport(handler)
    )
    assert result == {"ok": True}


def test_request_json_http_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text="bad key")

    with pytest.raises(ProviderError) as exc_info:
        request_json(provider="X", method="GET", url="http://x", headers={}, transport=httpx.MockTransport(handler))
    assert "401" in exc_info.value.message
    assert exc_info.value.provider == "X"


def test_request_json_retries_then_fails() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        raise httpx.ConnectError("boom")

    with pytest.raises(ProviderError) as exc_info:
        request_json(
            provider="X",
            method="GET",
            url="http://x",
            headers={},
            max_retries=2,
            transport=httpx.MockTransport(handler),
        )
    assert exc_info.value.message.startswith("request failed after retries")
    assert calls["n"] == 3  # 1 attempt + 2 retries


# --------------------------------------------------------------------------- #
# DeepSeek engine
# --------------------------------------------------------------------------- #


@override_settings(DEEPSEEK_ENABLED=True, DEEPSEEK_API_KEY="ds-test")
def test_deepseek_complete_chat_and_summarize(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    def fake_request_json(**kwargs: Any) -> dict[str, Any]:
        captured["body"] = kwargs.get("json")
        captured["auth"] = kwargs.get("headers", {}).get("Authorization")
        return {"choices": [{"message": {"content": "The summary."}}]}

    monkeypatch.setattr(deepseek, "request_json", fake_request_json)
    assert deepseek.summarize("long text to summarise") == "The summary."
    assert captured["auth"] == "Bearer ds-test"
    assert captured["body"]["model"] == "deepseek-v4-pro"


@override_settings(DEEPSEEK_ENABLED=False)
@pytest.mark.django_db
def test_deepseek_disabled_raises() -> None:
    with pytest.raises(ProviderError):
        deepseek.summarize("text")


@override_settings(DEEPSEEK_ENABLED=True, DEEPSEEK_API_KEY="x")
def test_deepseek_bad_response_shape(monkeypatch) -> None:
    monkeypatch.setattr(deepseek, "request_json", lambda **kwargs: {"choices": []})
    with pytest.raises(ProviderError):
        deepseek.complete_chat([{"role": "user", "content": "hi"}])


@override_settings(DEEPSEEK_ENABLED=True, DEEPSEEK_API_KEY="x")
def test_deepseek_empty_text(monkeypatch) -> None:
    monkeypatch.setattr(deepseek, "request_json", lambda **kwargs: {"choices": [{"message": {"content": "x"}}]})
    with pytest.raises(ProviderError):
        deepseek.summarize("   ")


# --------------------------------------------------------------------------- #
# Mapbox engine
# --------------------------------------------------------------------------- #


@override_settings(MAPBOX_ENABLED=True, MAPBOX_API_KEY="mb-test")
def test_mapbox_geocode_and_cache(monkeypatch) -> None:
    calls = {"n": 0}

    def fake_request_json(**kwargs: Any) -> dict[str, Any]:
        calls["n"] += 1
        assert kwargs["params"]["access_token"] == "mb-test"
        return {"features": [{"text": "Nungwi", "place_name": "Nungwi, Zanzibar", "center": [39.2, -5.7]}]}

    monkeypatch.setattr(mapbox, "request_json", fake_request_json)
    feature = mapbox.geocode("Nungwi")
    assert feature is not None
    assert feature["longitude"] == 39.2
    assert feature["latitude"] == -5.7
    # Second call is served from cache — no request.
    mapbox.geocode("Nungwi")
    assert calls["n"] == 1


@override_settings(MAPBOX_ENABLED=True, MAPBOX_API_KEY="x")
def test_mapbox_geocode_no_results(monkeypatch) -> None:
    monkeypatch.setattr(mapbox, "request_json", lambda **kwargs: {"features": []})
    assert mapbox.geocode("nowhere") is None


@override_settings(MAPBOX_ENABLED=False)
@pytest.mark.django_db
def test_mapbox_disabled_raises() -> None:
    with pytest.raises(ProviderError):
        mapbox.geocode("Nungwi")


@override_settings(MAPBOX_ENABLED=True, MAPBOX_API_KEY="x")
def test_mapbox_reverse_geocode(monkeypatch) -> None:
    monkeypatch.setattr(
        mapbox,
        "request_json",
        lambda **kwargs: {"features": [{"text": "Stone Town", "place_name": "Stone Town", "center": [39.1, -6.2]}]},
    )
    feature = mapbox.reverse_geocode(39.1, -6.2)
    assert feature is not None
    assert feature["name"] == "Stone Town"


# --------------------------------------------------------------------------- #
# Services
# --------------------------------------------------------------------------- #


@override_settings(DEEPSEEK_ENABLED=True, DEEPSEEK_API_KEY="x")
def test_summarize_site_report(monkeypatch, site) -> None:
    from apps.site_management.reporting_services import generate_site_report

    report = generate_site_report(site_id=site.pk, day=datetime.date.today(), user=UserFactory())
    monkeypatch.setattr(deepseek, "summarize", lambda text, instruction="": "Bullet summary")
    assert summarize_site_report(report) == "Bullet summary"


@override_settings(DEEPSEEK_ENABLED=False)
def test_summarize_site_report_disabled(monkeypatch, site) -> None:
    from apps.site_management.reporting_services import generate_site_report

    report = generate_site_report(site_id=site.pk, day=datetime.date.today(), user=UserFactory())
    assert summarize_site_report(report) is None


@override_settings(MAPBOX_ENABLED=True, MAPBOX_API_KEY="x")
def test_geocode_site_updates_coordinates(monkeypatch, site) -> None:
    monkeypatch.setattr(
        mapbox,
        "geocode",
        lambda q: {"name": "Nungwi", "place_name": "Nungwi", "longitude": 39.2, "latitude": -5.7},
    )
    feature = geocode_site(site)
    site.refresh_from_db()
    assert site.latitude == -5.7
    assert site.longitude == 39.2
    assert feature is not None
    assert feature["longitude"] == 39.2


@override_settings(MAPBOX_ENABLED=True, MAPBOX_API_KEY="x")
def test_geocode_site_no_coordinates_raises(monkeypatch, site) -> None:
    from django.core.exceptions import ValidationError

    monkeypatch.setattr(mapbox, "geocode", lambda q: {"name": "?", "longitude": None, "latitude": None})
    with pytest.raises(ValidationError):
        geocode_site(site)


# --------------------------------------------------------------------------- #
# API
# --------------------------------------------------------------------------- #


@override_settings(DEEPSEEK_ENABLED=False)
def test_api_ai_summarize_disabled_503(admin_user) -> None:
    response = _authed(admin_user).post(
        "/api/site-management/v1/ai/summarize",
        data={"text": "hello world"},
        content_type="application/json",
    )
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "deepseek_error"


@override_settings(DEEPSEEK_ENABLED=True, DEEPSEEK_API_KEY="x")
def test_api_ai_summarize_ok(monkeypatch, admin_user) -> None:
    monkeypatch.setattr(deepseek, "summarize", lambda text, instruction="": "Summary OK")
    response = _authed(admin_user).post(
        "/api/site-management/v1/ai/summarize",
        data={"text": "report body", "instruction": "be brief"},
        content_type="application/json",
    )
    assert response.status_code == 200
    assert response.json()["summary"] == "Summary OK"


@override_settings(DEEPSEEK_ENABLED=True, DEEPSEEK_API_KEY="x")
def test_api_ai_summarize_forbidden_for_viewer(monkeypatch, viewer_user) -> None:
    monkeypatch.setattr(deepseek, "summarize", lambda text, instruction="": "x")
    response = _authed(viewer_user).post(
        "/api/site-management/v1/ai/summarize",
        data={"text": "body"},
        content_type="application/json",
    )
    assert response.status_code == 403


@override_settings(MAPBOX_ENABLED=True, MAPBOX_API_KEY="x")
def test_api_geo_geocode_ok(monkeypatch, admin_user) -> None:
    monkeypatch.setattr(
        mapbox, "geocode", lambda q: {"name": "Nungwi", "place_name": "Nungwi", "longitude": 39.2, "latitude": -5.7}
    )
    response = _authed(admin_user).get("/api/site-management/v1/geo/geocode", {"q": "Nungwi"})
    assert response.status_code == 200
    assert response.json()["longitude"] == 39.2


@override_settings(MAPBOX_ENABLED=True, MAPBOX_API_KEY="x")
def test_api_geo_reverse_viewer_allowed(monkeypatch, viewer_user) -> None:
    monkeypatch.setattr(
        mapbox, "reverse_geocode", lambda longitude, latitude: {"name": "Place", "longitude": 1.0, "latitude": 2.0}
    )
    response = _authed(viewer_user).get("/api/site-management/v1/geo/reverse", {"lng": 1.0, "lat": 2.0})
    assert response.status_code == 200
    assert response.json()["name"] == "Place"


@override_settings(MAPBOX_ENABLED=False)
def test_api_geo_disabled_503(admin_user) -> None:
    response = _authed(admin_user).get("/api/site-management/v1/geo/geocode", {"q": "x"})
    assert response.status_code == 503


# --------------------------------------------------------------------------- #
# Celery tasks (eager)
# --------------------------------------------------------------------------- #


@override_settings(DEEPSEEK_ENABLED=True, DEEPSEEK_API_KEY="x")
def test_summarize_report_task(monkeypatch, site, admin_user) -> None:
    from apps.integrations.tasks import summarize_site_report as task
    from apps.site_management.reporting_services import generate_site_report

    monkeypatch.setattr(deepseek, "summarize", lambda text, instruction="": "Task summary")
    report = generate_site_report(site_id=site.pk, day=datetime.date.today(), user=admin_user)
    assert task(report_id=report.pk) == "Task summary"


@override_settings(MAPBOX_ENABLED=True, MAPBOX_API_KEY="x")
def test_geocode_site_task(monkeypatch, site) -> None:
    from apps.integrations.tasks import geocode_site as task

    monkeypatch.setattr(
        mapbox, "geocode", lambda q: {"name": "N", "place_name": "N", "longitude": 39.0, "latitude": -6.0}
    )
    feature = task(site_id=site.pk)
    assert feature is not None
    site.refresh_from_db()
    assert site.latitude == -6.0


@pytest.mark.django_db
def test_tasks_missing_object_returns_none() -> None:
    from apps.integrations.tasks import geocode_site, summarize_site_report

    assert summarize_site_report(report_id=999999) is None
    assert geocode_site(site_id=999999) is None


# --------------------------------------------------------------------------- #
# Key reachability — env and constance (admin Integration settings)
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
def test_deepseek_enabled_with_env_key_only() -> None:
    with override_settings(DEEPSEEK_ENABLED=False, DEEPSEEK_API_KEY="env-key"):
        assert deepseek.enabled() is True


@pytest.mark.django_db
def test_deepseek_enabled_with_constance_key_only() -> None:
    with override_settings(DEEPSEEK_ENABLED=False, DEEPSEEK_API_KEY=""):
        from constance.test import override_config

        with override_config(DEEPSEEK_API_KEY="constance-key"):
            assert deepseek.enabled() is True


@pytest.mark.django_db
def test_deepseek_disabled_when_no_key_anywhere() -> None:
    with override_settings(DEEPSEEK_ENABLED=True, DEEPSEEK_API_KEY=""):
        from constance.test import override_config

        with override_config(DEEPSEEK_API_KEY=""):
            assert deepseek.enabled() is False


@pytest.mark.django_db
def test_mapbox_enabled_from_public_token() -> None:
    with override_settings(MAPBOX_ENABLED=False, MAPBOX_API_KEY="", MAPBOX_PUBLIC_TOKEN="pk.token"):
        assert mapbox.enabled() is True


@pytest.mark.django_db
def test_mapbox_enabled_from_constance_public_token() -> None:
    with override_settings(MAPBOX_ENABLED=False, MAPBOX_API_KEY="", MAPBOX_PUBLIC_TOKEN=""):
        from constance.test import override_config

        with override_config(MAPBOX_PUBLIC_TOKEN="pk.constance"):
            assert mapbox.enabled() is True
            assert mapbox._api_key() == "pk.constance"


@pytest.mark.django_db
def test_mapbox_disabled_when_no_token() -> None:
    with override_settings(MAPBOX_ENABLED=True, MAPBOX_API_KEY="", MAPBOX_PUBLIC_TOKEN=""):
        from constance.test import override_config

        with override_config(MAPBOX_PUBLIC_TOKEN=""):
            assert mapbox.enabled() is False


@override_settings(DEEPSEEK_ENABLED=True, DEEPSEEK_API_KEY="x")
def test_summarize_site_report_gracefully_returns_none_on_error(monkeypatch, site) -> None:
    from apps.integrations.services import summarize_site_report
    from apps.integrations.transport import ProviderError
    from apps.site_management.reporting_services import generate_site_report

    def boom(text, instruction=""):
        raise ProviderError("DeepSeek", "boom")

    monkeypatch.setattr(deepseek, "summarize", boom)
    report = generate_site_report(site_id=site.pk, day=datetime.date.today(), user=UserFactory())
    assert summarize_site_report(report) is None


@override_settings(MAPBOX_ENABLED=False)
def test_geocode_site_disabled_returns_none(site) -> None:
    from apps.integrations.services import geocode_site

    assert geocode_site(site) is None


@override_settings(MAPBOX_API_KEY="pk.env_mapbox", MAPBOX_PUBLIC_TOKEN="", DEEPSEEK_API_KEY="sk-env")
@pytest.mark.django_db
def test_integration_settings_endpoint_reads_env_token(admin_user) -> None:
    from apps.site_management.api import _mapbox_token

    assert _mapbox_token() == "pk.env_mapbox"
    client = _authed(admin_user)
    response = client.get("/api/site-management/v1/integrations/settings")
    assert response.status_code == 200
    body = response.json()
    assert body["mapbox_public_token"] == "pk.env_mapbox"
    assert body["deepseek_configured"] is True
    assert body["deepseek_key_suffix"] == "-env"


@override_settings(MAPBOX_API_KEY="", MAPBOX_PUBLIC_TOKEN="pk.pub", DEEPSEEK_API_KEY="")
@pytest.mark.django_db
def test_integration_settings_prefers_public_token(admin_user) -> None:
    from apps.site_management.api import _mapbox_token

    assert _mapbox_token() == "pk.pub"
