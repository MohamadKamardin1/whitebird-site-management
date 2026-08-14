# Changelog

All notable changes to the White Bird Zanzibar — Site Management Module.

The format follows [Keep a Changelog](https://keepachangelog.com/); versions
map to build prompts.

## [Prompt 05] — 2026-08-13

### Added

- **`SiteShift`**: manual per-site shift configuration (`shift_name`,
  `shift_code`, `start_time`, `end_time`, `effective_days`, `sequence`,
  `description`) with partial-unique active name/code constraints,
  `crosses_midnight` (overnight support), and deactivate-instead-of-delete.
- **`SiteArea`**: per-site areas (`area_name`, `area_code`, `floor`,
  `description`) unique per site; soft deactivation.
- **`OperationalRole`**: globally configurable operational roles with unique
  name/code and deactivation protection.
- **`SiteWorkingRule`**: per-site operational flags
  (`allowed_assignment_types`, `attendance_locked`,
  `require_shift_area_assignment`, `allow_temporary_transfers`).
- **Validation**: `validate_effective_days`, `validate_shift_time_logic`,
  `validate_site_work_mode`, `validate_shift_belongs_to_site`,
  `validate_area_belongs_to_site`, `validate_site_configuration_consistency`
  (incl. duplicate-shift detection).
- **Services** (transactional + audited): shift/area/role
  create/update/deactivate.
- **API**: shift, area, and operational-role list/create/update/status
  endpoints with role-scoped write permissions (SYSTEM_ADMIN /
  GENERAL_SUPERVISOR / `manage_site_configuration`).
- **Admin**: `SiteShift` and `SiteArea` inlines under Site; standalone
  `OperationalRole` admin with status badge, actions, and hard-delete guard.
- **Factories** for shifts, areas, roles, and working rules (tests).

## [Prompt 04] — 2026-08-13

### Added

- **`Zone` model**: name, unique `code`, description, soft-deactivate
  (`ActivatableModel` + `UserStampedModel`).
- **`Site` organisation fields**: `zone` FK, `building_name`, `location`,
  `contact_person`, `work_mode` (`FULL_TIME`/`SHIFT`/`FULL_TIME_AND_SHIFT`),
  validated `working_days` weekday codes, `start_date`, `notes`, plus
  `has_operational_history` and `supervisor_count`.
- **Supervisor assignments**: `SiteSupervisorAssignment`,
  `ZoneSupervisorAssignment`, `AssistantGeneralSupervisorAssignment` — date
  windows (`assigned_from`/`assigned_to`), soft `is_active`, partial-unique
  active constraints, `clean()` rules (AGS zone required unless `all_zones`,
  per-site supervisor cap from constance `MAX_SITE_SUPERVISORS_PER_SITE`,
  date-range validation).
- **Scoping selectors** (`apps/site_management/scoping.py`): `visible_zones`,
  `visible_sites`, `supervised_sites`, `assigned_zone_ids`,
  `site_in_user_scope`, `active_site_supervisor_ids`; `user_can_manage_site`
  rewritten for the assignment-based rules.
- **Services** for zone lifecycle (`create`/`update`/`deactivate`/`restore`)
  and supervisor assignment/ending (transactional, audited, cache-safe).
- **Admin**: `ZoneAdmin`, `SiteAdmin` (supervisor inline, delete guard),
  and the three assignment admins (search/filter/date-hierarchy/
  activate-deactivate actions/raw id fields).
- **API foundation**: paginated role-scoped `GET /zones`, `GET /zones/{id}`,
  paginated `GET /sites` (Paginated envelope + `zone_id`/`work_mode` filters),
  `GET /sites/{id}/supervisors`.
- **Factories**: `ZoneFactory`, updated `SiteFactory`, and the three
  assignment factories.

### Changed

- `/sites` list response is now the paginated envelope
  (`count`/`next`/`previous`/`results`) instead of a bare array.
- Site list/detail include zone and work-mode data; visibility is
  assignment/zone-based via the new scoping selectors.

## [Prompt 03] — 2026-08-13

### Added

- **Base models**: `TimeStampedModel`, `UserStampedModel` (nullable
  `created_by`/`updated_by` with `SET_NULL`), `ActivatableModel` (soft-delete
  manager), `CodeSlugModel`.
- **Audit logging**: redesigned `AuditLog` with `user`, `action`, `model_name`,
  `object_id`, `object_repr`, `before_data`/`after_data` JSON snapshots,
  `ip_address`, `request_id`; `record_audit()` service (backward-compatible
  `actor`/`changes` aliases) and `model_data()` snapshot helper.
- **Request-ID middleware**: reads/generates `X-Request-ID`, sets the response
  header, stores it in a contextvar, and injects it into every structured log
  line via `RequestIdFilter`.
- **Domain error contract**: `DomainError` hierarchy (`ConflictError`,
  `NotFoundError`, `ForbiddenActionError`, `BusinessRuleError`).
- **API error contract**: shared `{"error": {code, message, trace_id,
  fields}}` envelope via `apps.core.handlers` (ValidationError→422,
  DoesNotExist→404, PermissionDenied→403, ConflictError→409, unexpected→500).
- **Pagination & sorting**: `PageParams`, generic `Paginated` envelope
  (`count`/`next`/`previous`/`results`), constance-driven page-size defaults
  and caps, whitelisted `apply_ordering`.
- **Private file foundation**: `PrivateMediaStorage` (no public URL),
  extension/size validators, abstract `PrivateFileModel`, signed download
  tokens (TTL from constance `FILE_TOKEN_TTL_SECONDS`), and the
  `/files/signed/{token}/` streaming endpoint with permission checks and
  `FILE_DOWNLOAD` audit entries.
- **Domain-event outbox**: `DomainEvent` model + `publish_domain_event()`
  persisted via `transaction.on_commit`; `list_pending_domain_events`.
- **Cache utilities**: keys namespaced under `wbz_site`, `get_or_set`,
  `versioned`, `safe_delete`, prefix invalidation.
- **Layering helpers**: `apps/core/policies.py` (`require`,
  `ensure_permitted`) and `apps/core/validators.py`.

### Changed

- `record_audit` snapshots: `create_site`/`update_site` now record real
  `before_data`/`after_data` instead of a field delta.
- `config/api.py` now registers all error handlers from `apps.core.handlers`.
- Logging includes `request_id` on every line.
- Mypy test relaxation now disables `no-untyped-def` explicitly.

### Fixed

- django-constance database backend requires a cross-process cache; test
  settings disable `CONSTANCE_DATABASE_CACHE_BACKEND`.
- `ValidationError` with a list of messages now maps to 422 with a `_` field
  bucket (previous code crashed on `error_dict`).

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
