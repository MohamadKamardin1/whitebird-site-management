"""Development settings — relaxed security, verbose output, full debug.

Selected via ``DJANGO_SETTINGS_MODULE=config.settings.dev``.
"""

from .base import *  # noqa: F403

DEBUG = True

INTERNAL_IPS = ["127.0.0.1", "localhost"]

# Relaxed for local tooling only — never use these values in production.
CSRF_COOKIE_SECURE = False
SESSION_COOKIE_SECURE = False
SECURE_SSL_REDIRECT = False

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# The sole superuser used by the seed command / local bootstrap.
DEV_ADMIN_EMAIL = "admin@whitebird.local"
DEV_ADMIN_PASSWORD = "admin-password"
