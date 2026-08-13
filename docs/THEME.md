# Theme — Design Direction

## Summary

A **Material 2-inspired "light soft gold"** theme for the custom Jazzmin admin
and the future Vite + Lit frontend. Warm, calm, professional — suited to a
premium coastal hospitality platform.

## Design tokens

Brand values are runtime-configurable via `django-constance` and mirrored in
the Jazzmin settings so the admin and (future) frontend stay in sync.

| Token                     | Default     | Constance key                |
| ------------------------- | ----------- | ---------------------------- |
| Brand name                | White Bird Zanzibar | `BRAND_NAME`       |
| Primary colour            | `#9c7c38`   | `BRAND_PRIMARY_COLOR`        |
| Accent colour             | `#c9a96e`   | `BRAND_ACCENT_COLOR`         |
| Background colour         | `#f7f3ea`   | `BRAND_BACKGROUND_COLOR`     |

The palette is a warm neutral base with a muted gold accent — low-contrast,
easy on the eyes for operations staff who live in the dashboard.

## Jazzmin admin

- Jazzmin sits **before** `django.contrib.admin` in `INSTALLED_APPS`.
- `JAZZMIN_SETTINGS` configure branding, sidebar, icons, and the UI tweaks.
- `JAZZMIN_UI_TWEAKS` use the `materia` theme with a light navbar and a
  soft-warning (gold) accent for active states.
- A tiny custom stylesheet (`static/css/admin.css`) exposes the CSS variables
  `--wb-primary`, `--wb-accent`, `--wb-background` for overrides.
- Constance adds a "Configuration" admin page for runtime settings; Celery
  Beat schedules are managed in the admin too.

## Future Vite + Lit frontend

- The `frontend/` directory is reserved; see `frontend/README.md`.
- The frontend must consume the OpenAPI schema published by the backend and
  honour the same tokens, so the look stays consistent.
- Web Components (Lit) allow the dashboard to compose reusable widgets
  (site cards, stats, notification tray) without a heavy framework lock-in.
- CORS is pre-configured (`CORS_ALLOWED_ORIGINS`) so the Vite dev server can
  call the API directly; `CSRF_TRUSTED_ORIGINS` is ready for session flows.
