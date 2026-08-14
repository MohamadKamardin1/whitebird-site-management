# OpenCode Build State

Track of the 20-prompt build of the White Bird Zanzibar — Site Management
Module. Each prompt updates this file before its commit.

## Progress

| Prompt | Title                                        | Status             | Commit |
| ------ | -------------------------------------------- | ------------------ | ------ |
| 1      | Scaffold premium Django foundation           | Prompt 1 completed | —      |
| 2      | Custom user, RBAC and auth foundation        | Prompt 2 completed | —      |
| 3      | Shared kernel: audit, files, events, errors  | Prompt 3 completed | —      |
| 4      | Organisation hierarchy (zones/sites/supervisors) | Prompt 4 completed | —      |
| 5      | Site configuration (shifts/areas/roles) | Prompt 5 completed | —      |
| 6      | Cleaner registry & secure documents | Prompt 6 completed | —      |
| 7      | Assignments & scheduling engine | Prompt 7 completed | —      |
| 8      | Attendance engine | **Prompt 8 completed** | see CHANGELOG |
| 9      | Trainee lifecycle & conversion | **Prompt 9 completed** | see CHANGELOG |
| 10     | Site store & stock requests | **Prompt 10 completed** | see CHANGELOG |
| 11     | Inspections & templates | **Prompt 11 completed** | see CHANGELOG |
| 12     | Issues, jobs & escalation | **Prompt 12 completed** | see CHANGELOG |
| 13     | Reporting chain engine | **Prompt 13 completed** | see CHANGELOG |
| 14–20  | (pending)                                    | —                  | —      |

## Prompt 13 — completed ✅

Implemented the complete reporting chain from Site Supervisor to Management:

- **`DailySiteReport`**: aggregates real operational data (attendance, store,
  inspections, trainees, issues) for a site/date; immutable snapshot stored on
  submission; full status chain through zone/assistant/general/management.
- **`ZoneSummaryReport`**: zone roll-up with `issues_extracted` and site-report
  snapshots; **`AssistantGeneralSummaryReport`**: cross-zone summary with
  `problems_extracted`; **`GeneralManagementReport`**: final management output
  with `key_issues` and `assigned_jobs`.
- **Services**: generate/submit/return/review at every level (transactional +
  audited), `recalculate_report_snapshots`, report cache invalidation, and
  `SiteReportSubmitted` / `ZoneReportSubmitted` / `AssistantReportSubmitted` /
  `GeneralReportSubmitted` domain events. Return flow preserves history.
- **Selectors**: report details, `missing_site_reports`,
  `reporting_status_dashboard`.
- **API**: `/reports/site`, `/reports/zone`, `/reports/assistant`,
  `/reports/general` (list/generate/submit/return), `/reports/status`,
  `/reports/missing`; read = management/viewer, site report manage = site
  scope, zone review = zone supervisor+, assistant authoring = AGS/GS, general
  authoring = GS.
- **Admin**: reporting admin for all four levels (status badges, readonly JSON
  snapshots, date hierarchy, submit/return actions, delete guard).
- **Factories** + migration (`site_management.0011`).

**Quality gates (all green):** Ruff · Mypy strict · pytest 428 passed ·
coverage 90.30% ≥ 90 · `makemigrations --check` clean.

## Prompt 12 — completed ✅

Implemented issue tracking and job/work-order assignment with full escalation
and verification workflow:

- **`Issue`**: sources (inspection/attendance/store/manual/report), category,
  priority, escalation level/flag, status lifecycle with due dates; linked to
  area/cleaner/inspection.
- **`Job`**: issue-linked or standalone work orders assigned to users/cleaners,
  full lifecycle OPEN → ASSIGNED → IN_PROGRESS → COMPLETED → VERIFIED → CLOSED
  (+ REOPENED preserving history), private completion photo, `overdue` flag.
- **Services**: transition-controlled and audited; verify is required before a
  job can close; photo evidence enforced when `JOB_COMPLETION_PHOTO_REQUIRED`;
  issue status follows its jobs (assigned when worked, closed when all jobs
  close); `IssueCreated`, `IssueEscalated`, `JobAssigned`, `JobCompleted`,
  `JobVerified` domain events.
- **API**: issues CRUD + review/escalate/jobs, jobs CRUD +
  assign/start/complete/verify/close/reopen, photo upload + signed download,
  `/issues/summary`, `/jobs/overdue`, `/jobs/summary`; read = management/
  viewer, manage = site scope, review/close/reopen = zone supervisor+,
  escalate = GS/AGS, assign/verify = RBAC `assign_job`/`verify_job` + site
  scope.
