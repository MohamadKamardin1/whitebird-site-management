# Architecture

## Layered architecture

The codebase follows a clean, testable layering. **Routers are thin** — they
parse and validate input, enforce authorization, and delegate:

```
HTTP ──► routers (apps/*/api.py, apps/*/views.py)
             │  auth (accounts/auth.py) + policies (apps/core/policies.py, per-app)
             ▼
      services (writes, business rules, transactions, audit, cache invalidation)
             │
             ▼
      selectors (reads, filtering, cache-aware access)
             │
             ▼
      validators (domain validation: apps/*/validators.py, apps/core/validators.py)
             │
             ▼
      models (persistence only — no business logic)
```

Layer responsibilities:

- **Routers** parse/validate request input, run a *policy*, and delegate to a
  service or selector. No business logic.
- **Policies** own permissions and data scoping (see `apps/core/policies.py`).
  Routers call a policy before a service; services assume it passed.
- **Services** own writes and business rules. Writes are transactional,
  audited, and invalidate affected caches.
- **Selectors** own reads: filtering, ordering, caching.
- **Validators** own domain validation rules (file policy, field formats).
- **Models** are persistence-only.

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

The shared kernel — reusable infrastructure with **no business logic**:

- Base models: `TimeStampedModel`, `UserStampedModel` (`created_by`/
  `updated_by`, `SET_NULL`), `ActivatableModel` (soft-delete manager),
  `CodeSlugModel`.
- `SoftDeleteManager` / `SoftDeleteQuerySet`.
- `AuditLog` — append-only trail: `user`, `action`, `model_name`, `object_id`,
  `object_repr`, `before_data`/`after_data` snapshots, `ip_address`,
  `request_id`. Written via `apps/core/services.record_audit`.
- `DomainEvent` — transactional outbox (created via `transaction.on_commit`);
  a future publisher consumes pending events.
- `PrivateFileModel` + `apps/core/files.py` — private storage (no public URL),
  extension/size validators, signed download tokens, `FILE_DOWNLOAD` audits.
- `apps/core/errors.py` — domain error contract (`DomainError` hierarchy).
- `apps/core/handlers.py` — Ninja error handlers implementing the shared
  `{"error": {code, message, trace_id, fields}}` envelope.
- `apps/core/middleware.py` — `RequestIdMiddleware` (X-Request-ID, contextvar,
  log filter, response header).
- `apps/core/pagination.py` — reusable page params + `Paginated` envelope +
  whitelisted sorting.
- `apps/core/cache.py` — namespaced keys under `wbz_site`, `get_or_set`,
  versioned keys, prefix invalidation.
- `apps/core/policies.py` / `apps/core/validators.py` — tiny helpers for the
  policy and validation layers.
- `AuthenticatedRequest` — typed `request.auth` for handlers.

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
