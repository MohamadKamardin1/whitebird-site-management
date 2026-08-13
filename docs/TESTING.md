# Testing Strategy

## Stack

- `pytest` + `pytest-django`
- `factory-boy` for data factories (`apps/accounts/factories.py`,
  `apps/site_management/factories.py`)
- `pytest-mock` for focused patching
- `pytest-cov` with **branch coverage**, gate at **90%** for `apps/`
- `pytest-xdist` available for parallel runs

## Hermetic by default

Test settings (`config.settings.test`) never touch external services:

- SQLite in-memory database
- local-memory cache
- eager Celery (`CELERY_TASK_ALWAYS_EAGER = True`) with errors propagated
- console/locmem email backend
- django-axes disabled
- fast password hashing

This makes the suite deterministic, fast, and CI-friendly.

## Test taxonomy

| Level        | Scope                                                       | Examples |
| ------------ | ---------------------------------------------------------- | -------- |
| Unit         | Models, services, selectors, cache helpers, managers       | `test_services.py`, `test_utils.py` |
| Integration  | API endpoints end-to-end via the test client               | `test_api.py`, `test_auth.py` |
| Permission   | Role/site-scope denials for every protected endpoint       | `test_auth_scheme.py`, permission assertions in `test_api.py` |
| Task         | Celery task behaviour in eager mode                        | `test_tasks.py`, `test_beat_schedule.py` |
| View         | Host-facing views (`/healthz`, `/readyz`, landing)         | `apps/web/tests/test_views.py` |

## Factories

`factory-boy` factories mirror the models so tests read clearly:

```python
site = SiteFactory(status=SiteStatusFactory(slug="active"))
user = UserFactory(role=Role.MANAGER, password="S3cure-pass")
```

## Naming and layout

- One `tests/` package per app, `test_<area>.py` files.
- Shared fixtures live in `apps/conftest.py` (users, authed clients, a base
  site, an autouse cache-clear to keep the local-memory cache hermetic).

## Commands

```bash
make test        # full suite + branch coverage, 90% gate
make test-fast   # tests without coverage
```

## Coverage expectations

- **Gate:** `apps/` ≥ 90% branch coverage (currently ~95%).
- New code must arrive with tests; the gate is enforced by `make quality`.
- Excluded from coverage: migrations, test code itself, `__init__.py`.
