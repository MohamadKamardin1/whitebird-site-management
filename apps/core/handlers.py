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
