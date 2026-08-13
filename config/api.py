"""Central Django Ninja API definition.

The single ``api`` object mounts every versioned router and exposes the
generated OpenAPI schema and interactive docs. The prefix is
``/api/site-management/v1`` (see ``settings.API_V1_PREFIX``). All error
handlers implement the shared error envelope from ``apps.core.handlers``.
"""

from ninja import NinjaAPI

from apps.accounts.api import router as accounts_router
from apps.accounts.auth import TokenAuth
from apps.core.api import router as core_router
from apps.core.handlers import register_error_handlers
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

register_error_handlers(api)

api.add_router("/auth", accounts_router)
api.add_router("", site_management_router)
api.add_router("", core_router)
