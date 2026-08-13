"""Test settings — isolated fast database, eager Celery, no external services.

Selected via ``DJANGO_SETTINGS_MODULE=config.settings.test`` (pytest sets this).
"""

from .base import *  # noqa: F403

DEBUG = False

# Fast in-memory SQLite keeps the suite hermetic and dependency-free.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

# Inline Redis so the suite never requires a running broker.
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "whitebird-test-cache",
    }
}

CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
CELERY_BROKER_URL = "memory://"

EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

DEV_ADMIN_EMAIL = "admin@whitebird.test"
DEV_ADMIN_PASSWORD = "admin-password"

SITE_STATS_SCHEDULE_SECONDS = 900
