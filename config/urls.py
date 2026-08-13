"""Root URL configuration.

Public surface: operational probes, the API under ``/api/site-management/v1``,
and the Django admin. The host-facing ``web`` app owns the root routes.
"""

from django.conf import settings
from django.contrib import admin
from django.urls import include, path

from config.api import api

api_urls, api_app_name, _ = api.urls

urlpatterns = [
    path("", include("apps.web.urls")),
    path("admin/", admin.site.urls),
    # Session auth views: login/logout + password reset/change foundation.
    path("accounts/", include("django.contrib.auth.urls")),
    path(settings.API_V1_PREFIX + "/", include((api_urls, api_app_name), namespace="api")),
]

if settings.DEBUG and "debug_toolbar" in settings.INSTALLED_APPS:
    import debug_toolbar

    urlpatterns.append(path("__debug__/", include(debug_toolbar.urls)))
