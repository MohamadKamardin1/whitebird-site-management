# Assumptions & Decisions

Every assumption chosen while resolving ambiguity, recorded per the
engineering contract.

## Environment

1. **Python 3.14 at runtime; target 3.12.** The development machine has
   Python 3.14.5 only (no 3.12 installed). All code targets `>=3.12` and
   Docker uses `python:3.12-slim`, so production runs exactly 3.12 while the
   local toolchain runs 3.14.
2. **PostgreSQL and Redis run locally** (`127.0.0.1`); Docker Compose is
   provided for the same stack but could not be executed here because Docker
   is not installed on this machine. Compose YAML is validated by parsing;
   the image is untested until run in a Docker environment.
3. **django-environ defaults** assume a local `postgres/postgres` superuser on
   `whitebird`; override via `.env`.

## Scope & carry-forward

4. **The `site_management` module is carried forward from earlier scaffolding.**
   Prompt 1 requests empty app skeletons, but the working tree already
   contained a fully implemented, tested site domain. Rather than delete
   tested code (violating "no untested features" / "no dead code"), the module
   was restructured into `apps.site_management` and retained. Subsequent
   prompts should build on it rather than rebuild it.
5. **Accounts (users, roles, API tokens) are infrastructure**, not business
   modules, and are implemented now so later prompts have a real auth base.
6. **No business modules** (attendance, shifts, tasks, inspections, issues,
   jobs, stores) are implemented in this prompt — they are specified in
   `DOMAIN.md` and `RBAC.md` for later prompts.

## Architecture

7. **Permission roles are code constants** (`Role`, `AssignmentRole`).
   Authorization must be verifiable in code; only *reference data* (site
   types, statuses, categories, thresholds, branding) is configuration-driven.
8. **`PATCH /sites/{id}` treats `null` fields as "keep current"**; clearing an
   optional field is done through the admin until explicit set-null semantics
   are requested.
9. **Django Ninja returns HTTP 200 for successful POST** in this version;
   responses use 200/201 consistency as the framework provides.
10. **`AUTH_MECHANISM` defaults to `session`**; JWT is pre-configured
    (`JWT_*`) but not installed, per the roadmap.
11. **django-axes is active in dev/prod** and requires the `request` object in
    `authenticate`; the login service forwards the request so API logins are
    throttled too.

## Runtime configuration

12. **`MAX_SITE_SUPERVISORS_PER_SITE` default 2**, `LOW_STOCK_DEFAULT` 5,
    page size 25 (max 100), dashboard/report cache TTLs 300/600s, file token
    TTL 900s, domain events off, notifications on. All editable in the admin
    via django-constance.
13. **The default periodic task** (site statistics refresh) is registered into
    the Celery Beat *database* scheduler idempotently on migrate, so the
    schedule is admin-editable.

## Media

14. **Private media root** (`private_media/`) is separate from public static;
    `public_media/` is reserved. WhiteNoise serves static only. Signed file
    tokens are a later milestone (`FILE_TOKEN_TTL_SECONDS`).

## Quality

15. **Coverage gate 90% branch** applies to `apps/` application code;
    migrations, tests, and `__init__.py` are excluded. Current coverage ~95%.
16. **Mypy strict** for app code; tests and factories relax only annotation
    requirements (factory-boy ships no type stubs), never logic checks.
17. **Factory-boy deprecation** (`skip_postgeneration_save`) is handled by
    saving in the password hook explicitly.
