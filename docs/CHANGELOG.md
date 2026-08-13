# Changelog

All notable changes to the White Bird Zanzibar — Site Management Module.

The format follows [Keep a Changelog](https://keepachangelog.com/); versions
map to build prompts.

## [Prompt 02] — 2026-08-13

### Added

- **Custom user model** (`accounts.User`): email as the unique login
  identifier (case-insensitive, stored lowercased), validated Tanzania/E.164
  phone, IANA timezone (default `Africa/Dar_es_Salaam`), optional avatar,
  `full_name`, `created_at`/`updated_at`, `last_login`, and a custom
  `UserManager` (`create_user`/`create_superuser`).
- **Role system**: `RoleCode` enum (`system_admin`, `general_supervisor`,
  `assistant_general_supervisor`, `zone_supervisor`, `site_supervisor`,
  `management_viewer`) with helper methods on `User`.
- **RBAC foundation**: Django groups per role, model + custom permissions
  (site reports, job assignment/verification, trainee approval, exports, …),
  declarative matrix (`apps/accounts/rbac.py`), idempotent `seed_rbac`
  command, and a `post_save` signal that keeps user group membership in sync.
- **Authentication**: signed (HMAC) access tokens + revocable server-side
  refresh tokens; `TokenAuth` bearer scheme; API endpoints
  `login`, `refresh`, `logout`, `me`, `password-change`; django-axes
  lockout; password validators (min length 12, common, numeric, similarity).
- **Session auth foundation**: Django auth views mounted at `/accounts/`
  (login/logout, password change, password reset) with functional templates.
- **User admin**: role/active filters, activate/deactivate actions, deletion
  guard for users with operational history, readonly audit fields.
- **`UserTimezoneMiddleware`** activating the authenticated user's timezone.
- **Factories** for users in every role and active/inactive states.

### Changed

- Replaced the prompt-1 `Role` (`admin/manager/staff/viewer`) with the
  professional `RoleCode` set; site management, seed command, core API and
  tests updated accordingly.
- `UserAdmin` and admin login now use email.
- API auth now prefers stateless access tokens, falling back to long-lived
  `ApiToken` keys.
- `.env.example` gains `ACCESS_TOKEN_TTL_SECONDS` and
  `REFRESH_TOKEN_TTL_SECONDS`.

### Fixed

- django-axes recorded failed logins with `username=None` because it derived
  `AXES_USERNAME_FORM_FIELD="email"` from `USERNAME_FIELD`; pinned to
  `"username"` so lockout matches `authenticate(username=...)`.
- Django `ValidationError` in `accounts` services propagates as HTTP 422
  via the global API handler.
- `password_reset_email.html` apostrophe template error.

## [Prompt 01] — 2026-08-13

### Added

- Split settings profile (`base` / `dev` / `test` / `prod`) powered by
  `django-environ`.
- Custom `accounts.User` with platform roles; `ApiToken` bearer authentication;
  django-axes brute-force protection.
- Django Ninja API at `/api/site-management/v1` with OpenAPI/Swagger docs,
  a Django `ValidationError → 422` handler, and versioned routers.
- Celery application (`config/celery_app.py`) with `django-celery-beat`
  database scheduler and an idempotently-registered periodic stats task.
- Redis-backed cache (`django-redis`), WhiteNoise static compression, private
  media root, CORS/CSRF from environment, structured JSON console logging.
- Jazzmin admin with branding plus `django-constance` runtime configuration
  (branding colours, page sizes, cache TTLs, thresholds, feature flags).
- Host probes `/healthz` and `/readyz`, landing redirect to `/admin/`.
- `apps.core` (audit log, soft-delete, cache helpers, typed request),
  `apps.web` (probes), and the carried-forward `apps.site_management`.
- Docker foundation: `Dockerfile` (python:3.12-slim, non-root),
  `docker-compose.yml` (db/redis/web), entrypoint + wait-for-db.
- Tooling: `Makefile`, `.pre-commit-config.yaml`, split `requirements/`.
- Test foundation: factory-boy factories, 96 tests at ~95% branch coverage.
- Documentation set: contract, architecture, domain, RBAC, API, theme,
  testing, performance, assumptions, state, changelog.

### Fixed

- Django `ValidationError` now maps to HTTP 422 instead of a 500.
- Axes-compatible login: `authenticate(request=...)` forwarded from the API.
