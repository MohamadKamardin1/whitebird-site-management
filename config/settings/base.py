"""Base settings shared by every deployment profile.

Environment variables are read through ``django-environ``. Defaults are
development-friendly but safe; production and test profiles tighten them.
"""

from datetime import timedelta
from pathlib import Path

import environ

from config.logging import RequestIdFilter, StructuredFormatter

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env(
    DEBUG=(bool, False),
    ALLOWED_HOSTS=(list, ["localhost", "127.0.0.1"]),
    CSRF_TRUSTED_ORIGINS=(list, []),
    CORS_ALLOWED_ORIGINS=(list, []),
    TIME_ZONE=(str, "Africa/Dar_es_Salaam"),
    LANGUAGE_CODE=(str, "en-us"),
    AUTH_MECHANISM=(str, "session"),
)

# --------------------------------------------------------------------------- #
# Django core
# --------------------------------------------------------------------------- #

environ.Env.read_env(BASE_DIR / ".env")

DEBUG = env.bool("DJANGO_DEBUG")
SECRET_KEY = env.str("DJANGO_SECRET_KEY", default="django-insecure-dev-only-change-me")

ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_USER_MODEL = "accounts.User"

TIME_ZONE = env("TIME_ZONE")
USE_I18N = True
USE_TZ = True
LANGUAGE_CODE = env("LANGUAGE_CODE")

# --------------------------------------------------------------------------- #
# Applications
# --------------------------------------------------------------------------- #

INSTALLED_APPS = [
    # Django
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third-party (Jazzmin must precede admin to restyle it)
    "jazzmin",
    "constance",
    "constance.backends.database",
    "corsheaders",
    "whitenoise.runserver_nostatic",
    "ninja",
    "django_celery_beat",
    "axes",
    "django.contrib.humanize",
    "widget_tweaks",
    # Local
    "apps.core",
    "apps.accounts",
    "apps.site_management",
    "apps.web",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "apps.core.middleware.RequestIdMiddleware",
    "apps.core.throttling.ApiThrottleMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "axes.middleware.AxesMiddleware",
    "apps.accounts.middleware.UserTimezoneMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# Header that carries the caller-provided request id (e.g. X-Request-ID).
REQUEST_ID_HEADER = "HTTP_X_REQUEST_ID"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 12}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.core.context_processors.brand",
            ],
        },
    },
]

# --------------------------------------------------------------------------- #
# Databases, cache, redis
# --------------------------------------------------------------------------- #

DATABASES = {"default": env.db("DATABASE_URL", default="postgres://postgres:postgres@127.0.0.1:5432/whitebird")}
DATABASES["default"]["CONN_MAX_AGE"] = env.int("POSTGRES_CONN_MAX_AGE", default=60)
DATABASES["default"]["OPTIONS"] = {"connect_timeout": env.int("POSTGRES_CONNECT_TIMEOUT", default=10)}

REDIS_URL = env.str("REDIS_URL", default="redis://127.0.0.1:6379/0")

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": REDIS_URL,
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "CONNECTION_POOL_KWARGS": {"max_connections": env.int("REDIS_MAX_CONNECTIONS", default=50)},
        },
        "TIMEOUT": env.int("CACHE_DEFAULT_TIMEOUT", default=300),
        "KEY_PREFIX": env.str("CACHE_KEY_PREFIX", default="whitebird"),
    }
}

# --------------------------------------------------------------------------- #
# Celery
# --------------------------------------------------------------------------- #

CELERY_BROKER_URL = env.str("CELERY_BROKER_URL", default=REDIS_URL)
CELERY_RESULT_BACKEND = env.str("CELERY_RESULT_BACKEND", default=REDIS_URL)
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = env.int("CELERY_TASK_TIME_LIMIT", default=300)
CELERY_TASK_SOFT_TIME_LIMIT = env.int("CELERY_TASK_SOFT_TIME_LIMIT", default=270)
CELERY_TASK_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_RESULT_SERIALIZER = "json"
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"

# Cadence for the periodic site-statistics refresh (seconds).
SITE_STATS_SCHEDULE_SECONDS = env.int("SITE_STATS_SCHEDULE_SECONDS", default=900)

