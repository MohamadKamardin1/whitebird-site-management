"""Tests for the host-facing views: probes and landing redirect."""

import pytest
from django.test import Client


@pytest.mark.django_db
def test_healthz_returns_ok(anon_client: Client) -> None:
    response = anon_client.get("/healthz")
    assert response.status_code == 200
    assert response.content == b"OK"


@pytest.mark.django_db
def test_readyz_returns_ok_when_dependencies_healthy(anon_client: Client) -> None:
    response = anon_client.get("/readyz")
    assert response.status_code == 200
    assert response.content == b"OK"


@pytest.mark.django_db
def test_readyz_returns_503_when_cache_fails(anon_client: Client, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("apps.web.views.cache.get", lambda key, **kwargs: None)
    response = anon_client.get("/readyz")
    assert response.status_code == 503
    assert response.content == b"NOT READY"


@pytest.mark.django_db
def test_readyz_returns_503_when_database_fails(anon_client: Client, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("apps.web.views.connection", _BrokenConnection())
    response = anon_client.get("/readyz")
    assert response.status_code == 503
    assert response.content == b"NOT READY"


@pytest.mark.django_db
def test_landing_redirects_to_admin(anon_client: Client) -> None:
    response = anon_client.get("/")
    assert response.status_code == 302
    assert response.url == "/admin/"


def test_react_app_serves_collected_frontend_bundle(anon_client: Client, settings, tmp_path) -> None:
    settings.STATIC_ROOT = tmp_path
    bundle = tmp_path / "frontend"
    bundle.mkdir()
    (bundle / "index.html").write_text("<html><title>White Bird Zanzibar — Operations</title></html>")

    response = anon_client.get("/app/")

    assert response.status_code == 200
    assert b"White Bird Zanzibar" in b"".join(response.streaming_content)


class _BrokenConnection:
    """Stub that raises when the readiness probe tries to reach the DB."""

    def cursor(self):
        raise ConnectionError("database down")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False
