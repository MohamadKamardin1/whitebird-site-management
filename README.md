# White Bird Zanzibar — Site Management Module

Premium Django backend for managing sites, supervisors, staff, attendance,
tasks and stores across the White Bird Zanzibar estate. Backend foundation
first; a Vite + Lit frontend and a custom Jazzmin admin come later.

## Stack

| Layer          | Technology                                   |
| -------------- | -------------------------------------------- |
| Runtime        | Python 3.12 (Docker) / 3.14 (local)          |
| Framework      | Django 5.2                                   |
| API            | Django Ninja — `/api/site-management/v1`     |
| Database       | PostgreSQL 16                                |
| Cache / Broker | Redis (`django-redis`)                       |
| Background     | Celery + `django-celery-beat`                |
| Admin          | Jazzmin + `django-constance` runtime config  |
| Tests          | pytest + pytest-django + factory-boy         |
| Quality gates  | Ruff (120) · Mypy strict · coverage ≥ 90%    |

## Quick start

```bash
cp .env.example .env          # then edit to taste
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements/dev.txt -r requirements/test.txt
createdb whitebird
python manage.py migrate
python manage.py seed_sites   # idempotent demo tenant
make run                      # dev server
```

- API docs: `http://127.0.0.1:8000/api/site-management/v1/docs`
- OpenAPI: `http://127.0.0.1:8000/api/site-management/v1/openapi.json`
- Admin: `http://127.0.0.1:8000/admin/` (Jazzmin; constance "Configuration")
- Probes: `/healthz`, `/readyz`

## Commands

```bash
make setup          # venv + deps + pre-commit install
make lint           # ruff check
make format         # ruff format + fix
make type           # mypy strict
make test           # pytest + branch coverage (90% gate)
make quality        # lint + type + test + migration check
make run            # dev server
make worker         # celery worker
make beat           # celery beat
make seed           # demo data
make docker-up      # compose: db + redis + web
```

## Project layout

```
config/            split settings, urls, celery_app, ninja API
apps/core          audit log, soft-delete, cache, probes
apps/accounts      users, roles, API tokens, auth, permissions
apps/site_management   the site domain (sites, departments, assets, staff)
apps/web           host views (/healthz, /readyz, landing)
templates/ static/ frontend/   admin/theme + future Vite+Lit client
requirements/      base / dev / test / prod
scripts/           entrypoint + wait-for-db
docs/              contract, architecture, domain, RBAC, API, theme, …
```

## Documentation

- `docs/OPENCODE_CONTRACT.md` — engineering rules that govern every prompt
- `docs/ARCHITECTURE.md` — layering and module boundaries
- `docs/DOMAIN.md` — the White Bird operations domain
- `docs/RBAC.md` — role matrix
- `docs/API.md` — API strategy
- `docs/THEME.md` — light-soft-gold design direction
- `docs/TESTING.md`, `docs/PERFORMANCE.md`, `docs/ASSUMPTIONS.md`
- `docs/OPENCODE_STATE.md`, `docs/CHANGELOG.md`

## Docker

```bash
make docker-up      # builds image, starts db + redis + web on :8000
```

See `docs/ARCHITECTURE.md` and `docs/ASSUMPTIONS.md` for notes on the
Docker/test environment on this machine.
