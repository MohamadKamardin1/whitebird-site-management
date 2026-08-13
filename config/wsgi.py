"""
WSGI config for the White Bird platform.

Exposes ``application`` — the WSGI callable used by Gunicorn and the
WhiteNoise static-file middleware.
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

application = get_wsgi_application()
