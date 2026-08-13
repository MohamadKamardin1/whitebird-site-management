"""Central Django Ninja API definition.

Every versioned router is mounted here; the single ``api`` object exposes the
generated OpenAPI schema at ``/api/v1/openapi.json`` and interactive docs at
``/api/v1/docs``.
"""

from ninja import NinjaAPI

from apps.accounts.api import router as accounts_router
from apps.accounts.auth import ApiTokenAuth
from apps.common.api import router as common_router
from apps.sites.api import router as sites_router

api = NinjaAPI(
    title="White Bird Zanzibar — Site Management API",
    version="1.0.0",
    description=(
        "Internal platform API for managing sites, departments, assets, staff "
        "assignments, notifications and operational statistics. All endpoints "
        "except login/health require a bearer API token."
    ),
    auth=ApiTokenAuth(),
    urls_namespace="api",
    docs_url="/docs",
    openapi_url="/openapi.json",
)

api.add_router("/auth", accounts_router)
api.add_router("", sites_router)
api.add_router("", common_router)