- **Admin**: `IssueAdmin` (badges, job inline, escalate/assign/verify/reopen
  actions, delete guard) and `JobAdmin` (due/status/assignee, readonly photo
  fields, delete guard).
- **Factories** + migration (`site_management.0010`).

**Quality gates (all green):** Ruff · Mypy strict · pytest 412 passed ·
coverage 90.30% ≥ 90 · `makemigrations --check` clean.

## Prompt 11 — completed ✅

Implemented the full inspection engine for site area reports:

- **`InspectionTemplate`** (+ items): global or site-scoped checklists with
  YES_NO/PASS_FAIL/SCORE/TEXT/PHOTO rows, required flags, frequencies, soft
  deactivation.
- **`Inspection`** (+ results): DRAFT → SUBMITTED → REVIEWED → RETURNED
  workflow with type-matched answers, private photo attachments, and
  transparent `calculate_inspection_score` (SCORE average; any failed answer →
  FAILED, score < 70 → NEEDS_ATTENTION, else PASSED).
- **Workflow rules**: required items enforced before submit; submitted
  inspections immutable unless returned; `InspectionSubmitted` domain event;
  failed results trigger the `create_issue_from_failed_result` hook
  (notification + `InspectionIssueDetected` event, ready for the Issues module).
- **Security**: result photos stored on the private backend, served only via
  signed download tokens (owner or system admin).
- **API**: templates CRUD/status, inspections list/start/update/submit/return/
  review/summary, results create/update, photo upload + signed URL; read =
  management/viewer, manage = site scope, review/return = zone supervisor+.
- **Admin**: template + item inline, inspection filters/status badges, readonly
  result inline with signed photo thumbnail, submit/return/review actions,
  delete guard on submitted inspections.
- **Factories** + migration (`site_management.0009`).

**Quality gates (all green):** Ruff · Mypy strict · pytest 394 passed ·
coverage 90.20% ≥ 90 · `makemigrations --check` clean.

## Prompt 10 — completed ✅

Implemented accurate, concurrency-safe site store records and stock requests
ready for future Office Management integration:

- **`SiteStore`** (per-site, soft deactivate) + **`StoreItem`** (opening/running
  stock, reorder point, unique name/code per store, `low_stock` flag).
- **`StockMovement`**: immutable OPENING/RECEIVED/ISSUED/RETURNED/DAMAGED/
  LOST/ADJUSTMENT records; damage/loss requires a reason; adjustments use
  signed quantities.
- **`StockRequest`** + **`StockRequestItem`**: DRAFT → SUBMITTED →
  ZONE_REVIEWED → OFFICE_PROCESSED → COMPLETED/REJECTED with per-item
  requested/approved quantities; completion issues approved stock against the
  store.
- **Concurrency safety**: movements lock the item row (`select_for_update`)
  and apply the delta with `F` expressions inside an atomic transaction;
  negative stock is rejected unless the `ALLOW_NEGATIVE_STOCK` constance
  override is on.
- **Low-stock hook**: `StockLow` domain event + notification to the store
  manager when an item reaches its reorder point; `StockRequestSubmitted`
  domain event for the office module.
- **API**: `/stores` CRUD, items, movements, requests + submit/review/reject/
  complete, `/stores/low-stock`; read = management/viewer, manage = site scope,
  review/reject/complete = zone-level management.
- **Admin**: `SiteStoreAdmin` (item inline, low-stock badge), `StoreItemAdmin`,
  read-only `StockMovementAdmin`, `StockRequestAdmin` with submit/review/
  reject/complete actions.
- **Factories** + migration (`site_management.0008`).

**Quality gates (all green):** Ruff · Mypy strict · pytest 376 passed ·
coverage 90.52% ≥ 90 · `makemigrations --check` clean.

## Prompt 9 — completed ✅

Implemented the trainee lifecycle and cleaner conversion:

- **`TraineeProgram`**: cleaner→site training with status
  (in_training/extended/passed/failed/dropped), date window, assigned site
  supervisor, notes, partial-unique `uniq_active_trainee_program` (one active
  program per cleaner), `is_active_program`.
- **`TraineeEvaluation`**: scored evaluations (attendance/performance/behavior/
  skill ≤ 100 each, computed `total_score` ≤ 400), `is_final`, evaluated-by.
- **Services** (transactional + audited): start (cleaner → TRAINEE, rejects
  ACTIVE), update, extend (reason required), record evaluation, pass (final
  evaluation + verified ID → cleaner ACTIVE), fail/drop (reason required →
  cleaner INACTIVE); `TraineeStarted/Extended/Passed/Failed/Dropped` events.
