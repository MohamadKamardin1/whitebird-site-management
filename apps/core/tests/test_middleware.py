"""Tests for the request-id middleware."""

import pytest
from django.test import Client

from apps.core.context import current_request_id, request_id_var


@pytest.mark.django_db
def test_echoes_incoming_request_id(anon_client: Client) -> None:
    response = anon_client.get("/healthz", HTTP_X_REQUEST_ID="client-provided-id")
    assert response["X-Request-ID"] == "client-provided-id"


@pytest.mark.django_db
def test_generates_request_id_when_absent(anon_client: Client) -> None:
    response = anon_client.get("/healthz")
    request_id = response["X-Request-ID"]
    assert request_id
    assert len(request_id) == 32  # uuid4 hex


@pytest.mark.django_db
def test_request_id_available_in_view_context() -> None:
    from django.http import HttpResponse
    from django.test import RequestFactory

    from apps.core.context import current_request_id
    from apps.core.middleware import RequestIdMiddleware

    captured: list[str] = []

    def view(request):
        captured.append(current_request_id())
        return HttpResponse("ok")

    request = RequestFactory().get("/x", HTTP_X_REQUEST_ID="ctx-id")
    response = RequestIdMiddleware(lambda req: view(req))(request)
    assert response["X-Request-ID"] == "ctx-id"
    assert captured == ["ctx-id"]


@pytest.mark.django_db
def test_contextvar_reset_after_request() -> None:
    from django.http import HttpResponse
    from django.test import RequestFactory

    from apps.core.middleware import RequestIdMiddleware

    request = RequestFactory().get("/x", HTTP_X_REQUEST_ID="one")
    RequestIdMiddleware(lambda req: HttpResponse("ok"))(request)
    assert current_request_id() == ""
    assert request_id_var.get() == ""
