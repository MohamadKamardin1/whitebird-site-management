# White Bird Zanzibar — Site Management Module

Premium, production-grade Django backend for managing sites (properties),
departments, assets, staff assignments, notifications and operational
statistics across the White Bird Zanzibar estate.

## Stack

| Layer          | Technology                                    |
| -------------- | --------------------------------------------- |
| Runtime        | Python 3.12+ (developed on 3.14)              |
| Framework      | Django 5.2                                    |
| API            | Django Ninja (auto-generated OpenAPI)         |
| Database       | PostgreSQL 16                                 |
| Cache / Broker | Redis                                         |
| Background     | Celery (Redis broker, periodic beat schedule) |
| Tests          | pytest + pytest-django                        |
| Quality gates  | Ruff + Mypy (strict) + migration check        |

## Quick start

```bash
# 1. Environment
cp .env.example .env          # then edit to taste
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt

# 2. Database (PostgreSQL must be running)
createdb whitebird
python manage.py migrate

# 3. Seed a demo tenant (admin / admin-password, plus staff users)
python manage.py seed_sites

# 4. Run
python manage.py runserver          # API + admin
celery -A config worker --loglevel=info      # async tasks
celery -A config beat --loglevel=info        # periodic stats refresh
```

Interactive API docs: `http://127.0.0.1:8000/api/v1/docs`
OpenAPI schema: `http://127.0.0.1:8000/api/v1/openapi.json`
Django admin: `http://127.0.0.1:8000/admin/`

## Development commands

```bash
python -m pytest                       # run the test suite
ruff check .                           # lint
mypy .                                 # static types (strict)
python manage.py makemigrations --check --dry-run   # pending migrations?
python manage.py seed_sites            # (re)seed demo data (idempotent)
```

## Documentation

- [`docs/setup.md`](docs/setup.md) — environment, configuration, deployment
- [`docs/architecture.md`](docs/architecture.md) — layered architecture and domain model
- [`docs/api.md`](docs/api.md) — API reference and authentication
