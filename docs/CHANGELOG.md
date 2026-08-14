# Changelog

All notable changes to the White Bird Zanzibar — Site Management Module.

The format follows [Keep a Changelog](https://keepachangelog.com/); versions
map to build prompts.

## [Prompt 17] — 2026-08-14

### Added

- **Jazzmin configuration**: expanded `JAZZMIN_SETTINGS` — brand logo/welcome/
  copyright, icon set for every model, sidebar `order_with_respect_to`,
  `topmenu_links` (Dashboard, API Docs, OpenAPI JSON, Settings), `custom_links`
  (Zones, Sites, Cleaners, Attendance, Trainees, Stores, Inspections, Issues,
  Jobs, Reports, Audit Logs, Users), hidden system models, horizontal-tab
  change forms, `custom_css`/`custom_js`; `JAZZMIN_UI_TWEAKS` with the
  `materia` theme, light navbar, gold accent and filled action buttons.
- **Brand context processor** (`apps.core.context_processors.brand`) injecting
  constance `BRAND_*` values + version into every template as CSS variables.
- **Custom templates**: premium `admin/login.html` (centred card, soft-gold
  radial gradient, brand logo, material inputs, styled errors, forgot-password
  link), `admin/base_site.html` (brand variables, favicon, `whitebird_admin.css`,
  branded header + user links), branded `404/403/500` error pages, and web
  `base.html` brand wiring.
- **Static assets**: `material_soft_gold.css` (full Material Soft Gold design
  system — variables, cards, shadows, tables, buttons, badges, forms, sidebar,
  focus states, responsive), `whitebird_admin.css` (admin polish), the small
  `whitebird_admin.js` badge helper, `logo.svg`, and `favicon.svg`.
- **Theme API**: `GET /theme` now returns `logo_url` and `version` alongside
  the brand palette (constance-backed, briefly cached).
- **Tests** (`apps/web/tests/test_admin_theme.py`): branded login page,
  stylesheet/favicon loading, essential links on the admin index, admin
  requires staff, theme payload, branded error page, login still works.

### Changed

- `API_VERSION` setting added (used by theme payload and branding).
- `docs/THEME.md` rewritten as the design-direction + implementation guide.

## [Prompt 16] — 2026-08-14

### Added

- **Database**: composite indexes (migration `0012`) for attendance date+status,
  issue status/priority/due_date, job assignee/status, store stock scans,
  cleaner document status/type, and report date+status; `CheckConstraint`s for
  movement quantity, item stock non-negativity and request quantities.
- **Query optimisation**: cleaner list verified-ID flag via `Exists` subquery
  (kills N+1); `get_all_site_stats` collapsed to a single annotated aggregate
  (was 4N queries).
- **Caching**: namespaced read-through caches for the cross-site KPI overview
  (`kpi`, exact-key invalidation), the report status dashboard (`report:status`,
  prefix invalidation), and theme metadata (`theme`); TTLs from
  constance/settings; DB fallback via `cached_or`; write-path lookups stay
  uncached.
- **Exports**: streaming CSV export `GET /issues/export`
  (`StreamingHttpResponse` + `iterator(chunk_size=500)`), guarded by
  `can_export_data`.
- **Load readiness**: `seed_volume` management command (zones/sites/cleaners/
  attendance 30 days/inspections/issues/jobs/store data, bulk-created,
  idempotent per `--run-tag`) and `benchmark` command (per-selector timing +
  query counts, warns and exits non-zero on slowness).
- **Performance tests** (`test_performance.py`): query-count tests for cleaner
  list, issue list, store list, inspection summary; cache-hit tests (KPI,
  report dashboard, theme); cache invalidation test; pagination sanity; CSV
  export; `seed_volume` smoke test.
- **Docs**: `docs/PERFORMANCE.md` extended with indexes/constraints, cache
  strategy table, query-optimisation patterns, volume/benchmark instructions
  and production tuning recommendations.

## [Prompt 15] — 2026-08-14

### Added

- **Central policy layer** `apps/site_management/policies.py`: 25 object-level
  predicates (`can_view_site`, `can_edit_site`, `can_view_cleaner`,
  `can_edit_cleaner`, `can_view_assignment`, `can_edit_assignment`,
  `can_record_attendance`, `can_review_attendance`, `can_manage_store`,
  `can_view/create/review_inspection`, `can_view/edit_issue`,
  `can_assign/verify_job`, report policies, `can_export_data`, ...) plus an
  `ensure(...)` guard that raises `ForbiddenActionError`.
- **Service hardening**: report workflow (submit/return/review site report,
  submit zone/assistant/general), job assign/verify/complete, inspection
  review/return, and attendance record/review/return services now raise
  `ForbiddenActionError` for actors outside their role/site scope.
- **Admin hardening**: `ScopedAdminMixin` applied to all data-bearing
  ModelAdmins — `get_queryset` restricted to `visible_sites`/`visible_zones`
  for non-superuser/non-GS admins; management viewer can view but never
  add/change/delete; zone-based/nested-site scope overrides (StoreItem via
  `store__site`, Cleaner via `site_assignments`, InspectionTemplate global +
  scoped).
- **Permission test suite** (`apps/site_management/tests/test_permissions.py`):
  every major policy parametrized over all six roles; cross-site/cross-zone
  denials; service `ForbiddenActionError` guards; admin queryset scoping and
  viewer read-only; API cross-scope denial.
- **Docs**: `docs/RBAC.md` now contains the complete permission matrix
  (resources × roles, read/write/submit/review/approve/export) plus the policy
  layer and admin-hardening descriptions.

## [Prompt 14] — 2026-08-14

### Added

- **Theme endpoint** `GET /theme`: brand name + primary/accent/background
  colours from constance for frontend theming.
- **`/auth/me/permissions`**: action/resource permission set (mirrors the
  mobile `PermissionSet` contract) for client-side UI gating.
- **OpenAPI polish**: every operation is grouped under a domain tag
  (Auth, Zones, Sites, Site Configuration, Cleaners, Assignments, Attendance,
  Trainees, Stores, Inspections, Issues & Jobs, Reports, Notifications, Theme,
  Dashboard); Bearer security scheme documented; docs and `openapi.json` gated
  by `API_DOCS_ENABLED`.
- **Consistent error envelope for all statuses**: 401/403/422/429 now use the
  shared `{"error": {code, message, trace_id, fields}}` envelope (Ninja
  `AuthenticationError`/`AuthorizationError`/`ValidationError`/`Throttled`
  handlers); every response carries `X-Request-ID`.
- **Whitelisted sorting** (`ordering`) on the issue, job, inspection, store,
  trainee, cleaner, and site-report list endpoints via `apply_ordering`.
- **API rate limiting**: fixed-window middleware (`apps/core/throttling.py`)
  with configurable `API_THROTTLE_ANON_RATE`/`API_THROTTLE_AUTH_RATE`/
  `API_THROTTLE_ENABLED`, returning `429` with the standard envelope.
- **Contract tests** (`apps/core/tests/test_api_contract.py`): OpenAPI schema
  generation + tags + responses, docs page, pagination envelope + page-size
  cap, ordering whitelist (injection-safe), error shapes (401/404/422), auth
  flow (login/refresh/logout/me/me-permissions), management-viewer read-only,
  throttling 429, theme endpoint, request-id header.

### Changed

- Documented API standards: snake_case JSON, HTTP status codes (201/204/409/
  429), pagination, filtering/sorting, CORS, throttling, and frontend guidance
  in `docs/API.md` and the new `docs/FRONTEND_INTEGRATION.md`.

## [Prompt 13] — 2026-08-14

### Added

- **`DailySiteReport`**: per-site daily report aggregating real operational
  data (attendance, store, inspections, trainees, issues) with per-domain JSON
  fields, immutable `snapshot` on submission, and the full status chain
  (DRAFT → SUBMITTED → RETURNED → ZONE_REVIEWED → ASSISTANT_REVIEWED →
  GENERAL_APPROVED → MANAGEMENT_SUBMITTED).
- **`ZoneSummaryReport`**: zone roll-up of its site reports with
  `issues_extracted` and site-report snapshots; DRAFT → SUBMITTED → RETURNED →
  ASSISTANT_REVIEWED.
- **`AssistantGeneralSummaryReport`**: cross-zone summary with
  `problems_extracted`; DRAFT → SUBMITTED → RETURNED → GENERAL_REVIEWED.
- **`GeneralManagementReport`**: final management output with `key_issues` and
  `assigned_jobs`; DRAFT → SUBMITTED_TO_MANAGEMENT.
- **Services** (transactional + audited): generate/submit/return/review for
  every level, `recalculate_report_snapshots`; site reports aggregate real
  data and store an immutable snapshot on submit; return flow preserves
  history; report caches invalidated; domain events `SiteReportSubmitted`,
  `ZoneReportSubmitted`, `AssistantReportSubmitted`, `GeneralReportSubmitted`.
- **Selectors**: report details at each level, `missing_site_reports`,
  `reporting_status_dashboard` (per-site statuses + chain status).
- **API**: `/reports/site` (list/detail/generate/submit/return),
  `/reports/zone` (list/generate/submit/return), `/reports/assistant`
  (list/generate/submit/return), `/reports/general` (list/generate/submit),
  `/reports/status`, `/reports/missing`; read = management/viewer,
  site report manage = site scope, zone review/summary = zone supervisor+,
  assistant authoring = AGS/GS, general authoring = GS.
- **Admin**: reporting admin for all four levels with status badges, readonly
  JSON snapshots, date hierarchy, submit/return actions, delete guard on
  submitted reports.
- **Factories** + migration (`site_management.0011`).

## [Prompt 12] — 2026-08-14

### Added

- **`Issue`**: title/description, source (inspection/attendance/store/manual/
  report), site/area/cleaner/inspection refs, category, priority, full status
  lifecycle (OPEN → UNDER_REVIEW → ASSIGNED → IN_PROGRESS → COMPLETED →
  VERIFIED → CLOSED, REOPENED), escalation level + flag, due date, resolved/
  closed timestamps.
- **`Job`**: work orders (issue-linked or standalone) assigned to users or
  cleaners, priority, full status lifecycle with verify-before-close, private
  completion photo (`file` on the private backend), completion/verified/closed
  timestamps; `overdue` = past due and not done.
- **Services** (transactional + audited): create/update/review/escalate issue,
  assign-from-issue, create/update/assign/start/complete/verify/close/reopen
  job; transition-controlled; photo evidence enforced when
  `JOB_COMPLETION_PHOTO_REQUIRED`; reopened jobs preserve history; issue status
  follows its jobs (assigned once worked, closed when all jobs close); domain
  events `IssueCreated`, `IssueEscalated`, `JobAssigned`, `JobCompleted`,
  `JobVerified`.
- **Selectors**: role-scoped `issue_list`, `issue_detail`, `job_list`,
  `job_detail`, `overdue_jobs`, `issue_summary`, `job_summary` (single
  queries).
- **API**: `/issues` CRUD + review/escalate/jobs, `/jobs` CRUD +
  assign/start/complete/verify/close/reopen + photo upload + signed
  download-url + `/jobs/overdue` + `/jobs/summary` + `/issues/summary`; read =
  management/viewer, manage = site scope, review/close/reopen = zone
  supervisor+, escalate = GS/AGS, assign = `assign_job` perm + site scope,
  verify = `verify_job` perm + site scope.
- **Admin**: `IssueAdmin` (priority/category/status badges, job inline,
  escalate/assign/verify/reopen actions, delete guard) and `JobAdmin`
  (due date/status/assignee, readonly photo fields, delete guard).
- **Factories** + migration (`site_management.0010`).

### Changed

- `JOB_COMPLETION_PHOTO_REQUIRED` added to constance runtime configuration.

## [Prompt 11] — 2026-08-14

### Added

- **`InspectionTemplate`**: reusable checklists — global (site null) or
  site-scoped, optional area, frequency (daily/weekly/monthly/manual), soft
  deactivation (never deleted once inspections exist).
- **`InspectionTemplateItem`**: YES_NO / PASS_FAIL / SCORE / TEXT / PHOTO rows
  with required flag, sequence, help text; unique sequence per template.
- **`Inspection`**: site/area/template, inspection_date, optional shift,
  inspected_by, overall_status (PASSED/FAILED/NEEDS_ATTENTION), score, notes,
  DRAFT → SUBMITTED → REVIEWED → RETURNED workflow, submitted_at.
- **`InspectionResult`**: private PHOTO attachments (PrivateFileModel + signed
  tokens), type-matched answers (value_text/value_number/value_boolean/passed),
  notes; unique (inspection, template_item).
- **Services** (transactional + audited): template CRUD + deactivate, start/
  save/submit/return/review, add/update result, photo upload, transparent
  `calculate_inspection_score` (SCORE average; any failure → FAILED, score < 70
  → NEEDS_ATTENTION, else PASSED); required items enforced on submit;
  immutable once submitted unless returned; `InspectionSubmitted` event and the
  `create_issue_from_failed_result` hook (notification + `InspectionIssueDetected`
  event, ready for the future Issues module).
- **Selectors**: role-scoped `template_list`, `inspection_list`, detail,
  `inspection_summary`, `area_latest_status` (single queries).
- **API**: `/inspection-templates` CRUD + status, `/inspections` list/start/
  detail/update/submit/return/review/summary, results create/update, photo
  upload + signed download URL; read = management/viewer, manage = site scope,
  review/return = zone supervisor or above.
- **Admin**: `InspectionTemplateAdmin` (item inline, actions), `InspectionAdmin`
  (status badges, result inline readonly after submission, photo thumbnail with
  signed access, submit/return/review actions, delete guard).
- **Factories** + migration (`site_management.0009`).

## [Prompt 10] — 2026-08-14

### Added

- **`SiteStore`**: per-site store(s) with `managed_by`, soft deactivation.
- **`StoreItem`**: item_name/item_code/unit/category, opening + running
  `current_stock`, `minimum_stock_level` reorder point, unique name/code per
  store, `low_stock` flag (`current_stock <= minimum_stock_level`).
- **`StockMovement`**: immutable OPENING/RECEIVED/ISSUED/RETURNED/DAMAGED/
  LOST/ADJUSTMENT records (signed for adjustments), optional cleaner/area,
  required reason for damage/loss.
- **`StockRequest`** + **`StockRequestItem`**: DRAFT → SUBMITTED →
  ZONE_REVIEWED → OFFICE_PROCESSED → COMPLETED/REJECTED workflow with
  per-item requested/approved quantities, ready for Office Management.
- **Services** (transactional + audited): store/item CRUD, concurrency-safe
  `record_stock_movement` (`select_for_update` + `F` expressions), receive/
  issue/damage/loss/adjust helpers, request create/submit/review/reject/
  complete (completion issues approved stock); `StockLow` + `StockRequestSubmitted`
  domain events, low-stock in-platform notification to the store manager.
- **Negative-stock guard**: refused at the service layer unless the
  `ALLOW_NEGATIVE_STOCK` constance override is enabled.
- **Selectors**: role-scoped `store_list`/`store_detail`, `stock_items`,
  `stock_movements` (filters), `low_stock_items`, `stock_requests`.
- **API**: `/stores` CRUD + items, movements, requests and workflow endpoints
  + `/stores/low-stock`; read = management/viewer, manage = site scope,
  review/reject/complete = zone-level management.
- **Admin**: `SiteStoreAdmin` (item inline, low-stock badge, actions),
  `StoreItemAdmin`, read-only `StockMovementAdmin`, `StockRequestAdmin`
  (item inline, submit/review/reject/complete actions).
- **Factories** + migration for all five entities.

### Changed

- `ALLOW_NEGATIVE_STOCK` added to constance runtime configuration.

## [Prompt 09] — 2026-08-14

### Added

- **`TraineeProgram`**: cleaner→site training lifecycle with status
  (in_training/extended/passed/failed/dropped), date window, assigned site
  supervisor, notes, partial-unique `uniq_active_trainee_program` constraint
  (one active program per cleaner), `is_active_program` helper.
- **`TraineeEvaluation`**: scored evaluations (attendance/performance/behavior/
  skill, each ≤ 100, computed `total_score` ≤ 400), `is_final` flag, evaluated-by.
- **Services** (transactional + audited): `start_trainee_program` (cleaner →
  TRAINEE, rejects ACTIVE cleaners), `update_trainee_program`,
  `extend_trainee_program` (reason required), `record_trainee_evaluation`,
  `pass_trainee` (final evaluation + verified ID required; cleaner → ACTIVE),
  `fail_trainee` / `drop_trainee` (reason required; cleaner → INACTIVE);
  `TraineeStarted/Extended/Passed/Failed/Dropped` domain events.
- **Selectors**: `TraineeFilter` (site_id/status/search), role-scoped
  `trainee_list_queryset`, `trainee_evaluations`, `trainee_summary`,
  `trainee_average_score`.
- **API**: `/trainees` list (paginated, filtered) & create, `/trainees/{id}`
  detail & update, evaluations list & create, `extend`/`pass`/`fail`/`drop`
  actions, `/trainees/summary`; read = management or viewer, manage = site
  scope, decide = senior management only.
- **Admin**: `TraineeProgramAdmin` (evaluation inline, status filter, avg
  score, extend/pass/fail/drop actions, readonly + delete guard for completed
  programs).
- **Factory** + migration for trainee programs and evaluations.

## [Prompt 08] — 2026-08-13

### Added

- **`AttendanceRecord`**: full status set, check-in/out (overnight-safe),
  review workflow (DRAFT/SUBMITTED/REVIEWED/RETURNED/LOCKED), partial-unique
  constraints for full-time (cleaner+date) and shift (cleaner+shift+date)
  records.
- **Services** (transactional + audited): generate daily sheet (idempotent
  from active assignments + shift bindings, `bulk_create`), bulk upsert,
  save draft, record single, submit (requires all scheduled marked), return
  (group or record), review, auto-lock (`ATTENDANCE_LOCK_AFTER_DAYS`);
  `AttendanceSubmitted` domain events.
- **Selectors**: `attendance_daily_sheet` (single query), `attendance_history`,
  `attendance_summary` (single grouped aggregate), `missing_attendance_sites`,
  `attendance_exceptions`.
- **API**: daily/bulk/record/submit/return/review/history/summary/missing/
  exceptions endpoints with role scoping, pagination, and validation.
- **Admin**: `AttendanceRecordAdmin` (filters, date hierarchy, readonly after
  submission, submit/return/review actions, delete guard for locked records).
- **Factory** + migration for attendance records.

### Changed

- `ATTENDANCE_LOCK_AFTER_DAYS` added to constance runtime configuration.

## [Prompt 07] — 2026-08-13

### Added

- **`CleanerSiteAssignment`**: cleaner→site assignment with `assignment_type`
  (FULL_TIME/SHIFT, validated against site work mode), date window, status
  lifecycle (DRAFT/ACTIVE/ENDED/SUSPENDED), partial-unique active constraint
  per cleaner+site, ACTIVE requires an ACTIVE cleaner.
- **`CleanerShiftAssignment`**: shift bindings (shift must belong to the
  assignment's site, SHIFT-type only, one active per assignment+shift).
- **`CleanerAreaSchedule`**: dated area/task/time responsibilities with
  overnight support and per-cleaner/day overlap blocking.
- **Services** (transactional + audited): assign/update/end/suspend/activate,
  bind/unbind shift, create/update/remove area schedules,
  `copy_schedule_from_date`; domain events `CleanerAssigned`/`CleanerUnassigned`.
- **Selectors**: `assignment_list_queryset`, `site_daily_schedule`,
  `cleaner_schedule`, and `scheduled_cleaners_for_attendance` (single-query,
  attendance-ready projection).
- **Policies**: `can_assign_cleaner`/`can_edit_assignment`/`can_view_assignment`
  with role/data scoping.
- **API**: assignments CRUD + status PATCHes, shift bindings, area schedules,
  and the `/schedules` daily endpoint.
- **Admin**: `CleanerSiteAssignmentAdmin` (inlines for shift bindings and
  area schedules, activate/end/suspend actions, delete guard) plus standalone
  shift-binding and area-schedule admins.
- **Factories** for assignments, shift bindings, and area schedules.

### Fixed

- Corrected the overnight time-overlap direction in `_spans_overlap`.

## [Prompt 06] — 2026-08-13

### Added

- **`Cleaner`** registry: ID type/number (normalised upper/trim, unique
  `(id_type, id_number)`), gender, birth date (future + minimum age via
  constance `MIN_CLEANER_AGE`), living location, validated phones, next-of-kin
  details, private profile photo, status lifecycle
  (APPLICANT/TRAINEE/ACTIVE/INACTIVE) enforced in the service layer,
  registration date.
- **`CleanerDocument`**: private storage (no public URL), SHA-256 duplicate
  detection, PENDING/VERIFIED/REJECTED lifecycle with verifier/timestamp/
  reason, expiry, primary-ID flag; only verified identity documents grant
  ACTIVE eligibility.
- **Privacy**: ID/phone masking in list APIs unless the caller is SYSTEM_ADMIN
  or holds `view_sensitive_cleaner_documents`; cleaner data is never cached;
  every document download is audited.
- **Services** (transactional + audited): register/update/status-change/
  activate-if-eligible/deactivate, document upload/verify/reject; domain
  events `CleanerRegistered`, `CleanerActivated`, `CleanerDeactivated`.
- **Selectors**: `cleaner_list_queryset`, `cleaner_serialize` (masking),
  `can_view_full_cleaner_profile`, `can_view_document`.
- **API**: cleaners list/create/detail/update/status + documents
  list/upload/detail/verify/reject/signed-download-url with role-based
  permissions.
- **Admin**: `CleanerAdmin` (status badges, masked ID, documents inline,
  activate/deactivate actions, delete guard) and `CleanerDocumentAdmin`
  (verify/reject actions, privileged image preview, delete guard for verified
  documents).
- **Factories** for cleaners and documents.

### Changed

- `MIN_CLEANER_AGE` added to constance runtime configuration.

## [Prompt 05] — 2026-08-13

### Added

- **`SiteShift`**: manual per-site shift configuration (`shift_name`,
  `shift_code`, `start_time`, `end_time`, `effective_days`, `sequence`,
  `description`) with partial-unique active name/code constraints,
  `crosses_midnight` (overnight support), and deactivate-instead-of-delete.
- **`SiteArea`**: per-site areas (`area_name`, `area_code`, `floor`,
  `description`) unique per site; soft deactivation.
- **`OperationalRole`**: globally configurable operational roles with unique
  name/code and deactivation protection.
- **`SiteWorkingRule`**: per-site operational flags
  (`allowed_assignment_types`, `attendance_locked`,
  `require_shift_area_assignment`, `allow_temporary_transfers`).
- **Validation**: `validate_effective_days`, `validate_shift_time_logic`,
  `validate_site_work_mode`, `validate_shift_belongs_to_site`,
  `validate_area_belongs_to_site`, `validate_site_configuration_consistency`
  (incl. duplicate-shift detection).
- **Services** (transactional + audited): shift/area/role
  create/update/deactivate.
- **API**: shift, area, and operational-role list/create/update/status
  endpoints with role-scoped write permissions (SYSTEM_ADMIN /
  GENERAL_SUPERVISOR / `manage_site_configuration`).
- **Admin**: `SiteShift` and `SiteArea` inlines under Site; standalone
  `OperationalRole` admin with status badge, actions, and hard-delete guard.
- **Factories** for shifts, areas, roles, and working rules (tests).

## [Prompt 04] — 2026-08-13

### Added

- **`Zone` model**: name, unique `code`, description, soft-deactivate
  (`ActivatableModel` + `UserStampedModel`).
- **`Site` organisation fields**: `zone` FK, `building_name`, `location`,
  `contact_person`, `work_mode` (`FULL_TIME`/`SHIFT`/`FULL_TIME_AND_SHIFT`),
  validated `working_days` weekday codes, `start_date`, `notes`, plus
  `has_operational_history` and `supervisor_count`.
- **Supervisor assignments**: `SiteSupervisorAssignment`,
  `ZoneSupervisorAssignment`, `AssistantGeneralSupervisorAssignment` — date
  windows (`assigned_from`/`assigned_to`), soft `is_active`, partial-unique
  active constraints, `clean()` rules (AGS zone required unless `all_zones`,
  per-site supervisor cap from constance `MAX_SITE_SUPERVISORS_PER_SITE`,
  date-range validation).
- **Scoping selectors** (`apps/site_management/scoping.py`): `visible_zones`,
  `visible_sites`, `supervised_sites`, `assigned_zone_ids`,
  `site_in_user_scope`, `active_site_supervisor_ids`; `user_can_manage_site`
  rewritten for the assignment-based rules.
- **Services** for zone lifecycle (`create`/`update`/`deactivate`/`restore`)
  and supervisor assignment/ending (transactional, audited, cache-safe).
- **Admin**: `ZoneAdmin`, `SiteAdmin` (supervisor inline, delete guard),
  and the three assignment admins (search/filter/date-hierarchy/
  activate-deactivate actions/raw id fields).
- **API foundation**: paginated role-scoped `GET /zones`, `GET /zones/{id}`,
  paginated `GET /sites` (Paginated envelope + `zone_id`/`work_mode` filters),
  `GET /sites/{id}/supervisors`.
- **Factories**: `ZoneFactory`, updated `SiteFactory`, and the three
  assignment factories.

### Changed

- `/sites` list response is now the paginated envelope
  (`count`/`next`/`previous`/`results`) instead of a bare array.
- Site list/detail include zone and work-mode data; visibility is
  assignment/zone-based via the new scoping selectors.

## [Prompt 03] — 2026-08-13

### Added

- **Base models**: `TimeStampedModel`, `UserStampedModel` (nullable
  `created_by`/`updated_by` with `SET_NULL`), `ActivatableModel` (soft-delete
  manager), `CodeSlugModel`.
- **Audit logging**: redesigned `AuditLog` with `user`, `action`, `model_name`,
  `object_id`, `object_repr`, `before_data`/`after_data` JSON snapshots,
  `ip_address`, `request_id`; `record_audit()` service (backward-compatible
  `actor`/`changes` aliases) and `model_data()` snapshot helper.
- **Request-ID middleware**: reads/generates `X-Request-ID`, sets the response
  header, stores it in a contextvar, and injects it into every structured log
  line via `RequestIdFilter`.
- **Domain error contract**: `DomainError` hierarchy (`ConflictError`,
  `NotFoundError`, `ForbiddenActionError`, `BusinessRuleError`).
- **API error contract**: shared `{"error": {code, message, trace_id,
  fields}}` envelope via `apps.core.handlers` (ValidationError→422,
  DoesNotExist→404, PermissionDenied→403, ConflictError→409, unexpected→500).
- **Pagination & sorting**: `PageParams`, generic `Paginated` envelope
  (`count`/`next`/`previous`/`results`), constance-driven page-size defaults
  and caps, whitelisted `apply_ordering`.
- **Private file foundation**: `PrivateMediaStorage` (no public URL),
  extension/size validators, abstract `PrivateFileModel`, signed download
  tokens (TTL from constance `FILE_TOKEN_TTL_SECONDS`), and the
  `/files/signed/{token}/` streaming endpoint with permission checks and
  `FILE_DOWNLOAD` audit entries.
- **Domain-event outbox**: `DomainEvent` model + `publish_domain_event()`
  persisted via `transaction.on_commit`; `list_pending_domain_events`.
- **Cache utilities**: keys namespaced under `wbz_site`, `get_or_set`,
  `versioned`, `safe_delete`, prefix invalidation.
- **Layering helpers**: `apps/core/policies.py` (`require`,
  `ensure_permitted`) and `apps/core/validators.py`.

### Changed

- `record_audit` snapshots: `create_site`/`update_site` now record real
  `before_data`/`after_data` instead of a field delta.
- `config/api.py` now registers all error handlers from `apps.core.handlers`.
- Logging includes `request_id` on every line.
- Mypy test relaxation now disables `no-untyped-def` explicitly.

### Fixed

- django-constance database backend requires a cross-process cache; test
  settings disable `CONSTANCE_DATABASE_CACHE_BACKEND`.
- `ValidationError` with a list of messages now maps to 422 with a `_` field
  bucket (previous code crashed on `error_dict`).

## [Prompt 02] — 2026-08-13

### Added

- **Custom user model** (`accounts.User`): email as the unique login
  identifier (case-insensitive, stored lowercased), validated Tanzania/E.164
  phone, IANA timezone (default `Africa/Dar_es_Salaam`), optional avatar,
  `full_name`, `created_at`/`updated_at`, `last_login`, and a custom
  `UserManager` (`create_user`/`create_superuser`).
- **Role system**: `RoleCode` enum (`system_admin`, `general_supervisor`,
  `assistant_general_supervisor`, `zone_supervisor`, `site_supervisor`,
  `management_viewer`) with helper methods on `User`.
- **RBAC foundation**: Django groups per role, model + custom permissions
  (site reports, job assignment/verification, trainee approval, exports, …),
  declarative matrix (`apps/accounts/rbac.py`), idempotent `seed_rbac`
  command, and a `post_save` signal that keeps user group membership in sync.
- **Authentication**: signed (HMAC) access tokens + revocable server-side
  refresh tokens; `TokenAuth` bearer scheme; API endpoints
  `login`, `refresh`, `logout`, `me`, `password-change`; django-axes
  lockout; password validators (min length 12, common, numeric, similarity).
- **Session auth foundation**: Django auth views mounted at `/accounts/`
  (login/logout, password change, password reset) with functional templates.
- **User admin**: role/active filters, activate/deactivate actions, deletion
  guard for users with operational history, readonly audit fields.
- **`UserTimezoneMiddleware`** activating the authenticated user's timezone.
- **Factories** for users in every role and active/inactive states.

### Changed

- Replaced the prompt-1 `Role` (`admin/manager/staff/viewer`) with the
  professional `RoleCode` set; site management, seed command, core API and
  tests updated accordingly.
- `UserAdmin` and admin login now use email.
- API auth now prefers stateless access tokens, falling back to long-lived
  `ApiToken` keys.
- `.env.example` gains `ACCESS_TOKEN_TTL_SECONDS` and
  `REFRESH_TOKEN_TTL_SECONDS`.

### Fixed

- django-axes recorded failed logins with `username=None` because it derived
  `AXES_USERNAME_FORM_FIELD="email"` from `USERNAME_FIELD`; pinned to
  `"username"` so lockout matches `authenticate(username=...)`.
- Django `ValidationError` in `accounts` services propagates as HTTP 422
  via the global API handler.
- `password_reset_email.html` apostrophe template error.

## [Prompt 01] — 2026-08-13

### Added

- Split settings profile (`base` / `dev` / `test` / `prod`) powered by
  `django-environ`.
- Custom `accounts.User` with platform roles; `ApiToken` bearer authentication;
  django-axes brute-force protection.
- Django Ninja API at `/api/site-management/v1` with OpenAPI/Swagger docs,
  a Django `ValidationError → 422` handler, and versioned routers.
- Celery application (`config/celery_app.py`) with `django-celery-beat`
  database scheduler and an idempotently-registered periodic stats task.
- Redis-backed cache (`django-redis`), WhiteNoise static compression, private
  media root, CORS/CSRF from environment, structured JSON console logging.
- Jazzmin admin with branding plus `django-constance` runtime configuration
  (branding colours, page sizes, cache TTLs, thresholds, feature flags).
- Host probes `/healthz` and `/readyz`, landing redirect to `/admin/`.
- `apps.core` (audit log, soft-delete, cache helpers, typed request),
  `apps.web` (probes), and the carried-forward `apps.site_management`.
- Docker foundation: `Dockerfile` (python:3.12-slim, non-root),
  `docker-compose.yml` (db/redis/web), entrypoint + wait-for-db.
- Tooling: `Makefile`, `.pre-commit-config.yaml`, split `requirements/`.
- Test foundation: factory-boy factories, 96 tests at ~95% branch coverage.
- Documentation set: contract, architecture, domain, RBAC, API, theme,
  testing, performance, assumptions, state, changelog.

### Fixed

- Django `ValidationError` now maps to HTTP 422 instead of a 500.
- Axes-compatible login: `authenticate(request=...)` forwarded from the API.
