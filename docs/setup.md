# Setup & Configuration

## Environment

All configuration is environment-driven. Copy `.env.example` to `.env` and
adjust. The following variables matter most:

| Variable                  | Purpose                                             |
| ------------------------- | --------------------------------------------------- |
| `DJANGO_SETTINGS_MODULE`  | `config.settings.dev`, `config.settings.test`, or `config.settings.prod` |
| `DJANGO_SECRET_KEY`       | **Required in production.** Never commit real keys. |
| `DJANGO_DEBUG`            | Boolean; defaults to `true` (dev)                   |
| `POSTGRES_*`              | PostgreSQL connection (`whitebird` DB by default)   |
| `REDIS_URL`               | Redis used for cache + Celery result backend        |
| `CELERY_BROKER_URL`       | Redis broker for Celery (separate DB number advised)|
| `SITE_STATS_SCHEDULE_SECONDS` | Cadence of the periodic stats refresh (default 900) |

### Settings profiles

- `config.settings.base` — shared settings consumed by every profile.
- `config.settings.dev` — relaxed security, console email, superuser seed defaults.
- `config.settings.test` — SQLite in-memory, local-memory cache, eager Celery;
  used automatically by pytest.
- `config.settings.prod` — locked-down posture: SSL redirect, secure cookies,
  HSTS; **refuses to start** without `DJANGO_SECRET_KEY` and `DJANGO_ALLOWED_HOSTS`.

## Local services

- **PostgreSQL 16** — create the database: `createdb whitebird`.
- **Redis** — any recent version; used for the Django cache and Celery broker.

## Running the stack

```bash
python manage.py migrate
python manage.py seed_sites            # optional demo data
python manage.py runserver             # API + admin at :8000
celery -A config worker --loglevel=info
celery -A config beat --loglevel=info
```

## Deployment notes

1. Use `DJANGO_SETTINGS_MODULE=config.settings.prod`.
2. Terminate TLS at a reverse proxy and send `X-Forwarded-Proto: https`
   (`SECURE_PROXY_SSL_HEADER` is already configured).
3. Run one or more Celery workers plus a single beat scheduler.
4. Apply migrations as part of the release; run `collectstatic`.
5. Rotate API tokens via the admin; tokens are revocable (soft) and can be
   given an expiry at issuance.

## Quality gates (CI)

The repository is gated on four checks, all green in CI:

```bash
python -m pytest
ruff check .
mypy .
python manage.py makemigrations --check --dry-run
```
