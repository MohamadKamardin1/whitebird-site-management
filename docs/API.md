# API Strategy

## Contract

- **Base path:** `/api/site-management/v1`
- **Framework:** Django Ninja
- **Docs:** interactive Swagger at `/api/site-management/v1/docs`
- **Schema:** OpenAPI 3 at `/api/site-management/v1/openapi.json`
- **Versioning:** URL-prefixed major version (`v1`). Breaking changes require a
  new prefix; additive changes keep the current prefix. The version is part of
  the URL so clients and proxies can pin it.

## Authentication

The API uses a hybrid, secure token foundation (no external JWT dependency —
see `apps/accounts/tokens.py`):

- **Access tokens** are short-lived, stateless, signed payloads
  (`django.core.signing`, HMAC with the project secret). TTL:
  `ACCESS_TOKEN_TTL_SECONDS` (default 1800s).
- **Refresh tokens** are server-side `ApiToken` rows: revocable, expiring
  (`REFRESH_TOKEN_TTL_SECONDS`, default 7 days), tracked with `last_used_at`.

Send the access token as `Authorization: Bearer <token>`. Long-lived machine
tokens issued via the admin/`POST /auth/tokens` are also accepted by the same
scheme.

- **Login identifier:** email (case-insensitive unique).
- **Brute force:** django-axes locks accounts after `AXES_FAILURE_LIMIT`
  repeated failures (by email + IP).
- **Session auth** covers the admin and the future dashboard; password
  reset/change flows use Django's built-in auth views at `/accounts/`.

### Token endpoints

| Method | Path                          | Description                          |
| ------ | ----------------------------- | ------------------------------------ |
| POST   | `/auth/login`                 | Exchange email + password for tokens |
| POST   | `/auth/refresh`               | Exchange refresh token for a new access token |
| POST   | `/auth/logout`                | Revoke a refresh token               |
| POST   | `/auth/password-change`       | Change the current user's password (authenticated) |
| GET    | `/auth/me`                    | Current user profile                 |
| GET    | `/auth/me/stats`              | Dashboard aggregates for the user    |

## Authorization

Permissions are enforced per route (see `RBAC.md`): platform roles via
`role_required(...)` and site-scoped access via read/write helpers. All
write endpoints are restricted to admin/manager (or site-manager assignment).

## Conventions

- **Pagination:** `PageParams` (`page`, `page_size`) with defaults/caps from
  constance (`DEFAULT_PAGE_SIZE`, `MAX_PAGE_SIZE`). Responses use the
  `Paginated` envelope: `count`, `next`, `previous`, `results`.
- **Filtering:** query parameters scoped to the resource (e.g.
  `?status=active&region=...&capacity_min=...`).
- **Sorting:** whitelisted sort keys via `apply_ordering` (unknown keys are
  ignored).
- **Errors:** consistent envelope, identical for every endpoint:

  ```json
  {
    "error": {
      "code": "validation_error",
      "message": "…",
      "trace_id": "…",
      "fields": {}
    }
  }
  ```

  | HTTP | Code              | Source                                |
  | ---- | ----------------- | ------------------------------------- |
  | 400  | `business_rule`   | `BusinessRuleError`                   |
  | 401  | `unauthorized`    | missing/invalid token                 |
  | 403  | `forbidden`       | `PermissionDenied` / `ForbiddenActionError` |
  | 404  | `not_found`       | `ObjectDoesNotExist` / `Http404` / `NotFoundError` |
  | 409  | `conflict`        | `ConflictError`                       |
  | 422  | `validation_error`| Django `ValidationError`              |
  | 500  | `internal_error`  | unexpected (safe, no internals leaked) |

- **Caching:** read-heavy endpoints (site detail, stats) are cached in Redis
  (keys namespaced under `wbz_site`) and invalidated by write-path services.

## Modules

