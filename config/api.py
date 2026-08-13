"""Central Django Ninja API definition.

The single ``api`` object mounts every versioned router and exposes the
generated OpenAPI schema and interactive docs. The prefix is
``/api/site-management/v1`` (see ``settings.API_V1_PREFIX``).
"""

from django.core.exceptions import ValidationError as DjangoValidationError
from ninja import NinjaAPI

from apps.accounts.api import router as accounts_router
from apps.accounts.auth import TokenAuth
from apps.core.api import router as core_router
from apps.site_management.api import router as site_management_router

api = NinjaAPI(
    title="White Bird Zanzibar — Site Management API",
    version="1.0.0",
    description=(
        "Internal platform API for managing sites, departments, assets, staff "
        "assignments, notifications and operational statistics. All endpoints "
        "except login/refresh/logout/health require a bearer token."
    ),
    auth=TokenAuth(),
    urls_namespace="api",
    docs_url="/docs",
    openapi_url="/openapi.json",
)

api.add_router("/auth", accounts_router)
api.add_router("", site_management_router)
api.add_router("", core_router)


@api.exception_handler(DjangoValidationError)
def handle_django_validation_error(request, exc):  # type: ignore[no-untyped-def]
    """Map Django ``ValidationError`` to HTTP 422 with a readable payload."""
    message = exc.messages[0] if exc.messages else "Invalid input."
    return api.create_response(request, {"detail": message}, status=422)
