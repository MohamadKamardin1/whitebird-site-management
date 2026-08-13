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
    migrations, tests, and `__init__.py` are excluded. Current coverage ~93%.
16. **Mypy strict** for app code; tests and factories relax only annotation
    requirements (factory-boy ships no type stubs), never logic checks.
17. **Factory-boy deprecation** (`skip_postgeneration_save`) is handled by
    saving in the password hook explicitly.

## Accounts (Prompt 2)

18. **Email is the login identifier.** `User` extends `AbstractBaseUser` +
    `PermissionsMixin` with `USERNAME_FIELD = "email"`; emails are stored
    lowercased for case-insensitive uniqueness. No `username` field.
19. **Roles are code constants** (`RoleCode`) with group-backed Django
    permissions. `seed_rbac` is idempotent; a `post_save` signal keeps each
    user in their role's group automatically.
20. **Token foundation is custom, secure, and documented** (no JWT library):
    stateless HMAC-signed access tokens (`django.core.signing`) plus revocable
    server-side refresh tokens (`ApiToken`). The `JWT_*` settings and
    `AUTH_MECHANISM` remain for a future PyJWT swap.
21. **Minimum password length 12**, plus common/numeric/similarity validators.
    Service-level creation and password changes run `validate_password`.
22. **django-axes `AXES_USERNAME_FORM_FIELD` is pinned to `"username"`** so the
    lockout matches how the API calls `authenticate(username=...)`. Axes
    auto-derives `"email"` from `USERNAME_FIELD`, which would break lockout.
23. **Hard deletion is guarded in the admin**: users with audit history,
    assignments, or tokens cannot be deleted; deactivation is the supported
    flow.
24. **Timezone middleware** activates the authenticated user's IANA timezone
    for the request and deactivates afterwards.
25. **Legacy test aliases**: `staff_user`→Management Viewer (read-only) and
    `manager_user`→Zone Supervisor (write-capable) preserve site-scoped test
    semantics from Prompt 1.

## Core kernel (Prompt 3)

26. **Audit schema redesigned** to `user/action/model_name/object_id/
    object_repr/before_data/after_data/ip_address/request_id`. The
    `record_audit` service keeps `actor` and `changes` as backward-compatible
    aliases; `create_site`/`update_site` now record real before/after JSON
    snapshots via `model_data()`.
27. **`AuditLog.summary` is kept** as an extra human-readable field beyond the
    spec's required list; it preserves existing call sites and aids triage.
28. **Private storage**: Django replaces `base_url=None` with `MEDIA_URL`, so
    `PrivateMediaStorage.url()` raises `ValueError` — no code path can produce
    a public URL. Files live under `PRIVATE_MEDIA_ROOT` (not served by
    WhiteNoise) and downloads go through signed tokens.
29. **File token permission model**: a valid signed token (owner + expiry)
    grants download; the endpoint additionally requires the request to be
    authenticated as the token owner or a system admin.
30. **Domain-event outbox** uses `transaction.on_commit`; events are only
    persisted when the producing transaction commits. No publisher exists yet.
31. **Cache keys** are namespaced under `wbz_site` with readable parts (no
    hashing); `invalidate_prefix` scans `wbz_site:{prefix}:*` on Redis.
32. **Error envelope** replaces the older `{"detail": ...}` responses:
    `{"error": {"code", "message", "trace_id", "fields"}}`. `trace_id` comes
    from the request-id contextvar.
33. **`CONSTANCE_DATABASE_CACHE_BACKEND` is disabled in tests** (local-memory
    cache is not cross-process), so constance values are read straight from
    the database.
34. **Request-id middleware** accepts a caller-provided `X-Request-ID` (via
    `HTTP_X_REQUEST_ID`) and echoes it back on the response; a
    `RequestIdFilter` injects it into every structured log line.
35. **HTTP 401 (missing/invalid token)** is emitted by Django Ninja's auth
    layer as `{"detail": "Unauthorized"}` and is not routed through our
    exception handlers; every *handled* error (400/403/404/409/422/500) uses
    the shared envelope.