| Router prefix        | Purpose                                        |
| -------------------- | ---------------------------------------------- |
| `/auth`              | Login, profile, tokens, staff directory        |
| `/zones`             | Zones (paginated, role-scoped)                 |
| `/sites`             | Sites + nested departments/assets/assignments/supervisors |
| `/catalog`           | Site types, statuses, asset categories         |
| `/stats`             | Cross-site statistics overview                 |
| `/notifications`     | In-platform notifications                      |
| `/files/signed/…`    | Signed private-file download                   |
| `/` (core)           | Health, audit logs                             |

### Organisation hierarchy endpoints (read-only foundation)

| Method | Path                                | Description                                   |
| ------ | ----------------------------------- | --------------------------------------------- |
| GET    | `/zones`                            | List zones (paginated, role-scoped)           |
| GET    | `/zones/{id}`                       | Zone detail (role-scoped)                     |
| GET    | `/sites`                            | List sites (paginated, filterable, role-scoped) |
| GET    | `/sites/{id}`                       | Site detail (role-scoped)                     |
| GET    | `/sites/{id}/supervisors`           | Active site-supervisor assignments            |

### Site configuration endpoints

| Method | Path                                        | Description                          |
| ------ | ------------------------------------------- | ------------------------------------ |
| GET    | `/sites/{id}/shifts`                         | List a site's shifts                 |
| POST   | `/sites/{id}/shifts`                         | Create a shift                       |
| PUT    | `/sites/{id}/shifts/{shift_id}`              | Update a shift                       |
| PATCH  | `/sites/{id}/shifts/{shift_id}/status`       | Activate/deactivate a shift          |
| GET    | `/sites/{id}/areas`                          | List a site's areas                  |
| POST   | `/sites/{id}/areas`                          | Create an area                       |
| PUT    | `/sites/{id}/areas/{area_id}`                | Update an area                       |
| PATCH  | `/sites/{id}/areas/{area_id}/status`         | Activate/deactivate an area          |
| GET    | `/operational-roles`                         | List operational roles               |
| POST   | `/operational-roles`                         | Create an operational role           |
| PUT    | `/operational-roles/{id}`                    | Update an operational role           |
| PATCH  | `/operational-roles/{id}/status`             | Activate/deactivate a role           |

Shift payload: `shift_name`, `shift_code`, `start_time`, `end_time`,
`effective_days` (day codes), `sequence`, `description`. Overnight shifts
(`end_time <= start_time`) are supported; responses include
`crosses_midnight`. Work-mode rules (FULL_TIME cannot have shifts, SHIFT must
keep ≥1) are enforced on every write. Writes require SYSTEM_ADMIN /
GENERAL_SUPERVISOR / `manage_site_configuration` permission scoped to the
site; reads follow the visible scope.

Site list filters: `search`, `status` (slug), `site_type` (slug), `region`,
`country`, `zone_id`, `work_mode`, `capacity_min`, plus pagination
(`page`, `page_size`). Responses use the `Paginated` envelope
(`count`/`next`/`previous`/`results`). Visibility follows the scoping rules
in `RBAC.md`.

## Private file downloads

Private files (cleaner documents, inspection photos, job photos) are never
served from a public URL. A signed token endpoint streams them:

`GET /api/site-management/v1/files/signed/{token}/`

The token is issued by `apps.core.files.create_file_token` and encodes the
target user, model, object id, and an expiry (TTL from constance
`FILE_TOKEN_TTL_SECONDS`). The endpoint validates the signature + expiry and
enforces that the downloader is the token owner or a system admin; every
download is written to the audit trail (`file_download` action).

## Outside the API

- `/healthz` — liveness (no dependencies touched)
- `/readyz` — readiness (DB + cache probes)
- `/` → `/admin/` — landing redirect until the dashboard ships
- `/admin/` — Jazzmin-themed Django admin (runtime configuration via constance)
- `/accounts/` — session auth views: login/logout, password change, password
  reset foundation (`password_reset`, `password_reset_confirm`, etc.)
