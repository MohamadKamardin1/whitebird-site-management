# OpenCode Build State

Track of the 20-prompt build of the White Bird Zanzibar — Site Management
Module. Each prompt updates this file before its commit.

## Progress

| Prompt | Title                                        | Status             | Commit       |
| ------ | -------------------------------------------- | ------------------ | ------------ |
| 1      | Scaffold premium Django foundation           | **Prompt 1 completed** | see CHANGELOG |
| 2–20   | (pending)                                    | —                  | —            |

## Prompt 1 — completed ✅

Delivered the premium foundation:

- Split settings (`base`/`dev`/`test`/`prod`) via django-environ
- Custom user model + roles + API tokens + bearer auth + django-axes
- Django Ninja API at `/api/site-management/v1` (OpenAPI + Swagger)
- Celery + `django-celery-beat` (database scheduler), Redis broker/cache
- Jazzmin admin with branding + django-constance runtime configuration
- WhiteNoise static, private media root, CORS/CSRF from env, structured logging
- Host probes `/healthz`, `/readyz`, landing redirect to `/admin/`
- Docker (Dockerfile, compose, entrypoint, wait-for-db), Makefile, pre-commit
- `apps/core`, `apps/accounts`, `apps/site_management`, `apps/web`
- Split requirements, factories, 96 tests at ~95% branch coverage
- Full docs set (contract, architecture, domain, RBAC, API, theme, testing,
  performance, assumptions, changelog)

**Quality gates (all green):** Ruff · Mypy strict · pytest 96 passed ·
coverage ≥ 90% · `makemigrations --check` clean.