# --------------------------------------------------------------------------- #
# Runtime configuration (django-constance) — editable from the admin
# --------------------------------------------------------------------------- #

CONSTANCE_BACKEND = "constance.backends.database.DatabaseBackend"
CONSTANCE_DATABASE_CACHE_BACKEND = "default"

CONSTANCE_CONFIG = {
    "BRAND_NAME": ("White Bird Zanzibar", "Platform display name."),
    "BRAND_PRIMARY_COLOR": ("#9c7c38", "Primary brand colour (hex)."),
    "BRAND_ACCENT_COLOR": ("#c9a96e", "Accent brand colour (hex)."),
    "BRAND_BACKGROUND_COLOR": ("#f7f3ea", "Dashboard background colour (hex)."),
    "MAX_SITE_SUPERVISORS_PER_SITE": (2, "Maximum supervisor assignments per site."),
    "MAX_UPLOAD_MB": (10, "Maximum upload size in megabytes."),
    "MIN_CLEANER_AGE": (18, "Minimum legal age for a registered cleaner."),
    "ATTENDANCE_LOCK_AFTER_DAYS": (7, "Days after review before attendance auto-locks."),
    "DEFAULT_PAGE_SIZE": (25, "Default API page size."),
    "MAX_PAGE_SIZE": (100, "Maximum allowed API page size."),
    "DASHBOARD_CACHE_TTL": (300, "Dashboard aggregate cache lifetime (seconds)."),
    "REPORT_CACHE_TTL": (600, "Report cache lifetime (seconds)."),
    "FILE_TOKEN_TTL_SECONDS": (900, "Signed file token lifetime (seconds)."),
    "LOW_STOCK_DEFAULT": (5, "Default low-stock threshold for the site store."),
    "ALLOW_NEGATIVE_STOCK": (False, "Explicit override allowing negative stock levels in the site store."),
    "JOB_COMPLETION_PHOTO_REQUIRED": (False, "Require photo evidence to complete a job."),
    "ENABLE_DOMAIN_EVENTS": (False, "Emit domain events to the event bus."),
    "ENABLE_NOTIFICATIONS": (True, "Deliver in-platform notifications."),
}

# --------------------------------------------------------------------------- #
# API (Django Ninja)
# --------------------------------------------------------------------------- #

API_V1_PREFIX = "api/site-management/v1"
API_VERSION = env.str("API_VERSION", default="1.0.0")

NINJA_PAGINATION_CLASS = "ninja.pagination.LimitOffsetPagination"
NINJA_PAGINATION_PER_PAGE = env.int("API_PAGE_SIZE", default=25)
NINJA_PAGINATION_MAX_LIMIT = env.int("API_MAX_PAGE_SIZE", default=100)

# Per-endpoint throttling rates (Django Ninja throttling), read from env.
API_THROTTLE_ANON_RATE = env.str("API_THROTTLE_ANON_RATE", default="30/min")
API_THROTTLE_AUTH_RATE = env.str("API_THROTTLE_AUTH_RATE", default="300/min")
# Master switch for the fixed-window API rate limiter (apps.core.throttling).
API_THROTTLE_ENABLED = env.bool("API_THROTTLE_ENABLED", default=True)
# Dashboard KPI/chart cache TTL (seconds) — mirrors constance DASHBOARD_CACHE_TTL.
DASHBOARD_CACHE_TTL_SECONDS = env.int("DASHBOARD_CACHE_TTL_SECONDS", default=300)
# When false, the interactive docs (Swagger UI / OpenAPI JSON) return 404.
API_DOCS_ENABLED = env.bool("API_DOCS_ENABLED", default=True)

# --------------------------------------------------------------------------- #
# Authentication: session for admin/dashboard, signed access + refresh tokens
# for the API. The token backend is swappable for a JWT library later without
# changing the router contract (see apps/accounts/tokens.py).
# --------------------------------------------------------------------------- #

