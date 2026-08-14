# Operations

Operational runbook for the White Bird Zanzibar backend.

## Health & readiness

- `GET /healthz` — liveness (no DB/cache dependency).
- `GET /readyz` — readiness (DB + cache probes; 503 when degraded).
- `GET /api/site-management/v1/audit-logs` — recent audit trail (management roles).

Wire these into your orchestrator's health checks (the Dockerfile HEALTHCHECK
already probes `/healthz`).

## Scheduled jobs (Celery Beat, DB scheduler)

Registered idempotently on `migrate`; editable from the admin under
**Periodic Tasks**:

| Task                        | Interval | Purpose                            |
| --------------------------- | -------- | ---------------------------------- |
| Recompute site statistics   | 15m      | Warm per-site stats caches         |
| Publish domain events       | 30s      | Advance the transactional outbox   |
| Warm dashboard cache        | 5m       | Precompute KPI/chart caches        |
| Check missing site reports  | 30m      | Notify supervisors of missing reports |
| Check overdue jobs          | 30m      | Notify assignees of overdue jobs   |
| Check low stock             | 30m      | Notify store managers of low stock |

All tasks are idempotent with retry/backoff.

## Common operations

### Daily reporting chain

1. Site supervisors generate/submit daily site reports (`/reports/site/...`).
2. Zone supervisors review and generate zone summaries (`/reports/zone/...`).
3. Assistant general submits a cross-zone summary.
4. General supervisor compiles and submits the management report.

Monitor progress with `GET /api/site-management/v1/reports/status` and
`GET /api/site-management/v1/reports/missing`.

### Exports

`GET /api/site-management/v1/exports/{attendance,cleaners,issues,jobs,reports}.csv`
stream scoped CSV; each export is audited. Set `EXPORT_MAX_ROWS` (constance) to
cap output.

### Alerts

In-app notifications power operational alerts (missing reports, overdue jobs,
low stock, escalations, job assignments). See
`GET /api/site-management/v1/notifications`. Retention is
`NOTIFICATION_RETENTION_DAYS` (constance); `cleanup_old_notifications` purges
read rows.

## Backups

- `scripts/backup_db.sh` — Postgres dump (compressed custom format).
- `scripts/backup_media.sh` — private media archive.
- `scripts/restore_notes.md` — restore steps.

## Performance

- Dashboard/cache: `DASHBOARD_CACHE_TTL_SECONDS`, `REPORT_CACHE_TTL`,
  `DASHBOARD_CACHE_TTL` (constance), `SITE_STATS_SCHEDULE_SECONDS`.
- API rate limits: `API_THROTTLE_ANON_RATE`, `API_THROTTLE_AUTH_RATE`.
- Benchmark: `python manage.py seed_volume --zones 3 --sites-per-zone 4 ...` then
  `python manage.py benchmark --threshold-ms 200`.
- Hot paths are indexed (migrations `0012`+); see `docs/PERFORMANCE.md`.

## Troubleshooting

- **429s**: rate limit exceeded — check `API_THROTTLE_*` settings.
- **Signed downloads fail after deploy**: `DJANGO_SECRET_KEY` changed — tokens
  re-issued on next request.
- **Tasks not running**: verify `beat` + `worker` services are up and Redis is
  reachable; check the admin **Periodic Tasks** page.
- **Missing data in dashboards**: run `warm_dashboard_cache` or wait for the
  beat schedule; confirm the site is in the caller's `visible_sites` scope.
