"""Production settings — locked-down posture for live deployment.

Selected via ``DJANGO_SETTINGS_MODULE=config.settings.prod``. Refuses to boot
without the non-negotiable secrets.
"""

from .base import *  # noqa: F403
from .base import env

DEBUG = False

SECRET_KEY = env.str("DJANGO_SECRET_KEY", default=None)
if not SECRET_KEY:
    raise RuntimeError("DJANGO_SECRET_KEY is required in production.")

ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=[])
if not ALLOWED_HOSTS:
    raise RuntimeError("DJANGO_ALLOWED_HOSTS is required in production.")

CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])
if not CSRF_TRUSTED_ORIGINS:
    raise RuntimeError("CSRF_TRUSTED_ORIGINS is required in production.")

SECURE_SSL_REDIRECT = env.bool("DJANGO_SECURE_SSL_REDIRECT", default=True)
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = env.int("DJANGO_HSTS_SECONDS", default=31536000)
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True

EMAIL_BACKEND = env.str("EMAIL_BACKEND", default="django.core.mail.backends.smtp.EmailBackend")
EMAIL_HOST = env.str("EMAIL_HOST", default="")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_HOST_USER = env.str("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env.str("EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)
DEFAULT_FROM_EMAIL = env.str("DEFAULT_FROM_EMAIL", default="noreply@whitebird.co.tz")
SERVER_EMAIL = DEFAULT_FROM_EMAIL

ADMINS = [tuple(entry.split(":", 1)) for entry in env.list("DJANGO_ADMINS", default=[]) if ":" in entry]

# Whitenoise serves immutable compressed assets; keep the browser cache long.
WHITENOISE_MAX_AGE = env.int("WHITENOISE_MAX_AGE", default=31536000)

# --------------------------------------------------------------------------- #
# Extra hardening for live deployments
# --------------------------------------------------------------------------- #

# API docs/OpenAPI are off in production unless explicitly enabled.
API_DOCS_ENABLED = env.bool("API_DOCS_ENABLED", default=False)

# Trust X-Forwarded-Proto from the reverse proxy so SSL redirect works.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

SECURE_REFERRER_POLICY = env.str("SECURE_REFERRER_POLICY", default="strict-origin-when-cross-origin")

# Content-Security-Policy via SecurityHeadersMiddleware.
CSP_ENABLED = env.bool("CSP_ENABLED", default=True)
CSP_DEFAULT_SRC = env.list("CSP_DEFAULT_SRC", default=["'self'"])
CSP_SCRIPT_SRC = env.list("CSP_SCRIPT_SRC", default=["'self'", "https://cdn.jsdelivr.net"])
CSP_STYLE_SRC = env.list("CSP_STYLE_SRC", default=["'self'", "'unsafe-inline'"])
CSP_IMG_SRC = env.list("CSP_IMG_SRC", default=["'self'", "data:"])

MIDDLEWARE += ["apps.core.middleware.SecurityHeadersMiddleware"]  # noqa: F405

# Optional Sentry error tracking — enabled only when SENTRY_DSN is set.
SENTRY_DSN = env.str("SENTRY_DSN", default="")
if SENTRY_DSN:
    import sentry_sdk
    from sentry_sdk.integrations.celery import CeleryIntegration
    from sentry_sdk.integrations.django import DjangoIntegration

    sentry_sdk.init(
        dsn=SENTRY_DSN,
        environment=env.str("SENTRY_ENVIRONMENT", default="production"),
        traces_sample_rate=env.float("SENTRY_TRACES_SAMPLE_RATE", default=0.1),
        send_default_pii=False,
        integrations=[DjangoIntegration(), CeleryIntegration()],
    )
