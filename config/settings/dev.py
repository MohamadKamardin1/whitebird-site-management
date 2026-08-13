"""Development settings — relaxed security, extra tooling, verbose output.

Selected via ``DJANGO_SETTINGS_MODULE=config.settings.dev``.
"""

from .base import *  # noqa: F403

DEBUG = True

ALLOWED_HOSTS = ["localhost", "127.0.0.1", "*"]
INTERNAL_IPS = ["127.0.0.1", "localhost"]

CSRF_COOKIE_SECURE = False
SESSION_COOKIE_SECURE = False
SECURE_SSL_REDIRECT = False

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

INSTALLED_APPS += ["django_extensions", "debug_toolbar"]  # noqa: F405

# Debug Toolbar must sit early in the middleware chain to capture queries.
MIDDLEWARE.insert(0, "debug_toolbar.middleware.DebugToolbarMiddleware")  # noqa: F405

# CORS: in development allow any local origin so the Vite dev server can call
# the API without a proxy.
CORS_ALLOW_ALL_ORIGINS = True

# Only Django runs the dev server; WhiteNoise static serving stays active.
WHITENOISE_AUTOREFRESH = True

# Credentials used only by the idempotent ``seed_sites`` command.
DEV_ADMIN_EMAIL = "admin@whitebird.local"
DEV_ADMIN_PASSWORD = "admin-password"
