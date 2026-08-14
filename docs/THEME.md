# Theme — Design Direction & Implementation

## Summary

A **Material 2-inspired "light soft gold"** theme for the custom Jazzmin admin
and the future Vite + Lit frontend. Warm, calm, professional — suited to a
premium coastal hospitality platform.

## Design tokens

Brand values are runtime-configurable via `django-constance` (`BRAND_*`),
injected into every template as CSS variables by a context processor
(`apps/core/context_processors.brand`), and mirrored in the Jazzmin settings so
the admin and (future) frontend stay in sync. CSS always declares `var(...)`
with sane fallbacks.

| Token                     | Default     | Constance key                |
| ------------------------- | ----------- | ---------------------------- |
| Brand name                | White Bird Zanzibar | `BRAND_NAME`       |
| Primary colour            | `#A47C00`   | `BRAND_PRIMARY_COLOR`        |
| Accent colour             | `#C9A227`   | `BRAND_ACCENT_COLOR`         |
| Background colour         | `#FBF7EF`   | `BRAND_BACKGROUND_COLOR`     |

Supporting palette (fixed in the stylesheet): surface `#FFFDF8`, sidebar
`#FFF9EC`, text `#231A05` / secondary `#6B5B33`, success `#2E7D32`, warning
`#B26A00`, error `#B3261E`, border `#EADFC3`.

## Jazzmin admin

- Jazzmin sits **before** `django.contrib.admin` in `INSTALLED_APPS`.
- `JAZZMIN_SETTINGS` configure: `site_logo` (`images/logo.svg`), welcome sign,
  copyright, icon set for every model, `order_with_respect_to` (clean sidebar
  order), `topmenu_links` (Dashboard, API Docs, OpenAPI JSON, Settings),
  `custom_links` (Zones, Sites, Cleaners, Attendance, Trainees, Stores,
  Inspections, Issues, Jobs, Reports, Audit Logs, Users), hidden system models,
  `changeform_format` (horizontal tabs), `custom_css`/`custom_js`.
- `JAZZMIN_UI_TWEAKS` use the `materia` theme, a light navbar and a
  soft-warning (gold) accent; filled primary/success/danger buttons.
- A context processor injects `brand` (name + colours + version) so
  `admin/base_site.html` and `admin/login.html` render live brand values.
- Templates override `admin/base_site.html` (CSS variable injection + favicon
  + `whitebird_admin.css`) and `admin/login.html` (premium centred card).

## Custom templates & static assets

- `templates/admin/base_site.html` — injects `:root` brand variables, loads
  `whitebird_admin.css` and the favicon, restyles branding + user links.
- `templates/admin/login.html` — self-contained premium login: centred card on
  a soft gold radial gradient, brand logo + name, material inputs, styled
  errors, forgot-password link, accessible labels/focus.
- `templates/404.html`, `403.html`, `500.html` — branded error pages.
- `templates/base.html` (web) — brand variables + favicon + design system.
- `static/css/material_soft_gold.css` — the full Material Soft Gold design
  system (CSS variables, cards `12–16px` radius, soft shadows/elevation,
  tables, buttons, status badges, forms, sidebar polish, focus states,
  responsive breakpoints). Loaded via `JAZZMIN_SETTINGS["custom_css"]`.
- `static/css/whitebird_admin.css` — admin-specific polish (readonly clarity,
  inline forms, search/toolbar, pagination, breadcrumbs, object tools).
- `static/js/whitebird_admin.js` — small helper that badgeifies status/priority
  columns with themed chips (no inline JS).
- `static/images/logo.svg` — brand mark (soft gold gradient bird).
- `static/images/favicon.svg` — brand favicon.

## Theme API

`GET /api/site-management/v1/theme` returns the brand payload for the future
Vite + Lit frontend:

```json
{
  "brand_name": "White Bird Zanzibar",
  "brand_primary_color": "#A47C00",
  "brand_accent_color": "#C9A227",
  "brand_background_color": "#FBF7EF",
  "logo_url": "/static/images/logo.svg",
  "version": "1.0.0"
}
```

Values come from constance (with fallbacks) and are cached briefly
(`report`-style TTL). CORS is pre-configured so the Vite dev server can call
the API directly; the frontend should honour the same tokens so the look stays
consistent. See `docs/FRONTEND_INTEGRATION.md`.
