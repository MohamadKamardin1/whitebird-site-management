"""Central Django Ninja API definition.

The single ``api`` object mounts every versioned router and exposes the
generated OpenAPI schema and interactive docs. The prefix is
``/api/site-management/v1`` (see ``settings.API_V1_PREFIX``). All error
handlers implement the shared error envelope from ``apps.core.handlers``.
"""

from typing import Any

from django.conf import settings
from ninja import NinjaAPI

from apps.accounts.api import router as accounts_router
from apps.accounts.auth import TokenAuth
from apps.core.api import router as core_router
from apps.core.handlers import register_error_handlers
from apps.site_management.api import router as site_management_router

_TAG_BY_SEGMENT = {
    "zones": "Zones",
    "sites": "Sites",
    "shifts": "Site Configuration",
    "areas": "Site Configuration",
    "operational-roles": "Site Configuration",
    "catalog": "Site Configuration",
    "cleaners": "Cleaners",
    "assignments": "Assignments",
    "schedules": "Assignments",
    "attendance": "Attendance",
    "trainees": "Trainees",
    "stores": "Stores",
    "inspection-templates": "Inspections",
    "inspections": "Inspections",
    "issues": "Issues & Jobs",
    "jobs": "Issues & Jobs",
    "reports": "Reports",
    "notifications": "Notifications",
    "theme": "Theme",
    "stats": "Dashboard",
    "auth": "Auth",
}


def _tag_for_path(path: str) -> str:
    segment = path.lstrip("/").split("/")[0]
    return _TAG_BY_SEGMENT.get(segment, "Site Management")


def _apply_domain_tags(router: Any) -> None:
    """Group every operation under a domain tag based on its URL path.

    Runs once at import time so the generated OpenAPI document (and Swagger
    UI) groups endpoints cleanly by domain. Operations that already declare a
    ``tags`` kwarg keep it.
    """
    for view in router.path_operations.values():
        tag = _tag_for_path(view.operations[0].path if view.operations else "")
        for operation in view.operations:
            if not operation.tags:
                operation.tags = [tag]


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
    docs_url="/docs" if settings.API_DOCS_ENABLED else None,
    openapi_url="/openapi.json" if settings.API_DOCS_ENABLED else None,
)

register_error_handlers(api)

api.add_router("/auth", accounts_router)
api.add_router("", site_management_router)
api.add_router("", core_router)

_apply_domain_tags(accounts_router)
_apply_domain_tags(site_management_router)
_apply_domain_tags(core_router)
