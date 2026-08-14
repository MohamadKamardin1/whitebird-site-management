# Security

The security posture of the White Bird Zanzibar Site Management backend.

## Authentication

- **Bearer API tokens**: short-lived signed access tokens
  (`ACCESS_TOKEN_TTL_SECONDS`) + revocable server-side refresh tokens
  (`REFRESH_TOKEN_TTL_SECONDS`); `/auth/logout` revokes the refresh token.
- **Session auth** for the admin/dashboard only; brute-force protection via
  django-axes (lockout by email + IP).
- Login identifier is email; passwords validated by Django validators
  (min length 12, common-password and numeric checks).

## Authorization

- **Central policy layer** (`apps/site_management/policies.py`): every
  read/write decision flows through object-level predicates; services raise
  `ForbiddenActionError` (403) for out-of-scope actors.
- **Data scoping**: all selectors restrict to `visible_sites`/`visible_zones`
  (site supervisor = assigned sites, zone supervisor = assigned zones,
  AGS = assigned/all zones, GS/admin = all).
- **Management viewer** is read-only across the API and admin.
- **Admin hardening**: `ScopedAdminMixin` scopes `get_queryset` by role and
  blocks add/change/delete for viewers.

## Transport & headers (production)

- `SECURE_SSL_REDIRECT`, HSTS (`SECURE_HSTS_SECONDS` + subdomains + preload),
  secure cookies, `SESSION_COOKIE_HTTPONLY`, `CSRF_COOKIE_HTTPONLY`,
  `SECURE_CONTENT_TYPE_NOSNIFF`, `X_FRAME_OPTIONS=DENY`,
  `SECURE_REFERRER_POLICY`.
- **Content-Security-Policy** via `SecurityHeadersMiddleware`
  (`CSP_ENABLED`, configurable `CSP_*_SRC`; default allows same-origin plus the
  Chart.js CDN).
- **CORS** restricted to `CORS_ALLOWED_ORIGINS` (dev allows all local origins).
- **API docs** are off by default in production (`API_DOCS_ENABLED`).

## Request security

- **CSRF** enforced on all session forms (admin/dashboard).
- **API throttling** (`apps/core/throttling.py`): anonymous
  `API_THROTTLE_ANON_RATE`, authenticated `API_THROTTLE_AUTH_RATE`; 429 with the
  standard error envelope.
- **Upload limits** enforced (`MAX_UPLOAD_MB`, extension whitelist) for private
  files.
- **SQL injection**: all queries go through the Django ORM (no raw SQL in app
  code); whitelisted `ordering` prevents injection.
- Every response carries `X-Request-ID`; errors include `trace_id`.

## Data protection

- **Private files** live on a private storage backend (no public URL) and are
  only served through short-lived signed tokens (`FILE_TOKEN_TTL_SECONDS`,
  owner-or-admin). Signed URLs carry no DB rows — rotation of
  `DJANGO_SECRET_KEY` expires them.
- **PII masking**: cleaner ID/phone numbers masked in list APIs unless the
  caller holds `view_sensitive_cleaner_documents`; document downloads audited.
- **Exports** are scoped, audited (`FILE_DOWNLOAD`), capped
  (`EXPORT_MAX_ROWS`) and sanitised against CSV formula injection.

## Operations

- Secrets live in environment variables; `.env` is gitignored. No secrets in
  code or repositories.
- Dependency versions are pinned in `requirements/*.txt`.
- No debug toolbar in production; `DEBUG=False` enforced by `prod.py`.
- Sentry optional (`SENTRY_DSN`, `send_default_pii=False`); logs are structured
  and free of PII.
