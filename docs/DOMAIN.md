# Domain — White Bird Zanzibar Site Management

This document summarises the operational domain the platform serves. It is
intended as shared vocabulary between engineering and operations; the domain
model is built incrementally across prompts.

## The estate

White Bird Zanzibar operates hospitality sites across the island. Sites are
organised into **zones** (geographic/administrative groupings) and each site
is a physical building or property under management.

## Roles

| Role                          | Responsibilities                                        |
| ----------------------------- | ------------------------------------------------------- |
| **General Supervisor**        | Oversees all zones; top of the operational reporting chain. |
| **Assistant General Supervisor** | Deputises for the general supervisor; escalations land here. |
| **Zone Supervisor**           | Owns a zone: site performance, staffing, escalation.     |
| **Site Supervisor**           | Owns a single site's day-to-day operations and staff.   |
| **Management Viewer**         | Read-only access to dashboards/reports (no operations).  |
| **Cleaners**                  | Execute cleaning tasks assigned to areas within a site.  |
| **Applicants**                | Candidates in the hiring pipeline; not yet staff.        |
| **Trainees**                  | In probation/training; limited task scope.               |

## Zones and sites

- A **zone** contains one or more **sites/buildings**.
- Each **site** has at least one **site supervisor** (bounded by
  `MAX_SITE_SUPERVISORS_PER_SITE`).
- A **zone supervisor** manages multiple sites within their zone.

## Operations

- **Attendance** — daily presence tracking for cleaners, trainees and staff,
  reconciled per site/shift.
- **Shifts / full-time configuration** — staff are either full-time or
  shift-based; the platform must record schedules and per-site coverage.
- **Area / task assignment** — sites are split into areas; cleaning tasks are
  assigned to individual cleaners or trainees, tracked to completion.
- **Site store** — per-site consumables inventory; stock levels trigger
  low-stock alerts (`LOW_STOCK_DEFAULT`).
- **Inspections** — periodic quality inspections per site; results feed the
  reporting chain.
- **Issues** — operational incidents raised at a site, escalated up the chain
  when unresolved.
- **Jobs** — work orders / ad-hoc jobs routed to staff by supervisors.

## Reporting chain

```
Cleaner / Trainee
      │  assigned tasks, attendance
      ▼
Site Supervisor
      │  site issues, inspections, store
      ▼
Zone Supervisor
      │  zone performance, escalations
      ▼
Assistant General Supervisor
      │
      ▼
General Supervisor
```

Management viewers observe aggregated dashboards and reports at any level
without mutating operations.

## Boundaries

- **Site management** (this module): zones, sites, supervisors, attendance,
  shifts, area/task assignment, inspections, issues, jobs.
- **Office management** (future module): store/inventory operations beyond the
  per-site store, HR applicant/trainee pipelines, finance-adjacent records.

## Notes for implementation

- Role permissions are code-enforced (see `RBAC.md`).
- Operational thresholds (page sizes, low stock, supervisor caps, cache TTLs)
  are runtime configuration via `django-constance`.
- Attendance, shifts, inspections, issues and jobs are **future prompts**;
  this prompt establishes only the foundational platform and the site
  management skeleton carried forward from earlier scaffolding.
