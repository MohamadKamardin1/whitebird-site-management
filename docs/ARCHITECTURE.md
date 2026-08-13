# Architecture

## Layered architecture

The codebase follows a clean, testable layering. **Routers are thin** — they
parse and validate input, enforce authorization, and delegate:

```
HTTP ──► routers (apps/*/api.py, apps/*/views.py)
             │  auth (apps/accounts/auth.py) + permissions (apps/accounts/permissions.py)
             ▼
      services (writes, business rules, transactions, audit, cache invalidation)
             │
             ▼
      selectors (reads, filtering, cache-aware access)
             │
             ▼
      models (persistence only — no business logic)
```

Rules enforced by review (see `OPENCODE_CONTRACT.md`):

- No business logic in routers, views, or admin.
- Writes are transactional, audited, and invalidate affected caches.
- Asynchronous side effects go through Celery tasks.
- Reference/business configuration lives in `django-constance` or DB rows.

## Module boundaries

```
config/                 settings (base/dev/test/prod), urls, celery, ninja API
apps/core               shared infrastructure: audit log, soft-delete, cache, probes
apps/accounts           users, roles, API tokens, bearer auth, permissions
apps/site_management    the site domain: sites, departments, assets, assignments
apps/web                host-facing views: /healthz, /readyz, landing redirect
```

### `apps.core`

- `TimeStampedModel` (abstract `created_at`/`updated_at`)
- `SoftDeleteManager` / `SoftDeleteQuerySet` — archived rows hidden by default
- `AuditLog` — append-only trail; admin is read-only
- `apps/core/cache.py` — stable cache keys, `cached_or`, invalidation
- `apps/core/api.py` — API health + audit-log endpoints
- `AuthenticatedRequest` — typed `request.auth` for handlers

### `apps.accounts`

- `User` — email-identified (`AbstractBaseUser` + `PermissionsMixin`) with
  platform `RoleCode` (`system_admin`, `general_supervisor`,
  `assistant_general_supervisor`, `zone_supervisor`, `site_supervisor`,
  `management_viewer`), phone/timezone/avatar, and role helpers.
- `ApiToken` — revocable refresh/machine tokens.
- `apps/accounts/tokens.py` — signed (HMAC) access tokens.
- `apps/accounts/auth.py` — `TokenAuth(HttpBearer)` accepting access tokens
  and `ApiToken` keys.
- `apps/accounts/rbac.py` — declarative role→group→permission matrix used by
  the idempotent `seed_rbac` command and the role-group sync signal.
- `apps/accounts/permissions.py` — `role_required`, `management_required`,
  site-scoped `user_can_manage_site`.
- `apps/accounts/middleware.py` — per-user timezone activation.
- Brute-force protection via django-axes (email + IP lockout).

### `apps.site_management`

The site domain (see `DOMAIN.md`). Models: `Site`, `SiteType`, `SiteStatus`,
`Department`, `Asset`, `AssetCategory`, `StaffAssignment`, `Notification`.
Services and selectors mirror the layering above; Celery tasks handle
status-change notifications and periodic statistics refresh (registered into
the Celery Beat database scheduler on migrate).

### `apps.web`

Host-facing views only: `/healthz` (liveness), `/readyz` (db + cache
readiness), and the root landing redirect to `/admin/`. The future dashboard
will live here.

### Future `apps.office_management` boundary

Stores/inventory/office concerns will be a separate app. It may depend on
`apps.core` (audit, cache, base models) and consume `site_management` data
through public services/selectors, but never reach into another app's
internals. Shared contracts live in `apps.core`.

## Settings

Split profiles, environment-driven through `django-environ`:

| Profile  | `DJANGO_SETTINGS_MODULE`     | Purpose                          |
| -------- | ---------------------------- | -------------------------------- |
| base     | (shared)                     | Common config                    |
| dev      | `config.settings.dev`        | Relaxed security, debug tools    |
| test     | `config.settings.test`       | Hermetic: SQLite, locmem, eager  |
| prod     | `config.settings.prod`       | Locked down; refuses missing env |

Runtime configuration (branding, page sizes, TTLs, feature flags) is editable
from the admin via `django-constance`.

## Async architecture

- **Broker/backend:** Redis (`CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`).
- **Scheduler:** `django_celery_beat.schedulers:DatabaseScheduler` — schedules
  are managed in the admin; the default stats-refresh task is registered
  idempotently on migrate.
- **Tests:** eager mode (no broker required).

## Security

- Bearer API tokens (revocable, expiring) for the API.
- django-axes locks accounts after repeated login failures.
- Production: HTTPS redirect, HSTS, secure cookies, trusted-CSRF/CORS lists.
- Private media root separate from public static (WhiteNoise serves static
  only); file delivery behind signed tokens is a later milestone.
