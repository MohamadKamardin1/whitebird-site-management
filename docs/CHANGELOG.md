# Changelog

All notable changes to the White Bird Zanzibar — Site Management Module.

The format follows [Keep a Changelog](https://keepachangelog.com/); versions
map to build prompts.

## [Prompt 01] — 2026-08-13

### Added

- Split settings profile (`base` / `dev` / `test` / `prod`) powered by
  `django-environ`.
- Custom `accounts.User` with platform roles; `ApiToken` bearer authentication;
  django-axes brute-force protection.
- Django Ninja API at `/api/site-management/v1` with OpenAPI/Swagger docs,
  a Django `ValidationError → 422` handler, and versioned routers.
- Celery application (`config/celery_app.py`) with `django-celery-beat`
  database scheduler and an idempotently-registered periodic stats task.
- Redis-backed cache (`django-redis`), WhiteNoise static compression, private
  media root, CORS/CSRF from environment, structured JSON console logging.
- Jazzmin admin with branding plus `django-constance` runtime configuration
  (branding colours, page sizes, cache TTLs, thresholds, feature flags).
- Host probes `/healthz` and `/readyz`, landing redirect to `/admin/`.
- `apps.core` (audit log, soft-delete, cache helpers, typed request),
  `apps.web` (probes), and the carried-forward `apps.site_management`.
- Docker foundation: `Dockerfile` (python:3.12-slim, non-root),
  `docker-compose.yml` (db/redis/web), entrypoint + wait-for-db.
- Tooling: `Makefile`, `.pre-commit-config.yaml`, split `requirements/`.
- Test foundation: factory-boy factories, 96 tests at ~95% branch coverage.
- Documentation set: contract, architecture, domain, RBAC, API, theme,
  testing, performance, assumptions, state, changelog.

### Fixed

- Django `ValidationError` now maps to HTTP 422 instead of a 500.
- Axes-compatible login: `authenticate(request=...)` forwarded from the API.
