"""
ASGI config for the White Bird platform.

Exposes ``application`` — the ASGI callable used by Uvicorn/Daphne when an
async server is required.
"""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

application = get_asgi_application()
