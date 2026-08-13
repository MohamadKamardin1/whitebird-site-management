"""Domain error contract.

Services and policies raise these; the API layer maps them to the standard
error envelope ``{"error": {"code", "message", "trace_id", "fields"}}``.
"""

from __future__ import annotations

from typing import Any


class DomainError(Exception):
    """Base class for all domain-level errors."""

    status_code: int = 400
    code: str = "domain_error"

    def __init__(self, message: str, *, fields: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.fields = fields or {}


class ConflictError(DomainError):
    """The operation conflicts with the current state of a resource."""

    status_code = 409
    code = "conflict"


class NotFoundError(DomainError):
    """The requested resource does not exist."""

    status_code = 404
    code = "not_found"


class ForbiddenActionError(DomainError):
    """The actor is authenticated but not permitted to perform the action."""

    status_code = 403
    code = "forbidden"


class BusinessRuleError(DomainError):
    """A business rule was violated.

    Defaults to HTTP 400; raise with a custom status where a 409 is more
    appropriate for the rule being enforced.
    """

    status_code = 400
    code = "business_rule"

    def __init__(self, message: str, *, status_code: int = 400, fields: dict[str, Any] | None = None) -> None:
        super().__init__(message, fields=fields)
        self.status_code = status_code