AUTH_MECHANISM = env("AUTH_MECHANISM")  # "session" | "jwt"
JWT_AUDIENCE = env.str("JWT_AUDIENCE", default="whitebird")
JWT_ISSUER = env.str("JWT_ISSUER", default="whitebird")
JWT_ACCESS_TOKEN_TTL = timedelta(seconds=env.int("JWT_ACCESS_TOKEN_TTL", default=900))
JWT_REFRESH_TOKEN_TTL = timedelta(days=env.int("JWT_REFRESH_TOKEN_TTL_DAYS", default=7))

# Signed access-token lifetime (seconds); refresh tokens use ApiToken expiry.
ACCESS_TOKEN_TTL_SECONDS = env.int("ACCESS_TOKEN_TTL_SECONDS", default=1800)
REFRESH_TOKEN_TTL_SECONDS = env.int("REFRESH_TOKEN_TTL_SECONDS", default=604800)

# django-axes brute-force protection for the login endpoint.
AXES_ENABLED = env.bool("AXES_ENABLED", default=True)
AXES_FAILURE_LIMIT = env.int("AXES_FAILURE_LIMIT", default=5)
AXES_COOLOFF_TIME = timedelta(hours=env.int("AXES_COOLOFF_TIME_HOURS", default=1))
AXES_LOCKOUT_PARAMETERS = [["username", "ip_address"]]
AXES_RESET_ON_SUCCESS = True
# Axes auto-derives this from USERNAME_FIELD ("email"); keep the credential key
# consistent with how the platform calls ``authenticate(username=...)``.
AXES_USERNAME_FORM_FIELD = "username"

AUTHENTICATION_BACKENDS = [
    "axes.backends.AxesStandaloneBackend",
    "django.contrib.auth.backends.ModelBackend",
]

# --------------------------------------------------------------------------- #
# Static & media storage
# --------------------------------------------------------------------------- #

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

# Private media: never served directly by WhiteNoise. Files uploaded through
# the platform live here and are delivered behind signed tokens.
PRIVATE_MEDIA_ROOT = BASE_DIR / "private_media"
MEDIA_ROOT = PRIVATE_MEDIA_ROOT
MEDIA_URL = "/media/"
PUBLIC_MEDIA_ROOT = BASE_DIR / "public_media"
PUBLIC_MEDIA_URL = "/public-media/"

# Upload policy for private files (defaults; runtime MAX_UPLOAD_MB via constance).
MAX_UPLOAD_MB = env.int("MAX_UPLOAD_MB", default=10)
ALLOWED_UPLOAD_EXTENSIONS = ["pdf", "jpg", "jpeg", "png", "webp"]
FILE_TOKEN_TTL_SECONDS = env.int("FILE_TOKEN_TTL_SECONDS", default=900)

# --------------------------------------------------------------------------- #
# Branding & dashboard (consumed by Jazzmin and future frontend)
# --------------------------------------------------------------------------- #

BRAND_NAME = "White Bird Zanzibar"
BRAND_PRIMARY_COLOR = "#9c7c38"
BRAND_ACCENT_COLOR = "#c9a96e"
BRAND_BACKGROUND_COLOR = "#f7f3ea"
DASHBOARD_CACHE_ALIAS = "default"

