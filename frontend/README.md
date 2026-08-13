# White Bird Zanzibar — Frontend

This directory is reserved for the future **Vite + Lit** client that will
consume the Site Management API.

## Planned architecture

- **Build tool:** Vite
- **Components:** Lit (Web Components)
- **UI direction:** Material 2-inspired "light soft gold" theme — see
  `docs/THEME.md` for design tokens and rationale
- **Backend contract:** OpenAPI schema published by the Django backend at
  `/api/site-management/v1/openapi.json`

## Status

- [ ] Vite scaffold
- [ ] Lit component library
- [ ] API client (generated from OpenAPI)
- [ ] Auth flow (session/JWT)
- [ ] Dashboard shell
- [ ] CI pipeline

Nothing lives here yet by design — Prompt 1 is backend-foundation only.
