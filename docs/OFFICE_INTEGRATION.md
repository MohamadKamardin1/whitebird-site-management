# Office Management Integration Boundary

How the future `apps.office_management` module will consume the Site Management
module — and why nothing is coupled to it today.

## The boundary

Site Management (`apps.site_management`) owns the operational estate: sites,
staffing, attendance, stores, inspections, issues, jobs and the reporting
chain. Office Management will own HR, inventory, finance and procurement.
They are **separate Django apps** and must never reach into each other's
internals.

Today the two are decoupled:

- Site Management publishes **domain events** into the transactional outbox
  (`apps.core.models.DomainEvent`) with **no consumer** — a future Office
  subscriber will read them.
- It exposes a complete **OpenAPI contract** (bearer auth, scoped, paginated)
  that Office modules can call across app boundaries or via service
  contracts in `apps.core`.

## What Site Management exposes

### 1. Domain events (transactional outbox)

Every major action writes a `DomainEvent` row via `transaction.on_commit`
(published only if the surrounding transaction commits). Events carry a
versioned payload, `aggregate_type`/`aggregate_id`, `occurred_at`, and a
`status` (pending → published). The Celery task `publish_domain_events`
advances the outbox; a future subscriber hooks in there.

Current event vocabulary:

| Event                      | Payload highlights                     |
| -------------------------- | -------------------------------------- |
| `CleanerRegistered`        | cleaner_id, site_id                     |
| `CleanerActivated`         | cleaner_id                              |
| `CleanerDeactivated`       | cleaner_id                              |
| `TraineePassed/Failed/Dropped` | program_id, cleaner_id, site_id, reason |
| `AttendanceSubmitted`      | record ids / site / date                |
| `SiteReportSubmitted`, `ZoneReportSubmitted`, `AssistantReportSubmitted`, `GeneralReportSubmitted` | report id, report_date |
| `IssueEscalated`           | issue_id, level, reason                 |
| `JobAssigned`              | job_id, assignees                       |
| `JobCompleted`, `JobVerified` | job_id, site_id                      |
| `StockRequestSubmitted`    | request_id, store_id, site_id           |
| `StockLow`                 | store_item_id, store_id, current/min    |

### 2. Public API

- Base path `/api/site-management/v1`, OpenAPI at
  `/api/site-management/v1/openapi.json`, bearer auth.
- **Exports** (`/exports/*.csv`) stream scoped CSV (sanitised against formula
  injection, audited, capped by `EXPORT_MAX_ROWS`).
- **Notifications** (`/notifications/*`) for user-facing alerts.

### 3. Service/selector contracts

Shared contracts live in `apps.core` (audit, cache, outbox, errors). Office
modules should call Site Management through its **public selectors/services**
(e.g. `dashboard_selectors.dashboard_kpis`, `reporting_selectors.*`) rather
than raw models, and never import `apps.site_management.models` internals
beyond documented public entry points.

## Future Office Management modules

| Module       | Scope                                              | Consumption                                 |
| ------------ | -------------------------------------------------- | ------------------------------------------- |
| **HR**       | Applicant/trainee lifecycle, contracts, payroll    | consumes `Cleaner*`, `Trainee*` events; reads cleaner registry |
| **Inventory**| Central/office inventory, procurement stock        | consumes `StockLow`, `StockRequestSubmitted` events; reads store data |
| **Finance**  | Invoicing, costs, payroll                          | consumes report chain events + export data  |
| **Procurement** | Purchase orders, supplier management            | consumes `StockRequestSubmitted`, low-stock alerts |

## Subscription strategy

1. **Today**: outbox rows accumulate; `publish_domain_events` marks them
   published (no-op consumer). No external system is required.
2. **Next**: implement a consumer (Celery task or streaming worker) that
   reads published events and forwards them to Office Management via a
   message bus (e.g. Redis pub/sub, SQS) or an HTTP callback with an
   outbox-delivery guarantee.
3. **Retries**: a failed delivery marks the event `failed` (with retry/backoff)
   rather than dropping it; consumers must be idempotent by `event_id`.

## Guarantees

- **No direct coupling** — Office Management never imports Site Management
  models; it consumes events/API/selectors.
- **Idempotency** — every consumer keys on `event_id` / `aggregate_id`.
- **Audit** — all exports and administrative actions are recorded in the
  audit trail.