- **Selectors**: `TraineeFilter`, role-scoped `trainee_list_queryset`,
  `trainee_evaluations`, `trainee_summary`, `trainee_average_score`.
- **API**: `/trainees` list/create, `/trainees/{id}` detail/update,
  evaluations list/create, `extend`/`pass`/`fail`/`drop`, `/trainees/summary`;
  read = management or viewer, manage = site scope, decide = senior only.
- **Admin**: `TraineeProgramAdmin` with evaluation inline, avg score,
  extend/pass/fail/drop actions, readonly + delete guard for completed programs.
- **Factory** + migration (`site_management.0007`).

**Quality gates (all green):** Ruff · Mypy strict · pytest 348 passed ·
coverage 90.13% ≥ 90 · `makemigrations --check` clean.

## Prompt 8 — completed ✅

Implemented the fast, accurate attendance engine:

- **`AttendanceRecord`**: statuses (SCHEDULED/PRESENT/LATE/ABSENT/SICK/LEAVE/
  PERMISSION/OFF/NOT_SCHEDULED), check-in/out (overnight-safe), review
  workflow (DRAFT/SUBMITTED/REVIEWED/RETURNED/LOCKED), partial-unique
  constraints per full-time (cleaner+date) and shift (cleaner+shift+date).
- **Services**: generate sheet (idempotent, from active assignments + shift
  bindings), bulk upsert, save draft, record single, submit (requires all
  scheduled marked), return, review, auto-lock; audited; `AttendanceSubmitted`
  domain events.
- **Selectors**: daily sheet (single query), history, summary (single grouped
  aggregate), missing sites, exceptions — all role-scoped.
- **API**: daily/bulk/record/submit/return/review/history/summary/missing/
  exceptions endpoints with strict scoping and validation.
- **Admin**: `AttendanceRecordAdmin` (filters, date hierarchy, readonly after
  submission, submit/return/review actions, delete guard for locked records).
- **Factory** + migration.

**Quality gates (all green):** Ruff · Mypy strict (126 files) · pytest 332
passed · coverage 90.1% ≥ 90 · `makemigrations --check` clean.

Implemented the cleaner assignment and scheduling engine:

- **`CleanerSiteAssignment`**: cleaner→site with FULL_TIME/SHIFT type (must
  match site work mode), start/end dates, DRAFT/ACTIVE/ENDED/SUSPENDED status,
  assigned-by, partial-unique active constraint per cleaner+site, ACTIVE
  requires an ACTIVE cleaner (trainees/applicants are DRAFT).
