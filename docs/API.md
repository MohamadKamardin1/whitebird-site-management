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

- **Today:** revocable bearer tokens (`Authorization: Bearer <token>`), issued
  via `POST /auth/login` or from the admin. Tokens may carry an expiry and are
  tracked with `last_used_at`.
- **Roadmap:** JWT (access + refresh) is pre-configured in settings
  (`JWT_*`, `AUTH_MECHANISM`); session auth covers the admin and future
  dashboard. The API switches mechanisms by configuration, not code churn.
- **Brute force:** django-axes locks accounts after repeated failures.

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
