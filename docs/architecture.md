# Architecture

## Layering

The codebase follows a clean, testable layering. **Routers are thin** — they
parse and validate input, enforce authorization, and delegate:

```
HTTP ──► routers (apps/*/api.py)
             │  auth (accounts/auth.py) + permissions (accounts/permissions.py)
             ▼
      services (writes, business rules, transactions, audit, cache invalidation)
             │
             ▼
      selectors (reads, filtering, cache-aware access)
             │
             ▼
      models (persistence only — no business logic)
```

Rules of thumb enforced by review:

- **No business logic in routers, views, or admin.** All mutations live in
  `apps/*/services.py`; all reads in `apps/*/selectors.py`.
- **Writes are transactional** and always emit an `AuditLog` entry (who, what,
  when, before/after delta).
- **Writes invalidate the affected caches** in the same transaction path.
- **Asynchronous side effects** (notifications, periodic aggregation) are
  dispatched through Celery tasks in `apps/*/tasks.py`, never run inline.
- **No hardcoded business configuration.** Site types, statuses and asset
  categories are configuration rows managed in the admin (`SiteType`,
  `SiteStatus`, `AssetCategory`). Only permission-relevant roles are code-level
  constants, because authorization must be enforced in code.

## Apps

### `apps.common`

- `TimeStampedModel` — abstract `created_at`/`updated_at` base.
- `SoftDeleteManager` / `SoftDeleteQuerySet` — hide archived rows by default,
  expose `all_with_deleted()`, `only_deleted()`.
- `AuditLog` — append-only trail; the admin is read-only.
- `apps/common/cache.py` — stable cache keys + `cached_or` + invalidation.
- `apps/common/api.py` — `/health` (DB + cache probes) and `/audit-logs`.
- `AuthenticatedRequest` (typed `request.auth`) used by all API handlers.

### `apps.accounts`

- `User` — custom user model with platform `Role`
  (`admin`, `manager`, `staff`, `viewer`). Superusers are always `admin`.
- `ApiToken` — revocable bearer tokens with optional expiry and
  `last_used_at` tracking.
- `accounts/auth.py` — `ApiTokenAuth(HttpBearer)`; refreshes `last_used_at`
  at most every 5 minutes.
- `accounts/permissions.py` — `role_required` predicate and site-scoped
  `user_can_manage_site`. Write access requires admin *or* (assignment +
  MANAGER role / site-manager assignment).

### `apps.sites`

Domain model:

- `SiteType`, `SiteStatus`, `AssetCategory` — configuration catalogs.
- `Site` — the core entity; soft-deleted via `is_active`; unique `slug` and
  `code`; optional geo-coordinates, capacity, contact details.
- `Department` — operational unit within a site (unique per site+name).
- `Asset` — physical asset (unique per site+serial number; soft-deleted).
- `StaffAssignment` — links a user to a site with a site-scoped
  `AssignmentRole` (`site_manager` / `staff`); unique per site+user.
- `Notification` — in-platform notifications delivered by Celery tasks.

Caching:

- Site detail and per-site stats are cached in Redis (`site:detail:*`,
  `site:stats:*`) and invalidated on every write.
- A Celery beat task (`recompute_site_statistics`) periodically refreshes the
  stats cache so dashboards stay warm even without read traffic.

## Data flows worth noting

1. **Status change** — `update_site` detects a status diff, writes an audit
   entry, dispatches `notify_site_status_change`, and invalidates caches.
   The task notifies all admins and any staff assigned to the site.
2. **Staff assignment** — `assign_staff` is idempotent (update-or-create),
   dispatches `notify_staff_assigned` on first assignment, and invalidates
   the site cache.
3. **Archive / restore** — soft delete keeps history and audit trails intact;
   restore returns the site to visibility.

## Cross-cutting concerns

- **Auditing** — every write path calls `record_audit` inside the same
  transaction. Exposed read-only to admins/managers at `/api/v1/audit-logs`.
- **Authorization** — handled in routers before any service call; service
  functions assume the caller already passed the permission check.
- **Typing** — mypy strict across the codebase; tests relax only the
  annotation requirements, not logic checks.
