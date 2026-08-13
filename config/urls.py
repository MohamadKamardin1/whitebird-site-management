"""URL routing. Public endpoints are versioned behind ``/api/v1``."""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from config.api import api

api_urls, api_app_name, _ = api.urls

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include((api_urls, api_app_name), namespace="api")),
]

if settings.DEBUG:
    urlpatterns.extend(static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT))  # type: ignore[arg-type]
