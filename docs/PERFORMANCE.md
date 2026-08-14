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

## 8. Prompt 16 — performance engineering additions

### Indexes & constraints

Composite indexes added in migration `0012` for the hot access patterns:

- `AttendanceRecord(attendance_date, status)` and
  `(site, attendance_date, status)` (daily sheets, exceptions).
- `Issue(status, priority, due_date)` and `(site, created_at)`.
- `Job(assigned_to_user, status)` and `(site, created_at)`.
- `StoreItem(store, current_stock)` and `(current_stock, minimum_stock_level)`
  (low-stock scans).
- `CleanerDocument(status, document_type)` and
  `(cleaner, status, document_type)` (verification queries).
- `DailySiteReport(report_date, status)`, `ZoneSummaryReport`,
  `AssistantGeneralSummaryReport` and `GeneralManagementReport`
  `(report_date, status)`.

`CheckConstraint`s (safe, DB-enforced): stock movement quantity non-zero; store
item opening/minimum stock non-negative; stock-request requested quantity
positive and approved quantity non-negative.

### Query optimisation

- **Cleaner list N+1 removed**: `cleaner_list_queryset` annotates the
  verified-identity flag with an `Exists` subquery, so serialising a page is a
  constant number of queries instead of 1 + N document lookups.
- **`get_all_site_stats`** collapsed from 4N queries to **one** annotated
  aggregate (departments/assets/staff counts via `Count(...)`).
- Every paginated list uses `select_related`/`prefetch_related` and aggregates
  in SQL; `Count`/`Avg`/`Exists`/`Subquery` are used instead of Python loops.

### Caching

All cache keys are namespaced under `wbz_site` and versioned where needed;
TTLs come from constance (`DASHBOARD_CACHE_TTL`, `REPORT_CACHE_TTL`) or
settings.

| Data                          | Cache key prefix | Invalidated by                               |
| ----------------------------- | ---------------- | -------------------------------------------- |
| Site stats                    | `site:stats`     | beat refresh / write paths                   |
| Cross-site KPI overview       | `kpi`            | `refresh_all_site_stats_cache` (exact key)   |
| Report status dashboard       | `report:status`  | report service writes (`invalidate_prefix`)  |
| Theme metadata                | `theme`          | short TTL (constance edit tolerance)         |

- `cached_or` falls back to the database when the cache backend errors.
- Write-path lookups (`site_report_detail`) are **not** cached — freshness
  beats latency for a single indexed-row read.
- Prefix invalidation (`invalidate_prefix`) uses Redis `SCAN`/`DEL`; on the
  local-memory cache used by tests it is a no-op, so tests clear the cache
  between cases.

### Bulk operations

- Attendance generation/review already use `bulk_create`/`bulk_update`.
- Stock movements update `current_stock` with `F` expressions under a row lock.
- The issues CSV export (`GET /issues/export`) streams rows with
  `StreamingHttpResponse` + `QuerySet.iterator(chunk_size=500)` — it never
  loads the full result set.
- List endpoints stay bounded by `page`/`page_size` (capped by
  `MAX_PAGE_SIZE`).

### Volume seeding & benchmarking

Generate realistic volume and measure the hot selectors:

```bash
python manage.py seed_volume --zones 3 --sites-per-zone 4 --cleaners-per-site 20 --days 30
python manage.py benchmark --threshold-ms 200
```

`seed_volume` is bulk-created and idempotent per `--run-tag`; `benchmark` runs
the key selectors, prints wall-clock time + query counts per selector, and
exits non-zero when any exceed the threshold.

### Production tuning recommendations

- Run the API behind an ASGI server (uvicorn/gunicorn+uvloop) with several
  workers; keep `CONN_MAX_AGE` high (Postgres).
- Point the cache at Redis (settings already default `REDIS_URL`); Redis makes
  `invalidate_prefix` efficient and keeps rate limiting shared across workers.
- Use `pgaudit`/`pg_stat_statements` to review hot queries; the composite
  indexes above cover the reported access patterns.
- Keep the Celery beat stats-refresh task registered so site stats stay warm
  (`SITE_STATS_SCHEDULE_SECONDS`).
- For very large tenant datasets, consider partitioning `AttendanceRecord` by
  month and adding a trigram index on `Site.name`/`Cleaner.first_name` for
  fuzzy search (requires `pg_trgm`).
