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

- **Pagination:** Limit/Offset (`?limit=`/`?offset=`), defaults from
  `DEFAULT_PAGE_SIZE` / `MAX_PAGE_SIZE` (runtime-configurable via constance).
- **Filtering:** query parameters scoped to the resource (e.g.
  `?status=active&region=...&capacity_min=...`).
- **Sorting:** stable server-side default ordering per resource; explicit
  sort keys are added per resource as needed.
- **Errors:** consistent envelope with a `detail` field.

  | HTTP | Meaning                                          |
  | ---- | ------------------------------------------------ |
  | 200  | Success                                          |
  | 401  | Missing/invalid token                            |
  | 403  | Authenticated but not permitted                  |
  | 404  | Resource not found                               |
  | 422  | Validation failure (Django `ValidationError`)    |
  | 429  | Rate limit exceeded (future)                     |

- **Caching:** read-heavy endpoints (site detail, stats) are cached in Redis
  and invalidated by write-path services.

## Modules

| Router prefix        | Purpose                                        |
| -------------------- | ---------------------------------------------- |
| `/auth`              | Login, profile, tokens, staff directory        |
| `/sites`             | Sites + nested departments/assets/assignments  |
| `/catalog`           | Site types, statuses, asset categories         |
| `/stats`             | Cross-site statistics overview                 |
| `/notifications`     | In-platform notifications                      |
| `/` (core)           | Health, audit logs                             |

## Outside the API

- `/healthz` — liveness (no dependencies touched)
- `/readyz` — readiness (DB + cache probes)
- `/` → `/admin/` — landing redirect until the dashboard ships
- `/admin/` — Jazzmin-themed Django admin (runtime configuration via constance)
- `/accounts/` — session auth views: login/logout, password change, password
  reset foundation (`password_reset`, `password_reset_confirm`, etc.)
