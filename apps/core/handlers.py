"""Django Ninja exception handlers implementing the API error contract.

Every response uses the same envelope::

    {"error": {"code", "message", "trace_id", "fields"}}

``trace_id`` comes from the request-id contextvar set by
``RequestIdMiddleware``.
"""

from __future__ import annotations

import logging
from typing import Any

from django.core.exceptions import ObjectDoesNotExist, PermissionDenied
from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import Http404
from ninja import NinjaAPI
from ninja.errors import AuthenticationError, AuthorizationError, Throttled, ValidationError

from apps.integrations.transport import ProviderError

from .context import current_request_id
from .errors import DomainError

logger = logging.getLogger("apps.core")


def error_payload(code: str, message: str, fields: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "error": {
            "code": code,
            "message": message,
            "trace_id": current_request_id(),
            "fields": fields or {},
        }
    }


def _validation_fields(exc: DjangoValidationError) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    message_dict = getattr(exc, "message_dict", None)
    if message_dict:
        for field, errors in message_dict.items():
            fields[field] = [str(error) for error in errors]
    else:
        for error in getattr(exc, "error_list", []):
            key = getattr(error, "field", None) or "_"
            messages = getattr(error, "messages", None)
            if messages:
                fields.setdefault(key, []).extend(str(message) for message in messages)
            else:
                fields.setdefault(key, []).append(str(error))
    return fields


def register_error_handlers(api: NinjaAPI) -> None:
    """Register every error handler on the given Ninja API instance."""

    @api.exception_handler(DomainError)
    def handle_domain_error(request: Any, exc: DomainError) -> Any:
        return api.create_response(
            request,
            error_payload(exc.code, exc.message, exc.fields),
            status=exc.status_code,
        )

    @api.exception_handler(DjangoValidationError)
    def handle_validation_error(request: Any, exc: DjangoValidationError) -> Any:
        message = exc.messages[0] if exc.messages else "Validation failed."
        return api.create_response(
            request,
            error_payload("validation_error", str(message), _validation_fields(exc)),
            status=422,
        )

    @api.exception_handler(AuthenticationError)
    def handle_authentication_error(request: Any, exc: AuthenticationError) -> Any:
        return api.create_response(
            request,
            error_payload("unauthorized", str(exc) or "Unauthorized."),
            status=401,
        )

    @api.exception_handler(ValidationError)
    def handle_request_validation_error(request: Any, exc: ValidationError) -> Any:
        fields: dict[str, Any] = {}
        for error in exc.errors:
            key = ".".join(str(part) for part in error.get("loc", [])) or "_"
            fields.setdefault(key, []).append(str(error.get("msg", "Invalid value.")))
        message = next(iter(fields.values()), ["Validation failed."])[0]
        return api.create_response(
            request,
            error_payload("validation_error", str(message), fields),
            status=422,
        )

    @api.exception_handler(AuthorizationError)
    def handle_authorization_error(request: Any, exc: AuthorizationError) -> Any:
        return api.create_response(
            request,
            error_payload("forbidden", str(exc) or "Forbidden."),
            status=403,
        )

    @api.exception_handler(Throttled)
    def handle_throttled(request: Any, exc: Throttled) -> Any:
        return api.create_response(
            request,
            error_payload("rate_limited", str(exc) or "Too many requests."),
            status=429,
        )

    @api.exception_handler(ProviderError)
    def handle_provider_error(request: Any, exc: ProviderError) -> Any:
        return api.create_response(
            request,
            error_payload(f"{exc.provider.lower()}_error", exc.message),
            status=exc.status_code,
        )

    @api.exception_handler(ObjectDoesNotExist)
    def handle_object_not_found(request: Any, exc: ObjectDoesNotExist) -> Any:
        return api.create_response(
            request,
            error_payload("not_found", "The requested resource does not exist."),
            status=404,
        )

    @api.exception_handler(Http404)
    def handle_http404(request: Any, exc: Http404) -> Any:
        return api.create_response(
            request,
            error_payload("not_found", str(exc) or "Not found."),
            status=404,
        )

    @api.exception_handler(PermissionDenied)
    def handle_permission_denied(request: Any, exc: PermissionDenied) -> Any:
        return api.create_response(
            request,
            error_payload("forbidden", str(exc) or "Forbidden."),
            status=403,
        )

    @api.exception_handler(Exception)
    def handle_unexpected(request: Any, exc: Exception) -> Any:
        logger.exception("Unhandled exception: %s", exc)
        return api.create_response(
            request,
            error_payload("internal_error", "Internal server error."),
            status=500,
        )