JAZZMIN_SETTINGS = {
    "site_title": BRAND_NAME,
    "site_header": BRAND_NAME,
    "site_brand": BRAND_NAME,
    "site_logo": "images/logo.svg",
    "site_logo_classes": "img-circle",
    "welcome_sign": "Welcome to the White Bird Zanzibar Management Platform",
    "copyright": f"{BRAND_NAME} · Ops Platform",
    "show_sidebar": True,
    "navigation_expanded": True,
    "hide_apps": [],
    "hide_models": [
        "auth.group",
        "sessions.session",
        "django_celery_beat.clockedschedule",
        "django_celery_beat.crontabschedule",
        "django_celery_beat.periodictasks",
        "django_celery_beat.solarschedule",
        "axes.accessattempt",
        "axes.accessfailurelog",
    ],
    "icons": {
        "auth": "fas fa-users-cog",
        "auth.user": "fas fa-user",
        "accounts": "fas fa-users-cog",
        "accounts.user": "fas fa-user",
        "accounts.apitoken": "fas fa-key",
        "site_management": "fas fa-umbrella-beach",
        "site_management.zone": "fas fa-map-marked-alt",
        "site_management.site": "fas fa-building",
        "site_management.sitetype": "fas fa-tags",
        "site_management.sitestatus": "fas fa-flag",
        "site_management.department": "fas fa-sitemap",
        "site_management.asset": "fas fa-box",
        "site_management.assetcategory": "fas fa-folder",
        "site_management.staffassignment": "fas fa-user-tag",
        "site_management.notification": "fas fa-bell",
        "site_management.siteshift": "fas fa-clock",
        "site_management.sitearea": "fas fa-th-large",
        "site_management.operationalrole": "fas fa-broom",
        "site_management.cleaner": "fas fa-user-tie",
        "site_management.cleanerdocument": "fas fa-id-card",
        "site_management.cleanersiteassignment": "fas fa-user-check",
        "site_management.cleanershiftassignment": "fas fa-calendar-alt",
        "site_management.cleanerareaschedule": "fas fa-tasks",
        "site_management.attendancerecord": "fas fa-clipboard-check",
        "site_management.traineeprogram": "fas fa-graduation-cap",
        "site_management.traineeevaluation": "fas fa-star-half-alt",
        "site_management.sitestore": "fas fa-warehouse",
        "site_management.storeitem": "fas fa-boxes",
        "site_management.stockmovement": "fas fa-exchange-alt",
        "site_management.stockrequest": "fas fa-shopping-cart",
        "site_management.stockrequestitem": "fas fa-list",
        "site_management.inspectiontemplate": "fas fa-clipboard-list",
        "site_management.inspection": "fas fa-search-plus",
        "site_management.inspectionresult": "fas fa-camera",
        "site_management.issue": "fas fa-exclamation-triangle",
        "site_management.job": "fas fa-wrench",
        "site_management.dailysitereport": "fas fa-file-alt",
        "site_management.zonesummaryreport": "fas fa-layer-group",
        "site_management.assistantgeneralsummaryreport": "fas fa-chart-line",
        "site_management.generalmanagementreport": "fas fa-landmark",
        "core": "fas fa-cogs",
        "core.auditlog": "fas fa-history",
        "core.domainevent": "fas fa-paper-plane",
        "constance": "fas fa-sliders-h",
        "django_celery_beat": "fas fa-clock",
        "django_celery_beat.periodictask": "fas fa-clock",
        "django_celery_beat.interval": "fas fa-stopwatch",
    },
    "order_with_respect_to": [
        "site_management",
        "site_management.Zone",
        "site_management.Site",
        "site_management.Cleaner",
        "site_management.CleanerSiteAssignment",
        "site_management.AttendanceRecord",
        "site_management.TraineeProgram",
        "site_management.SiteStore",
        "site_management.StockRequest",
        "site_management.InspectionTemplate",
        "site_management.Inspection",
        "site_management.Issue",
        "site_management.Job",
        "site_management.DailySiteReport",
        "site_management.ZoneSummaryReport",
        "site_management.AssistantGeneralSummaryReport",
        "site_management.GeneralManagementReport",
        "accounts",
        "accounts.User",
        "accounts.ApiToken",
        "core",
        "core.AuditLog",
        "core.DomainEvent",
        "constance",
        "django_celery_beat",
    ],
    "topmenu_links": [
        {"name": "Dashboard", "url": "admin:index", "icon": "fas fa-home"},
        {"name": "API Docs", "url": "/api/site-management/v1/docs", "icon": "fas fa-book-open"},
        {"name": "OpenAPI JSON", "url": "/api/site-management/v1/openapi.json", "icon": "fas fa-code"},
        {"name": "Settings", "model": "constance.config", "icon": "fas fa-sliders-h"},
    ],
    "custom_links": {
        "site_management": [
            {
                "name": "Zones",
                "url": "admin:site_management_zone_changelist",
                "icon": "fas fa-map-marked-alt",
                "permissions": [],
            },
            {
                "name": "Sites",
                "url": "admin:site_management_site_changelist",
                "icon": "fas fa-building",
                "permissions": [],
            },
            {
                "name": "Cleaners",
                "url": "admin:site_management_cleaner_changelist",
                "icon": "fas fa-user-tie",
                "permissions": [],
            },
            {
                "name": "Attendance",
                "url": "admin:site_management_attendancerecord_changelist",
                "icon": "fas fa-clipboard-check",
                "permissions": [],
            },
            {
                "name": "Trainees",
                "url": "admin:site_management_traineeprogram_changelist",
                "icon": "fas fa-graduation-cap",
                "permissions": [],
            },
            {
                "name": "Stores",
                "url": "admin:site_management_sitestore_changelist",
                "icon": "fas fa-warehouse",
                "permissions": [],
            },
            {
                "name": "Inspections",
                "url": "admin:site_management_inspection_changelist",
                "icon": "fas fa-search-plus",
                "permissions": [],
            },
            {
                "name": "Issues",
                "url": "admin:site_management_issue_changelist",
                "icon": "fas fa-exclamation-triangle",
                "permissions": [],
            },
            {"name": "Jobs", "url": "admin:site_management_job_changelist", "icon": "fas fa-wrench", "permissions": []},
            {
                "name": "Reports",
                "url": "admin:site_management_dailysitereport_changelist",
                "icon": "fas fa-file-alt",
                "permissions": [],
            },
        ],
        "core": [
            {
                "name": "Audit Logs",
                "url": "admin:core_auditlog_changelist",
                "icon": "fas fa-history",
                "permissions": [],
            },
        ],
        "accounts": [
            {"name": "Users", "url": "admin:accounts_user_changelist", "icon": "fas fa-user", "permissions": []},
        ],
    },
    "related_modal_active": False,
    "custom_css": "css/material_soft_gold.css",
    "custom_js": "js/whitebird_admin.js",
    "show_ui_builder": False,
    "changeform_format": "horizontal_tabs",
    "changeform_format_overrides": {
        "accounts.user": "collapsible",
        "site_management.cleaner": "collapsible",
        "site_management.inspection": "vertical_tabs",
    },
    "default_icon_parents": "fas fa-chevron-circle-right",
    "default_icon_children": "fas fa-circle",
}

