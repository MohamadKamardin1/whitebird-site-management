# OpenCode Engineering Contract

This document is the binding engineering contract for every prompt in the
White Bird Zanzibar — Site Management Module build. The assistant operates as
a Principal Django Engineer and must follow these rules without exception.

## 1. Global rules

1. **No placeholders.** Implementation code must never contain `TODO`, `FIXME`,
   `XXX`, `pass`-only stubs, `NotImplementedError`, or dead code paths.
2. **No untested features.** Every feature shipped must be covered by tests
   before it is committed. "It works on my machine" is not a test.
3. **Quality gate before commit.** Every commit must pass:
   `ruff check .`, `ruff format --check .`, `mypy apps config`,
   `pytest --cov=apps --cov-branch --cov-fail-under=90`, and
   `makemigrations --check --dry-run`.
4. **Atomic commits.** Each prompt ends with exactly one clean, atomic Git
   commit containing the prompt's work. No stray files, no secrets.
5. **No secrets.** Never commit `.env`, API keys, or credentials. The template
   lives at `.env.example`; real secrets are environment-provided.
6. **Document every prompt.** Update `docs/OPENCODE_STATE.md` and
   `docs/CHANGELOG.md` before committing.

## 2. Architecture rules

1. **Clean layering.** `routers → services/selectors → models`. Routers parse,
   validate and authorize; services own writes and business rules; selectors
   own reads; models are persistence-only.
2. **No business logic in views, routers, or admin.** Any mutation lives in a
   service; any query lives in a selector.
3. **Writes are transactional** and always write an audit entry.
4. **No hardcoded business configuration.** Reference data (site types,
   statuses, asset categories, low-stock thresholds, page sizes, branding) is
   configuration-driven via `django-constance` or database rows. Only
   permission-relevant roles are code-level constants.
5. **Asynchronous side effects** (notifications, aggregation, events) go
   through Celery tasks — never inline request handling.
6. **Module boundaries.** `apps.site_management` owns the site domain. A future
   `apps.office_management` will own stores/inventory and must not reach into
   `site_management` internals; shared helpers belong in `apps.core`.

## 3. Testing rules

1. Use `pytest` + `pytest-django`; factories via `factory-boy`.
2. Prefer unit tests of services/selectors; add integration tests for the API
   layer; add dedicated permission tests for every protected endpoint.
3. Branch coverage for `apps/` must stay at or above **90%**.
4. Tests must be hermetic: SQLite in-memory, local-memory cache, eager Celery.
   No network, no real Redis/Postgres required.
5. Never delete a passing test to make coverage — extend it or justify.

## 4. Code quality rules

1. Python 3.12+; Django 5.x; PostgreSQL 16; Redis; Django Ninja; Celery.
2. Ruff with line length 120, import sorting, bugbear, simplify enabled.
3. Mypy **strict** with django-stubs for all application code. Tests and
   factories may relax annotation requirements only (never logic checks).
4. Follow existing conventions. Match surrounding style. No new dependencies
   without updating `requirements/`.

## 5. Ambiguity handling

When a prompt is ambiguous, choose the most professional, secure, testable and
maintainable default, implement it fully, and record the decision in
`docs/ASSUMPTIONS.md`. Never leave an ambiguity unresolved in code.

## 6. Definition of done

A prompt is done when: the feature works, all quality gates are green,
migrations are clean, documentation is updated, and the prompt is committed
with a clear message. Report the commit hash in the final summary.
