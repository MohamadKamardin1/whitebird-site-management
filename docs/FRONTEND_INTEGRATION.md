# Frontend Integration Guide

How the future **Vite + Lit** web app should consume the White Bird Zanzibar
Site Management API. The API is built with Django Ninja and exposes a generated
OpenAPI 3 document.

## Base URL & versioning

- Base path: `/api/site-management/v1`
- OpenAPI JSON: `/api/site-management/v1/openapi.json`
- Interactive docs (Swagger UI): `/api/site-management/v1/docs`
- All responses use JSON. Property names are **snake_case** (the OpenAPI
  document is the source of truth).

## Authentication

1. **Login** — `POST /auth/login` with `{email, password}` returns an
   `access_token` (short-lived, default 30 min, configurable via
   `ACCESS_TOKEN_TTL_SECONDS`) and a `refresh_token` (server-side, revocable,
   default 7 days via `REFRESH_TOKEN_TTL_SECONDS`).
2. **Authenticate** — send `Authorization: Bearer <access_token>` on every
   request. Access tokens are stateless signed tokens; refresh tokens are
   stored server-side and can be revoked.
3. **Refresh** — `POST /auth/refresh` with `{refresh_token}` returns a fresh
   `access_token`.
4. **Logout** — `POST /auth/logout` with `{refresh_token}` revokes the refresh
   token.
5. **Current user** — `GET /auth/me` returns the user profile;
   `GET /auth/me/permissions` returns the action/resource permission set the
   client should use to gate UI.

The admin/dashboard uses Django session auth; the API uses bearer tokens.
Both coexist.

## HTTP semantics

| Case                    | Status                          |
| ----------------------- | ------------------------------- |
| Success (create)        | `201` (new endpoints) / `200`   |
| Read / list / update    | `200`                           |
| Delete / no content     | `204`                           |
| Validation error        | `422`                           |
| Unauthorized (no/invalid token) | `401`                    |
| Forbidden (role/site)   | `403`                           |
| Not found               | `404`                           |
| Conflict                | `409`                           |
| Rate limited            | `429`                           |

## Error envelope

Every error response uses one shape:

```json
{
  "error": {
    "code": "validation_error",
    "message": "human readable message",
    "trace_id": "a1b2c3…",
    "fields": {}
  }
}
```

- `trace_id` is echoed in the `X-Request-ID` response header (and the
  `X-Request-ID` request header is honoured when supplied).
- `fields` maps field paths to lists of messages for `422` validation errors.

## Pagination

List endpoints paginate with `page` (1-based) and `page_size`
(capped by `MAX_PAGE_SIZE`, default 25). The response envelope is:

```json
{
  "count": 137,
  "next": "/api/site-management/v1/issues?page=2&page_size=25",
  "previous": null,
  "results": []
}
```

## Filtering & sorting

- Filters are **query parameters** and differ per domain, but consistently
  include: `site_id`, `zone_id` (where applicable), `date`/`date_from`/
  `date_to`, `status`, `priority`, `category`, and `search`.
- Sorting uses a whitelisted `ordering` query param: `ordering=field` or
  `ordering=-field`. Unknown fields are **ignored** (never an error, never an
  injection risk). The whitelist per endpoint is declared in the OpenAPI
  description.
- There are **no unbounded list endpoints** — everything is paginated.

## CORS

The API allows CORS for `/api/*` (see `CORS_URLS_REGEX`). In development,
`CORS_ALLOW_ALL_ORIGINS=True` so the Vite dev server (e.g. `localhost:5173`)
can call the API directly. In production set `CORS_ALLOWED_ORIGINS` to the
approved frontend origin.

## Throttling

The API is rate limited with a fixed-window limiter:

- Anonymous callers: `API_THROTTLE_ANON_RATE` (default `30/min`).
- Authenticated callers: `API_THROTTLE_AUTH_RATE` (default `300/min`).

Exceeding the limit returns `429` with the standard error envelope
(`code: "rate_limited"`). The web app should back off and surface a
"try again shortly" state rather than retrying in a tight loop.

## Frontend checklist (Vite + Lit)

1. Generate a typed API client from `/api/site-management/v1/openapi.json`
   (e.g. `openapi-typescript`) — the schema is complete and tagged by domain.
2. Store `access_token` in memory; persist `refresh_token` in a secure
   `HttpOnly`-equivalent store and rotate on `401` using `/auth/refresh`.
3. Add an interceptor that attaches the bearer token, reads `trace_id` from
   errors for support, and triggers the refresh flow on `401`.
4. Read brand identity from `GET /theme` (name + colours) to theme the shell.
5. Gate UI actions with `GET /auth/me/permissions` (actions/resources/site
   scope) and keep the management viewer read-only client-side as well.
6. Use the domain groups in the OpenAPI `tags` to organise client modules:
   Auth, Zones, Sites, Site Configuration, Cleaners, Assignments, Attendance,
   Trainees, Stores, Inspections, Issues & Jobs, Reports, Notifications, Theme,
   Dashboard.

## Domain endpoints

See `docs/API.md` for the full catalog grouped by domain.