JAZZMIN_UI_TWEAKS = {
    "navbar_small_text": False,
    "footer_small_text": False,
    "body_small_text": False,
    "brand_small_text": False,
    "brand_colour": "navbar-light",
    "accent": "accent-warning",
    "navbar": "navbar-white navbar-light",
    "no_navbar_border": False,
    "navbar_fixed": True,
    "layout_boxed": False,
    "footer_fixed": False,
    "sidebar_fixed": True,
    "sidebar": "sidebar-light-warning",
    "sidebar_nav_small_text": False,
    "sidebar_disable_expand": False,
    "sidebar_nav_child_indent": False,
    "sidebar_nav_compact_style": False,
    "sidebar_nav_legacy_style": False,
    "theme": "materia",
    "dark_mode_theme": None,
    "button_classes": {
        "primary": "btn-primary",
        "secondary": "btn-outline-secondary",
        "info": "btn-outline-info",
        "warning": "btn-outline-warning",
        "danger": "btn-danger",
        "success": "btn-success",
    },
}

# --------------------------------------------------------------------------- #
# CORS & CSRF
# --------------------------------------------------------------------------- #

CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=[])
CORS_ALLOW_CREDENTIALS = True
CORS_URLS_REGEX = r"^/api/.*$"

CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])

# --------------------------------------------------------------------------- #
# Security
# --------------------------------------------------------------------------- #

SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = "DENY"
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True

# --------------------------------------------------------------------------- #
# Logging
# --------------------------------------------------------------------------- #

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "structured": {"()": StructuredFormatter},
    },
    "filters": {
        "request_id": {"()": RequestIdFilter},
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "structured",
            "filters": ["request_id"],
        },
    },
    "root": {"handlers": ["console"], "level": env.str("LOG_LEVEL", default="INFO")},
    "loggers": {
        "django": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "django.request": {"handlers": ["console"], "level": "ERROR", "propagate": False},
        "apps": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "celery": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "axes": {"handlers": ["console"], "level": "INFO", "propagate": False},
    },
}
