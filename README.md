# White Bird Zanzibar — Site Management Module

Premium Django backend for the White Bird Zanzibar estate: sites, zones,
supervisors, cleaners, attendance, inspections, issues/jobs, stores, stock,
reports and a role-aware dashboard. Built to production grade with a hardened
API, secure private-file handling, a branded Jazzmin admin, Celery background
jobs and a documented Office Management integration boundary.

## Overview

- **Ops backbone** — zones → sites → cleaners → assignments → attendance →
  inspections → issues/jobs → stores/stock → reporting chain → management
  dashboards.
- **RBAC** — six platform roles with a central object-level policy layer,
  site/zone data scoping, and a management-viewer read-only mode.
- **Events & notifications** — transactional domain-event outbox + in-app
  notifications with deduplication and Celery-delivered alerts.
- **Exports** — scoped, streamed, audit-logged CSV exports (attendance,
  cleaners, issues, jobs, reports).

## Tech stack

| Layer          | Technology                                   |
| -------------- | -------------------------------------------- |
| Runtime        | Python 3.12 (Docker) / 3.14 (local)          |
| Framework      | Django 5.2                                   |
| API            | Django Ninja — `/api/site-management/v1`     |
| Database       | PostgreSQL 16                                |
| Cache / Broker | Redis (`django-redis`)                       |
| Background     | Celery + `django-celery-beat`                |
| Admin          | Jazzmin (Material soft-gold theme) + `django-constance` |
| Tests          | pytest + pytest-django + factory-boy         |
| Quality gates  | Ruff (120) · Mypy strict · coverage ≥ 90%    |

## Quick start (local)

```bash
cp .env.example .env          # then edit to taste
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements/dev.txt -r requirements/test.txt
createdb whitebird
python manage.py migrate
python manage.py seed_rbac    # roles/groups/permissions (idempotent)
python manage.py seed_demo    # realistic demo tenant (idempotent)
make run                      # dev server on :8000
```

### URLs after boot

| Page                          | URL                                       |
| ----------------------------- | ----------------------------------------- |
| Dashboard                     | `http://localhost:8000/dashboard/`        |
| Jazzmin admin                 | `http://localhost:8000/admin/`            |
| API (Swagger docs)            | `http://localhost:8000/api/site-management/v1/docs` |
| API (OpenAPI JSON)            | `http://localhost:8000/api/site-management/v1/openapi.json` |
| Health / readiness            | `http://localhost:8000/healthz` · `/readyz` |

Demo admin login (from `seed_demo`): `admin@whitebird.local` / `demo-password-1`.

## Docker

```bash
# Production-like stack: web + Celery worker + beat + Postgres + Redis
cp .env.example .env
docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml exec web python manage.py seed_rbac
docker compose -f docker-compose.prod.yml exec web python manage.py seed_demo
```

The production image is a multi-stage, non-root build that runs migrations and
`collectstatic` on boot, then serves Gunicorn (see `scripts/entrypoint.sh`).
Persistent volumes cover Postgres data, Redis data, static files and private
media.

## Tests

```bash
pytest                          # full suite (test settings: SQLite, eager Celery)
pytest --cov=apps --cov-branch --cov-fail-under=90
ruff check . && ruff format --check .
mypy apps config
python manage.py makemigrations --check --dry-run
```

## Seed data

| Command                  | Purpose                                     |
| ------------------------ | ------------------------------------------- |
| `python manage.py seed_rbac`  | Idempotently create the six role groups + permissions. |
| `python manage.py seed_demo`  | Realistic demo tenant: users for every role, zones, sites, shifts/areas, cleaners, trainees, assignments, attendance, inspections, issues/jobs, stores/stock, and a completed reporting chain. |
| `python manage.py seed_volume` | Large synthetic volume for benchmarking (`--zones`, `--sites-per-zone`, `--cleaners-per-site`, `--days`). |

## Environment variables

See `.env.example` for the full set. The most important:

| Variable                       | Purpose                                   |
| ------------------------------ | ----------------------------------------- |
| `DJANGO_SECRET_KEY`            | Required in production.                   |
| `DJANGO_ALLOWED_HOSTS`         | Required in production.                   |
| `CSRF_TRUSTED_ORIGINS`         | Required in production.                   |
| `DJANGO_SETTINGS_MODULE`       | `config.settings.dev` (local) / `config.settings.prod` (deploy). |
| `DATABASE_URL`                 | PostgreSQL DSN.                           |
| `REDIS_URL`                    | Cache location.                           |
| `CELERY_BROKER_URL` / `CELERY_RESULT_BACKEND` | Celery broker/backend (Redis). |
| `CORS_ALLOWED_ORIGINS`         | Allowed frontend origins.                 |
| `API_THROTTLE_ANON_RATE` / `API_THROTTLE_AUTH_RATE` | API rate limits. |
| `SENTRY_DSN`                   | Optional error tracking.                  |
| `CSP_ENABLED`                  | Content-Security-Policy header (default on in prod). |

## Documentation

- `docs/DEPLOYMENT.md` — production deployment.
- `docs/SECURITY.md` — security posture.
- `docs/OPERATIONS.md` — operational runbook.
- `docs/API.md` — full endpoint catalog & API standards.
- `docs/FRONTEND_INTEGRATION.md` — how a Vite + Lit frontend consumes the API.
- `docs/OFFICE_INTEGRATION.md` — future Office Management boundary.
- `docs/PERFORMANCE.md` — indexes, caching, benchmarking.
- `docs/RBAC.md` — role/permission matrix.
- `docs/THEME.md` — design system.
