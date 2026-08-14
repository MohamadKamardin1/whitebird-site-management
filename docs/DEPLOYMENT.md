# Deployment

How to take the White Bird Zanzibar Site Management backend to production.

## 1. Prerequisites

- Docker with Compose v2 (recommended) or a bare host with Python 3.12,
  PostgreSQL 16 and Redis 7.
- A domain (or subdomain) for the API/admin and, when it ships, the Vite frontend.

## 2. Environment

Copy `.env.example` to `.env` and set (all required values fail the boot if
missing when using `config.settings.prod`):

| Variable                  | Required | Notes                                  |
| ------------------------- | -------- | -------------------------------------- |
| `DJANGO_SECRET_KEY`       | yes      | Long random value; rotate = token invalidation. |
| `DJANGO_ALLOWED_HOSTS`    | yes      | Comma-separated hosts.                 |
| `CSRF_TRUSTED_ORIGINS`    | yes      | Comma-separated origins (e.g. `https://app.whitebird.co.tz`). |
| `DJANGO_SETTINGS_MODULE`  | yes      | `config.settings.prod` in production.  |
| `DATABASE_URL`            | yes      | `postgres://user:pass@host:5432/whitebird`. |
| `REDIS_URL`               | yes      | `redis://host:6379/0`.                 |
| `CELERY_BROKER_URL`       | yes      | `redis://host:6379/1`.                 |
| `CELERY_RESULT_BACKEND`   | yes      | `redis://host:6379/1`.                 |
| `CORS_ALLOWED_ORIGINS`    | yes      | Frontend origin(s).                    |
| `EMAIL_HOST*` / `DEFAULT_FROM_EMAIL` | yes | Transactional email.          |
| `SENTRY_DSN`              | optional | Enables Sentry error tracking.         |
| `CSP_ENABLED`             | optional | Content-Security-Policy header (default on). |
| `API_DOCS_ENABLED`        | optional | Off by default in production.          |

## 3. Build & run (Docker Compose)

```bash
cp .env.example .env
docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml exec web python manage.py migrate
docker compose -f docker-compose.prod.yml exec web python manage.py seed_rbac
docker compose -f docker-compose.prod.yml exec web python manage.py seed_demo   # optional
```

Services: `db`, `redis`, `web` (Gunicorn), `worker` (Celery), `beat`
(Celery Beat with the DB scheduler). Persistent volumes: `postgres_data`,
`redis_data`, `staticfiles`, `private_media`.

## 4. Reverse proxy

Terminate TLS at the proxy (nginx/Caddy/ALB) and forward to the `web` service on
`:8000` with `X-Forwarded-Proto: https` (the app trusts it for SSL redirects).
Serve `/static/` via the proxy or Whitenoise from the container.

## 5. Bare-host run

```bash
python manage.py migrate --noinput
python manage.py collectstatic --noinput
gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 3 --timeout 60
celery -A config worker --loglevel=info
celery -A config beat --loglevel=info
```

## 6. Backups

`scripts/backup_db.sh` and `scripts/backup_media.sh` produce timestamped
archives; see `scripts/restore_notes.md` for restore steps. Schedule them via
cron:

```cron
0 2 * * * /opt/whitebird/scripts/backup_db.sh /var/backups/whitebird
30 2 * * * /opt/whitebird/scripts/backup_media.sh /var/backups/whitebird
```

## 7. CI/CD

`.github/workflows/ci.yml` runs Ruff, Mypy, the migration check, and pytest with
the 90% coverage gate, plus a production Docker build, on every push/PR.
