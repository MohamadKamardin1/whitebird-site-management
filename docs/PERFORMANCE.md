# Performance Principles

Non-negotiable performance rules for the platform.

## 1. No N+1 queries

- Every read selector uses `select_related` / `prefetch_related` for the
  relations it traverses (e.g. site list loads `site_type`, `status`).
- Aggregate counts are computed in a single annotated query (`Count` with
  `filter=...`, `distinct=True`) rather than per-object `.count()` calls.
- New selectors must be reviewed for query counts; the debug toolbar is on in
  dev to catch offenders early.

## 2. Pagination everywhere

- List endpoints return bounded pages (`?limit`/`?offset`), never unbounded
  querysets. Defaults and caps come from runtime configuration
  (`DEFAULT_PAGE_SIZE`, `MAX_PAGE_SIZE`).
- Cross-site statistics are aggregated server-side and cached, so dashboards
  never page over raw rows.

## 3. Caching

- **Read-heavy endpoints are cached in Redis** (site detail, per-site stats)
  with short, explicit TTLs (`DASHBOARD_CACHE_TTL`, `REPORT_CACHE_TTL`).
- **Write-through invalidation:** every service mutation invalidates the exact
  cache keys it affects inside the same transaction path.
- **Bulk invalidation** (`invalidate_prefix`) uses Redis `SCAN`/`DEL` for
  prefix families (e.g. stats refresh) instead of per-key deletes.
- `django-constance` values are read through the Django cache
  (`CONSTANCE_DATABASE_CACHE_BACKEND`).

## 4. Optimised selectors

- Selectors return exactly the fields and relations the API needs.
- Filtering happens in SQL (`.filter(...)`) rather than in Python where
  possible; Python-side scoping is reserved for authorization slices.
- Cache-aware reads use `cached_or` with a deterministic `cache_key`.

## 5. Indexes

- Foreign keys used as filters/joins are indexed (Django default).
- Composite indexes exist for hot lookups:
  - `Site(status, site_type)` and `Site(is_active, status)`
  - `AuditLog(entity_type, entity_id)` + `created_at`
  - unique constraints back `site.code`, `site.slug`, department/asset names.
- Migration review must consider whether new filters need indexes.

## 6. Bulk operations

- Batch mutations use queryset-level operations (`.update()`,
  `.filter(...).update(...)`) rather than per-row saves (e.g.
  `mark_notifications_read`).
- Background aggregation (`recompute_site_statistics`) refreshes the whole
  stats cache in one pass on a schedule, keeping dashboards warm without
  synchronous computation.
- Seeding uses `get_or_create` bulk-friendly patterns and is idempotent.

## 7. Async off the request path

- Notifications, status-change fan-out, and periodic aggregation run in
  Celery workers — never inline in a request.
- The request path only dispatches tasks (`.delay(...)`) and continues.
