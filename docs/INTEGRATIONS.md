# External Integrations

Provider engines for **DeepSeek** (LLM) and **Mapbox** (geocoding), living in
`apps/integrations`. Both engines are provider-transport-only; business
use-cases sit in `apps/integrations/services.py`, asynchronous work in
`apps/integrations/tasks.py`, and the HTTP surface in `apps/integrations/api.py`.

## Key safety

- Keys are read from the environment only (settings, never the DB/constance,
  never committed).
- Keys are sent only in request headers/query params; they are **never** logged,
  included in exception messages, or returned in API payloads.
- Provider errors are normalised to the standard error envelope
  (`{"error": {code, message, trace_id, fields}}`) with status `502`, or `503`
  when the integration is not configured.

## DeepSeek engine

Wraps the DeepSeek chat-completions API.

- `deepseek.enabled()` / `complete_chat(messages, ...)` / `summarize(text, ...)`.
- Config: `DEEPSEEK_ENABLED`, `DEEPSEEK_API_KEY`, `DEEPSEEK_BASE_URL`,
  `DEEPSEEK_MODEL`, `DEEPSEEK_TIMEOUT_SECONDS`, `DEEPSEEK_MAX_TOKENS`,
  `DEEPSEEK_MAX_RETRIES`.
- Bounded retries with backoff; malformed responses raise `ProviderError`.
- Use-case: `summarize_site_report(report)` — an executive bullet summary of a
  daily site report; gracefully returns `None` when disabled.

**API**: `POST /api/site-management/v1/ai/summarize`
`{text, instruction?}` → `{summary}` (management roles only; `503` when
disabled).

**Task**: `apps.integrations.tasks.summarize_site_report(report_id)` (idempotent,
retries transient failures).

## Mapbox engine

Wraps Mapbox forward/reverse geocoding with result caching.

- `mapbox.enabled()` / `geocode(query)` / `reverse_geocode(lng, lat)`.
- Config: `MAPBOX_ENABLED`, `MAPBOX_API_KEY`, `MAPBOX_GEOCODING_URL`,
  `MAPBOX_TIMEOUT_SECONDS`, `MAPBOX_MAX_RETRIES`, `MAPBOX_GEOCODE_CACHE_TTL`.
- Forward/reverse lookups are cached under a namespaced key
  (`wbz:geo:...`) so repeat calls never hit the network.
- Use-case: `geocode_site(site)` — geocodes a site's name/city/region/country and
  persists its `latitude`/`longitude`; raises `ValidationError` when Mapbox
  returns no coordinates.

**API**:
- `GET /api/site-management/v1/geo/geocode?q=Nungwi` → `{name, place_name, longitude, latitude}`
- `GET /api/site-management/v1/geo/reverse?lng=39.2&lat=-5.7` → feature

Both are read-only (management or viewer). `503` when disabled.

**Task**: `apps.integrations.tasks.geocode_site(site_id)` (idempotent).

## Architecture notes

- `apps/integrations/transport.py` — the single HTTP helper: bounded retries,
  timeouts, `httpx.MockTransport` injection for hermetic tests.
- Engines never import Django models; services map provider results into the
  domain. All tests are hermetic (no real network).