- **`CleanerShiftAssignment`**: shift bindings (shift must belong to the
  assignment's site, SHIFT-type only, one active per assignment+shift).
- **`CleanerAreaSchedule`**: dated area/task/time responsibilities with
  overnight support and overlap blocking per cleaner/day.
- **Services** (transactional + audited): assign/update/end/suspend/activate,
  shift bind/unbind, area-schedule create/update/remove, and
  `copy_schedule_from_date`; domain events `CleanerAssigned`/`CleanerUnassigned`.
- **Selectors**: `assignment_list_queryset`, `site_daily_schedule`,
  `cleaner_schedule`, and the optimised single-query
  `scheduled_cleaners_for_attendance` projection.
- **Policies**: `can_assign_cleaner`/`can_edit_assignment`/`can_view_assignment`
  with role/data scoping.

## Prompt 7 — completed ✅

Implemented the cleaner assignment and scheduling engine:
- **API**: assignments CRUD + status, shift bindings, area schedules, and the
  attendance-ready `/schedules` endpoint.
- **Admin**: `CleanerSiteAssignmentAdmin` (status badges, shift/schedule
  inlines, activate/end/suspend actions, delete guard) + standalone
  shift/schedule admins.

**Quality gates (all green):** Ruff · Mypy strict (122 files) · pytest 310
passed · coverage 90.1% ≥ 90 · `makemigrations --check` clean.

## Prompt 6 — completed ✅

Implemented the cleaner/applicant/trainee registry with secure document
handling and privacy-conscious design:**Quality gates (all green):** Ruff · Mypy strict (122 files) · pytest 310
passed · coverage 90.1% ≥ 90 · `makemigrations --check` clean.

Implemented the cleaner/applicant/trainee registry with secure document
handling and privacy-conscious design:

- **`Cleaner`** master data: ID type/number (normalised upper/trim, unique
  `(id_type, id_number)`), gender, birth date (future/age validated via
  constance `MIN_CLEANER_AGE`), living location, phones (validated), next of
  kin, private profile photo, status lifecycle (APPLICANT/TRAINEE/ACTIVE/
  INACTIVE), registration date.
- **`CleanerDocument`**: private file storage (no public URL), SHA-256
  duplicate detection, PENDING/VERIFIED/REJECTED lifecycle with
  verifier/timestamp/reason, identity eligibility flag.
- **Privacy**: ID/phone masking in list APIs unless the caller holds
  `view_sensitive_cleaner_documents`; cleaner data never cached; every
  download audited.
- **Services** (transactional + audited): register/update/status/
  activate-if-eligible/deactivate, document upload/verify/reject; domain
  events `CleanerRegistered`/`CleanerActivated`/`CleanerDeactivated` via the
  outbox.
- **Selectors** with `can_view_full_cleaner_profile`/`can_view_document`.
- **API**: cleaners CRUD/status + documents list/upload/detail/verify/reject/
  signed download-url with role-scoped permissions and PII masking.
- **Admin**: `CleanerAdmin` (status badges, masked ID, documents inline,
  activate/deactivate actions, delete guard) and `CleanerDocumentAdmin`
  (verify/reject actions, image preview for privileged staff, delete guard).

**Quality gates (all green):** Ruff · Mypy strict (116 files) · pytest 274
passed · coverage 91.4% ≥ 90 · `makemigrations --check` clean.

## Prompt 5 — completed ✅

Implemented fully manual, admin-configurable site configuration with zero
hardcoded operational rules:

- **`SiteShift`**: site-scoped, manual `shift_name`/`shift_code`/`start_time`/
  `end_time`/`effective_days`/`sequence`; partial-unique active name/code;
  `crosses_midnight`; overnight supported; deactivation (never delete).
- **`SiteArea`**: site-scoped `area_name`/`area_code`/`floor`/`description`;
  unique per site; soft deactivation.
- **`OperationalRole`**: global configurable roles (cleaners etc.);
  protect/deactivate when used.
- **`SiteWorkingRule`**: per-site flags (`allowed_assignment_types`,
  `attendance_locked`, `require_shift_area_assignment`,
  `allow_temporary_transfers`).
- **Validation** (`validators.py` + `validation.py`): `validate_effective_days`,
  `validate_shift_time_logic`, `validate_site_work_mode`,
  `validate_shift_belongs_to_site`, `validate_area_belongs_to_site`,
  `validate_site_configuration_consistency` (incl. duplicate-shift detection).
- **Services** (audited, transactional): shift/area/role
  create/update/deactivate.
- **API**: shifts, areas, and operational-roles CRUD/status endpoints with
  role-scoped permissions.
- **Admin**: `SiteShift`/`SiteArea` inlines under Site, `OperationalRole`
  standalone with status badge and delete guard.
- **Factories** for all four entities.

**Quality gates (all green):** Ruff · Mypy strict (111 files) · pytest 237
passed · coverage 92.1% ≥ 90 · `makemigrations --check` clean.

Built the organisation hierarchy inside `apps.site_management`:

- **`Zone`** model (unique `code`, soft-deactivate, `UserStampedModel`) with
  `Site.zone` FK.
- **`Site`** evolved: `zone`, `building_name`, `location`, `contact_person`,
  `work_mode` (`FULL_TIME`/`SHIFT`/`FULL_TIME_AND_SHIFT`), `working_days`
  (validated weekday codes), `start_date`, `notes`, `has_operational_history`
  guard.
- **Supervisor assignments**: `SiteSupervisorAssignment`,
  `ZoneSupervisorAssignment`, `AssistantGeneralSupervisorAssignment` with
  date windows, partial-unique active constraints, `clean()` rules
  (AGS zone/all_zones, per-site supervisor cap from constance, date ranges).
- **Scoping selectors**: `visible_zones`, `visible_sites`, `supervised_sites`,
  `assigned_zone_ids`, `site_in_user_scope` covering every role; write access
  rewritten in `user_can_manage_site`.
- **Services** for zone lifecycle and supervisor assignment/ending (audited,
  transactional, cache-safe).
- **Admin**: `Zone`, `Site` (+ supervisor inline), and the three assignment
  admins with search/filter/date-hierarchy/actions and hard-delete guards.
- **API foundation**: paginated role-scoped `GET /zones`, `GET /zones/{id}`,
  `GET /sites` (paginated envelope), `GET /sites/{id}`, `GET /sites/{id}/
  supervisors`.
- **Factories** for zones, sites, and all three assignment types.

**Quality gates (all green):** Ruff · Mypy strict (108 files) · pytest 215
passed · coverage 93.2% ≥ 90 · `makemigrations --check` clean.
