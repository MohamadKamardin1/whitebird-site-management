"""Test settings — hermetic and deterministic.

Selected by pytest via ``DJANGO_SETTINGS_MODULE=config.settings.test``.
No external services are required: SQLite in-memory, local-memory cache,
eager Celery.
"""

import tempfile
from pathlib import Path

from .base import *  # noqa: F403

DEBUG = False
SECRET_KEY = "test-secret-key-not-for-production"
ALLOWED_HOSTS = ["testserver", "localhost", "127.0.0.1"]

# Fast in-memory SQLite keeps the suite hermetic and fast.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

# Inline local-memory cache so the suite never needs a running Redis.
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "whitebird-test-cache",
    }
}

# Run tasks synchronously and surface their errors immediately.
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
CELERY_BROKER_URL = "memory://"
CELERY_RESULT_BACKEND = "cache+memory://"

# Never attempt outbound mail or brute-force protection.
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
AXES_ENABLED = False

# Constance uses a cross-process cache for the database backend; the test
# cache is local-memory, so disable constance's value cache.
CONSTANCE_DATABASE_CACHE_BACKEND = None  # type: ignore[assignment]

# Fast password hashing keeps the auth tests quick.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# Speed up admin/media rendering in tests and silence WhiteNoise startup noise.
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
WHITENOISE_AUTOREFRESH = False
WHITENOISE_USE_FINDERS = False

DEBUG_TOOLBAR_CONFIG = {"SHOW_TOOLBAR_CALLBACK": lambda request: False}

# Private uploads go to a per-session temp dir, cleaned by the test fixtures.
_MEDIA_TMP = Path(tempfile.mkdtemp(prefix="whitebird-test-media-"))
PRIVATE_MEDIA_ROOT = _MEDIA_TMP
MEDIA_ROOT = _MEDIA_TMP
PUBLIC_MEDIA_ROOT = _MEDIA_TMP / "public"

DEV_ADMIN_EMAIL = "admin@whitebird.test"
DEV_ADMIN_PASSWORD = "admin-password"
