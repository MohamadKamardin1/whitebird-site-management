"""
ASGI config for the White Bird platform.

Exposes ``application`` — the ASGI callable used by Uvicorn/Daphne when an
async server is required.
"""

import os

from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

django_asgi_app = get_asgi_application()

from apps.site_management.realtime import AccessTokenAuthMiddleware  # noqa: E402
from apps.site_management.routing import websocket_urlpatterns  # noqa: E402

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": AccessTokenAuthMiddleware(URLRouter(websocket_urlpatterns)),
    }
)
