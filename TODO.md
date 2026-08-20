# Integrated Frontend Delivery Todo

- [x] Merge the White Bird Zanzibar frontend source into this Django repository under a dedicated frontend directory, retaining the frontend documentation, task backlog, and project configuration.
- [x] Add documented local-development routing so the frontend can call the Django Ninja API at `/api/site-management/v1` without an external deployment dependency.
- [x] Install and validate frontend dependencies within the integrated repository without modifying existing Django API contracts.
- [x] Run Django checks, frontend type checks, frontend production build, and HTTP smoke tests against the locally running combined services.
- [x] Verify the Git worktree, commit the integrated frontend change set with the configured author identity, and push the commit to the repository’s configured GitHub remote.

## 3D Marketing and Senior Documentation Upgrade

- [x] Define the public marketing narrative, target audiences, conversion path, 3D visual language, and relationship between the marketing site and `/app/` operations workspace.
- [x] Implement a production-ready responsive 3D marketing landing page with accessible fallback behavior, reduced-motion support, clear CTAs, and no fabricated reviews or testimonials.
- [x] Add product, workflow, role, security, and deployment sections that accurately reflect the Django API and React operations frontend.
- [x] Rewrite the repository README for senior engineers and operators, including architecture, local setup, environment configuration, API integration, Docker deployment, testing, security, observability, and release workflow.
- [x] Validate marketing and application routes, frontend type checking, production build, Django tests, static delivery, accessibility states, and responsive behavior.
- [x] Commit and push the completed 3D marketing and documentation upgrade to the configured GitHub branch.

**Execution constraint:** marketing content must use only verifiable product capabilities and must not invent customer reviews, ratings, testimonials, or unsupported performance claims.

**Design direction:** extend Coastal Ledger into an editorial 3D command-layer presentation: warm limestone, Indian Ocean navy, Reef Ledger Green, subtle depth, tactile topographic forms, disciplined motion, and direct responsibility-oriented copy.

## Operational Workflow Improvements

- [x] Replace every frontend object-to-string rendering path with safe domain-aware display formatting for nested API objects, status values, dates, and IDs.
- [x] Derive the authenticated user’s permitted site and zone scope from the backend permission/session contract so site supervisors never manually type site IDs for scoped workflows.
- [x] Simplify attendance into a daily sheet where scheduled cleaners can be marked present/absent and sign-in/sign-out times can be recorded with minimal input, while preserving backend lifecycle and review states.
- [x] Restrict cleaner registration and full onboarding actions to HR and system administrators; provide site supervisors read-only visibility into cleaners assigned to their site, including active/trainee status and shift context.
- [x] Implement site-scoped stock configuration owned by administrators and a supervisor workflow that selects a configured stock item, enters remaining quantity, requested quantity, and an optional reason/message.
- [x] Implement daily, weekly, and monthly White Bird PDF report templates with attendance and operational summaries, automatic report generation, review routing to zone supervisors, and delivery to admin@whitebirdtanzania.com.
- [x] Integrate Resend as the outbound email engine with a configurable sending domain and sender identity; document Namecheap forwarding as a separate inbound-mail concern.
- [x] Register recurring report jobs through the project’s supported scheduled-job mechanism with idempotency, retries, UTC scheduling, durable task identifiers, and observable execution outcomes.
- [x] Add backend/frontend tests for permissions, object formatting, scope derivation, attendance actions, onboarding visibility, stock requests, PDF output, scheduled handlers, and Resend failure handling.
- [x] Validate the full integrated system, update documentation and environment templates, commit the changes, and push them to the configured GitHub branch.

**Operational constraints:** backend authorization remains authoritative; client visibility is not a security boundary. No fabricated customer reviews, ratings, testimonials, or fallback operational data may be added.

## Attendance Lifecycle and Cleanliness Management Upgrade

- [ ] Replace the attendance present/absent-only controls with explicit sign-in and sign-out actions; preserve immutable timestamps and actor audit metadata.
- [x] Derive attendance outcome from the shift lifecycle: Present when sign-in and valid sign-out are recorded, Half present when sign-in exists without sign-out at close/review time, and Absent when no sign-in exists.
- [x] Keep attendance status visible but make the lifecycle actions primary: sign in, sign out, reopen/return when authorized, and submit for review.
- [x] Add a daily site-cleanliness declaration for toilets, garden, reception, and configurable operational areas, with completion status, on-time status, responsible cleaner(s), notes, corrective action, and escalation reason.
- [x] Scope daily cleanliness forms to the authenticated supervisor’s assigned site and prevent manual site-ID entry for scoped users.
- [x] Add backend validation that a responsible cleaner belongs to the site and is active/assigned for the declared date.
- [ ] Add management review states for daily cleanliness declarations: draft, submitted, returned, reviewed, escalated, and locked.
- [ ] Surface cleanliness exceptions, missed deadlines, half-present cleaners, and unresolved corrective actions in supervisor, zone-supervisor, and administrator dashboards.
- [ ] Include daily cleanliness and attendance lifecycle outcomes in daily, weekly, and monthly PDF reports and Resend delivery payloads.
- [x] Add audit history for attendance actions, cleanliness declarations, changes, returns, escalations, and review decisions.
- [ ] Add backend and frontend tests for lifecycle transitions, half-present derivation, scoped cleaner attribution, area validation, review permissions, escalation, reporting, and audit visibility.
- [x] Validate the integrated workflows with realistic site-supervisor and management-review scenarios, update documentation, commit, and push the completed upgrade.

**Operational constraint:** the backend remains the authorization source; client-side hiding is only a usability layer. No fabricated operational records or fallback cleanliness results may be introduced.

## Production Deep Links and Operational Workflow Upgrade

- [x] Fix production SPA refresh/deep-link handling so `/app/attendance`, `/app/inspections`, `/app/operations/issues`, `/app/stores`, and `/app/reports` never fall through to the Vite public-base error.
- [x] Verify the deployed static asset base, Django SPA catch-all route, and authenticated client route prefix work together in production and on browser refresh.
- [ ] Turn Start a field inspection into a guided, site-scoped workflow with configurable questions, evidence/photos where required, responsible-cleaner attribution, corrective actions, audit history, review/return states, and report-ready results.
- [ ] Turn Raise a site issue into an intelligent operational intake workflow with category, priority, affected area, responsible cleaner/team, due date, suggested next action, evidence, escalation, ownership, and auditable status transitions.
- [x] Turn Request configured stock into a simple interactive collection flow that selects configured items, captures quantity remaining, quantity needed, urgency, reason, and optional notes without manual IDs.
- [x] Upgrade report generation so the user chooses Daily or Weekly; non-Friday generation defaults to a daily report, while Friday generation offers/uses the weekly report containing the complete Monday–Friday operational data set.
- [ ] Include attendance lifecycle, cleanliness, inspections, issues, stock, and unresolved corrective actions in the appropriate daily and weekly report payloads and review routing.
- [ ] Add backend/frontend tests for deep-link refreshes, inspection completion, issue ownership/escalation, stock-request validation, and Friday weekly-report selection.
- [ ] Update documentation, run the full integrated quality suite, commit, and push the production release.

## White Bird AI Optimization Engine

- [x] Define a role-aware AI summary contract: site supervisors receive site-level action guidance, zone supervisors receive zone rollups, assistant-general supervisors receive cross-zone summaries, and general supervisors receive organization-level oversight.
- [x] Build a server-side operational evidence pack from authoritative attendance, cleanliness, inspections, issues, jobs, stock, and report data, constrained by the authenticated user’s existing scope and permissions.
- [x] Integrate DeepSeek through a server-only API client with an environment-held key, bounded prompts, structured JSON output validation, request timeouts, and no client-side secret exposure.
- [x] Add deterministic data-integrity checks that identify missing daily records, incomplete required inspection items, unresolved exceptions, overdue work, low-stock risks, and reporting gaps before AI summarization.
- [x] Persist auditable AI summary requests and outputs with actor, role scope, evidence snapshot fingerprint, model metadata, generated time, and explicit disclaimer that recommendations do not change operational records automatically.
- [x] Expose authorized APIs for on-demand AI summaries and reporting-quality optimization, with graceful human-readable fallback when the provider is unavailable or returns invalid structured output.
- [x] Add a responsive White Bird AI Optimization widget to the dashboard and reporting workspace, including priorities, evidence-backed observations, data-quality warnings, recommended accountable actions, and a refresh control.
- [x] Keep AI output read-only and require existing backend workflows for every operational action, review, escalation, stock request, report submission, or assignment change.
- [x] Add backend/frontend tests for role-scope isolation, payload integrity, DeepSeek failure handling, structured-output validation, audit logging, and role-specific UI behavior.
- [x] Document the DeepSeek environment contract, security boundaries, model-use policy, operational limitations, validation results, release commit, and GitHub push.
- [x] Deliver the selected hybrid model: on-demand AI optimization plus role-scoped scheduled daily leadership briefs and a Friday weekly optimization brief, with idempotent execution and durable delivery/audit status.

## Role-Based Management Platform Redesign

- [x] Add the HR role with explicit responsibility for cleaner and trainee lifecycle, onboarding, employee records, site assignments, shifts, qualification decisions, and HR audit.
- [x] Add the Store Manager role with explicit responsibility for configured stock catalogs, site inventory visibility, stock requests, approvals/fulfillment, stock movements, and inventory audit.
- [x] Separate System Administrator capabilities from site-management menus: administrators manage platform users, roles, sites, zones, site-zone relationships, site configuration, shifts, and permission governance.
- [x] Define and enforce a capability matrix for HR, Store Manager, Site Manager/Supervisor, Zone Supervisor, Assistant General Supervisor, General Supervisor, and System Administrator.
- [x] Add HR cleaner onboarding for single records and validated Excel bulk import, including downloadable template, reference sheets, dropdowns, field validation, import preview, row-level errors, duplicate handling, and audited results.
- [x] Keep new cleaners in trainee status until an authorised HR qualification action transitions them to active cleaner status with qualification evidence and audit history.
- [x] Add site-manager trainee management for assigned trainees, daily attendance, performance observations, corrective actions, progress milestones, and daily trainee reporting.
- [x] Add HR-controlled cleaner/trainee site assignment and shift management with effective dates, site-scope validation, conflict checks, and audit history.
- [x] Build Store Manager inventory workflows for configured items, stock counts, reorder signals, request review, fulfillment, and complete stock movement audit.
- [x] Build dynamic role-specific side navigation and distinct dashboard compositions so each role sees only relevant responsibilities, metrics, alerts, and next actions.
- [x] Add role-isolation, import-validation, trainee-transition, assignment, shift, inventory, navigation, dashboard, and audit regression tests.
- [x] Document the role operating model, deployment migration, administrator setup sequence, Excel template usage, and release validation before commit and push.

## Reporting, Stock, Administration, Pagination, and GIS Upgrade

- [x] Replace report JSON preview with a professional White Bird PDF preview/download that includes reporter identity, role, site/zone scope, report type, reporting date/window, generation timestamp, review state, signatures/handover, KPIs, attendance, cleanliness, inspections, issues, stock, corrective actions, and audit metadata.
- [x] Ensure every site has a distinct configured store and that Store Manager can manage per-store item types, units, reorder thresholds, and quantities without mixing site inventory.
- [x] Make site stock collection interactive: supervisors select configured items for their assigned site, enter quantity remaining, requested quantity, urgency, and reason, with low-stock guidance and audited request state transitions.
- [x] Move the White Bird AI Optimization Engine below the dashboard analytics/cards so users see live analytics before AI insights and recommendations.
- [x] Fix the administrator user-management 404 by exposing the correct protected `/users` endpoint and preserving disable/revoke-only data-protection rules; user deletion must not be available.
- [x] Add compact, reusable pagination with five-row support and clear page controls for long operational tables and risk lists.
- [x] Provide ready-made daily cleanliness templates covering core Tanzanian site areas and ensure new sites receive usable checklist items without the empty-template dead end.
- [x] Implement protected System Administrator site CRUD, zone CRUD, complete site-zone assignment management, and clear definitions without exposing daily site-operation write actions.
- [x] Persist functional zone boundaries and site coordinates, provide a GIS workspace with Mapbox boundary drawing/editing and site markers, and keep boundary/site changes audited and administrator-controlled.
- [x] Add regression coverage for PDF rendering/content, store isolation, low-stock requests, AI widget order, user disable-only behavior, pagination, cleanliness template readiness, site/zone CRUD, site-zone assignment, and GIS configuration.
- [x] Update documentation, environment templates, migration instructions, run the full quality suite, commit, and push the release.

## Responsive Side Panels and Table Scrolling

- [x] Make shared individual-record side panels expand to the available mobile viewport width with safe padding, readable headers, and no horizontal page overflow.
- [x] Constrain horizontal overflow at the application/page shell so only intentionally wide tables scroll horizontally.
- [x] Ensure table wrappers retain accessible horizontal scrolling without forcing detail cards, forms, or the overall page to scroll sideways.
- [x] Validate side-panel behavior at phone and desktop breakpoints with frontend type checks, production build, and responsive visual verification.
- [x] Document, commit, and push the responsive side-panel and table-scroll fix.

## Integration Secret Loading Troubleshooting

- [x] Trace why `DEEPSEEK_API_KEY` and `VITE_MAPBOX_ACCESS_TOKEN` configured in project secrets are not taking effect in local or deployed runtime.
- [x] Correct environment loading, restart/rebuild affected services, and verify both integrations without exposing secret values.
- [x] Document the final configuration and validation steps.

## Administrator Panel, Report Preview, and Integration Settings Upgrade

- [x] Make the administrator mobile side panel internally scrollable with stable navigation grouping, spacing, and no content overlap between Account, Notifications, Exports archive, and scope information.
- [x] Replace raw report summary JSON blocks with a professional PDF-style preview that presents attendance, store, inspection, trainee, issue, comments, and audit information as readable sections and metrics.
- [x] Add administrator-only integration settings for DeepSeek and Mapbox with secure persistence, masked values, validation, audit history, and controlled runtime use across the platform.
- [x] Run schema/API/frontend tests and responsive verification without exposing secret values.
- [x] Document, commit, and push the completed administrator, reporting, and integration settings upgrade.

## Site Supervisor Daily Cleanliness Workflow from Report PDF

- [x] Pull and verify the latest `sultan` branch before starting the cleanliness workflow implementation.
- [x] Extract and map every daily cleanliness area, question, answer option, responsibility field, exception note, and sign-off requirement from the attached report PDF.
- [x] Design a beginner-friendly Excel-like site-supervisor grid that loads the logged-in supervisor's assigned site and current date automatically.
- [x] Implement guided daily answers, responsible-cleaner selection, comments/corrective action fields, validation, draft state, submit/lock behavior, and audit-safe persistence.
- [x] Validate the site-supervisor workflow across phone, tablet, and desktop layouts with backend/frontend tests and report data integrity checks.
- [x] Document, commit, and push the site-supervisor cleanliness workflow before beginning the zone-supervisor workflow.

## Inspection Save Reliability and Kiswahili-First Dashboard

- [x] Pull latest `sultan` code and trace the 422 create-result and 404 fake-result-ID update failures end to end.
- [x] Fix result identity handling so newly created results always use the server-issued ID and repeated saves update the real record only.
- [x] Improve row save feedback so saved answers show a stable responsive saved state and validation errors are clear to beginners.
- [x] Add full regression coverage for result creation, repeated updates, malformed payloads, permissions, and audit-safe persistence.
- [x] Add a Kiswahili-first localization foundation with an English switcher in the header and persistent language preference.
- [x] Translate the core dashboard navigation, site-supervisor cleanliness workflow, action labels, validation messages, and user-facing operational states into simple Tanzanian Kiswahili.
- [x] Run full backend/frontend tests, responsive checks, and localization validation, then document, commit, and push the release.

## Final Cleanliness Row and Complete Kiswahili Coverage

- [x] Pull latest `sultan` code and trace the exact backend question labels and final-row save/submission failure.
- [x] Translate every backend-provided checklist question and help text shown in the site-supervisor worksheet into simple Kiswahili.
- [x] Fix final-row result persistence, local state reconciliation, answered-count calculation, and area submission validation.
- [x] Add regression tests covering every row, especially the final row, and successful full-area submission.
- [x] Run full backend/frontend validation, document, commit, and push the fix.

## Generic Lobby Cleanliness Template Localization

- [x] Translate the existing generic Lobby area, template title, description, five checklist questions, help text, and visible workflow statuses into simple Kiswahili.
- [x] Verify that the generic template uses the same server-issued result reconciliation and fresh-submit validation as PDF-derived templates.
- [x] Add regression coverage for the generic template’s final-row save and successful area submission.
- [x] Run full backend/frontend validation, document, commit, and push the generic-template localization fix.

## Generic Template Completion and Kiswahili Coverage Correction

- [x] Trace why required generic text answers are still classified as unanswered at area submission.
- [x] Fix generic text-result completion checks in both the frontend pre-submit validator and backend submission service.
- [x] Translate every existing generic daily template area, title, description, question, and help text into simple Kiswahili.
- [x] Add regression tests for all generic template item types, final text-row saving, successful submission, and language coverage.
- [x] Run full backend/frontend validation, document, commit, and push the correction.

## Worksheet Refinement and Operational Calendar

- [x] Replace every written-answer cleanliness response control with an expanding text field that supports comfortable multi-line entry.
- [x] Remove the redundant paper-report instructional paragraph from the worksheet header.
- [x] Complete Kiswahili and English translations for worksheet table headers, statuses, generic/PDF-derived template titles, areas, questions, and help text.
- [x] Replace the dashboard AI brief with a polished operational calendar that highlights the current day and opens a selected-day survey table.
- [x] Add calm, accessible Airbnb-inspired motion and responsive states to the calendar and selected-day survey experience.
- [x] Run backend/frontend tests, selected-day survey validation, responsive checks, and commit/push the upgrade.

## Exact Kiswahili from Site Supervisor Report PDF

- [x] Re-read every page of the uploaded Site Supervisor cleanliness report and transcribe its exact direct Kiswahili questions, labels, response terms, and sign-off wording.
- [x] Replace current worksheet Kiswahili paraphrases with the document’s exact wording for all mapped daily cleanliness areas and generic controls.
- [x] Preserve the English switch and verify the document-aligned Kiswahili worksheet at phone and desktop widths.
- [x] Run frontend checks, document, commit, and push the PDF-language alignment update.

## Legacy Generic Area Title Correction

- [x] Identify every legacy generic template title currently shown as Ukumbi, Eneo la bwawa, Vyumba, or another non-PDF area.
- [x] Map relevant legacy generic areas to the PDF-approved headings ENEO LA NDANI, ENEO LA NJE, VYOONI, OFISINI, BUSTANI, STORE, or MAENDELEO YA WAFANYAKAZI.
- [x] Present any genuinely site-specific legacy survey as a clearly labelled site survey without falsely presenting it as a report-PDF heading.
- [x] Validate Kiswahili and English titles, document, commit, and push the correction.

## Remove Duplicate Legacy Surveys from PDF Worksheet

- [x] Detect and hide legacy generic daily templates from the site-supervisor worksheet whenever official PDF-derived templates are configured for the site.
- [x] Preserve legacy template records and history for audit purposes without presenting duplicate generic survey sections to supervisors.
- [x] Translate all remaining PDF template descriptions and guidance strings into the report’s direct Kiswahili so no English helper text remains in SW mode.
- [x] Add regression coverage for PDF-template preference, duplicate suppression, and complete Kiswahili rendering.
- [x] Run full backend/frontend validation, document, commit, and push the correction.

## PDF Official Heading and Daily Challenges Form

- [x] Remove the redundant TAARIFA YA USAFI · ENEO MAALUM title from official PDF-derived Store and Staff sections, leaving one approved report heading only.
- [x] Add the PDF’s MENGINEYO / CHANGAMOTO ZILIZOJITOKEZA form with seven expanding numbered entries to the daily site-supervisor workflow.
- [x] Persist daily challenge entries with audit history and include them in the report data flow without overwriting prior daily evidence.
- [x] Add role, persistence, heading, and responsive form regression tests.
- [x] Run full validation, document, commit, and push the update.

## Calendar Accuracy and Simplified Supervisor Workflows

- [x] Correct the operational calendar to use the Tanzania local date and accurately highlight the current day rather than the following day.
- [x] Make the selected-day calendar panel fetch and display the complete authorized operational dataset for the chosen day in a full-width, readable layout.
- [x] Convert attendance and trainee-management primary data-entry views into simple Excel-style responsive grids without page-level horizontal scrolling.
- [x] Remove the obsolete inspection/Ukaguzi navigation and workflow entry points while preserving historic records and report evidence.
- [x] Simplify the Raise a Site Issue workflow into a guided, beginner-friendly intake form with clear required fields and actionable feedback.
- [x] Add a unit-of-measure field to configured stock requests, source it from the selected item, preserve it in API/report data, and test the complete request flow.
- [x] Add focused calendar, permissions, spreadsheet UI, issue, and stock-unit regression tests; run full validation, commit, and push.

## Calendar Weekday Header Language

- [x] Use English weekday names only in the operational calendar header, regardless of the dashboard language setting.

## Compact Calendar and Daily Cleanliness Dashboard Refinement

- [x] Use the exact real daily-cleanliness module area names in the dashboard’s selected-day section rather than inspection fallback labels.
- [x] Apply the language switch accurately to all selected-day Daily Cleanliness labels and real area/template names.
- [x] Reduce calendar and Daily Cleanliness selected-day section sizing with responsive compact spacing while preserving readable controls and table access.
- [x] Validate, commit, and push the dashboard refinement.

## Desktop Calendar Footprint Refinement

- [x] Reduce the operational calendar’s desktop-only width, grid cell scale, and selected-day density without changing the approved mobile experience.

## Desktop Calendar Height Correction

- [x] Replace the oversized desktop square month cells with a compact fixed-height calendar grid while preserving the approved mobile layout.
- [x] Reduce desktop selected-day panel density and remove the excessive vertical footprint caused by the calendar section.
- [x] Validate the corrected responsive layout, commit, and push.

## Full-Width Responsive Calendar Redesign

- [x] Redesign the desktop calendar block as a full-width dashboard component aligned with the surrounding KPI cards rather than a narrow centered column.
- [x] Preserve the compact touch-friendly mobile calendar and responsive selected-day information layout.
- [x] Validate the redesigned component at desktop and mobile breakpoints, commit, and push.

## Calendar Live Attendance Correction

- [x] Replace generated-report-only attendance figures in the selected-day calendar with a live aggregate from the authorized daily attendance sheets.
- [x] Preserve report data as a fallback only when live daily sheets cannot be read, with no fabricated counts.
- [x] Add regression coverage and validate the live selected-day attendance calculation before commit and push.

## Zone Supervisor and Assistant General Supervisor Roster Workflow

- [x] Preserve the exact roster/checklist labels, weekday headings, shift headings, off-day labels, and equipment-report headings from `WBCROSTERMASTERPLAN(1).pdf` in a documented source catalogue.
- [x] Add administrator-managed, date-effective personal timetable records that assign a supervisor to authorized sites/zones, work days, morning/afternoon shifts, off-days, optional responsible relief person, and audit metadata.
- [x] Add strict RBAC and data isolation so Zone Supervisors and Assistant General Supervisors only see their own timetable rows, assigned sites/zones, scheduled shifts, and permitted daily submissions.
- [x] Add an administrator timetable-management workspace that creates, revises, cancels, and audits personal roster assignments without exposing a supervisor’s timetable to other supervisors.
- [x] Add a Zone Supervisor calendar dashboard that shows only the logged-in supervisor’s own daily assignment, off-day, shift, relief context, and every site scheduled for that date.
- [x] Add a systematic multi-site Zone Supervisor PDF-derived supervision table using the exact **SUPERVISION CHECKLIST** labels and requiring a scoped record for each assigned site/area.
- [x] Add an Assistant General Supervisor dashboard with the exact **SITE SUPERVISION CHECKLIST** labels and only that supervisor’s assigned timetable sites/zones, works performed, and accountable submission history.
- [x] Add the exact PDF equipment report headings and auditable site-equipment condition/movement workflow for the responsible scheduled supervisor role.
- [x] Include immutable submission snapshots, actor/role/site/shift/date context, review states, and audit history for every supervisor checklist and equipment report.
- [x] Add backend and frontend role-isolation, timetable, shift, off-day, multi-site submission, audit, PDF-label, and responsive-grid regression tests; validate, document, commit, and push.

## Monthly Remuneration Preparation Form

- [x] Preserve the exact remuneration-form heading and columns from `WBC_FOMUYAMISHAHARA.docx.pdf` in a documented source catalogue.
- [x] Add a Site Supervisor remuneration window restricted to the 15th–25th of the selected Tanzania-local month, with clear open/closed state and no payroll calculation outside that window.
- [x] Pre-fill only the authorized site’s active cleaners, their present/absent monthly attendance totals, and start-work date only when the cleaner began during the selected month.
- [x] Add payment-contact confirmation that uses the last approved Yas/Zantel phone and PBZ account when no replacement is entered, while allowing an audited proposed replacement without exposing unmasked prior values broadly.
- [x] Add administrator/HR review of remuneration contact changes and immutable submitted monthly snapshots including authenticated attestation rather than a copied signature image.
- [x] Add a beginner-friendly spreadsheet-style remuneration form, role isolation, window, attendance, new-cleaner, payment-change, review, audit, and responsive-grid regression tests; validate, commit, and push.

## Bilingual Remuneration and Administrator Audit Overview

- [x] Add complete Kiswahili and English translations for the Monthly Remuneration navigation, page title, instructions, workflow states, all spreadsheet columns, actions, payment guidance, and audit messages.
- [x] Add a System Administrator monthly remuneration overview route and navigation entry with an Excel-style, all-site cleaner table filtered by month.
- [x] Include site, cleaner name, worked/present days, absent days, new-worker start date, masked previous payment contacts, proposed replacement contacts, change states, form status, and saved/submitted/reviewed audit actors and times in the administrator view.
- [x] Preserve strict payment-data protection: administrators may review necessary audit information; non-administrators remain limited to their existing scoped and masked view.
- [x] Add localization and administrator-all-site remuneration regression tests; validate, commit, and push.

## Administrator User Management and Role-Scoped Messaging

- [x] Build an administrator user directory with auditable user creation, activation, deactivation, protected deletion/retention policy, role change, password reset/change, full profile review, assignment history, and per-user audit trail.
- [x] Add audited Site Supervisor assignment management: assign authorized site, transfer/change site with effective date, close old assignment, and preserve assignment history.
- [x] Add audited Zone Supervisor zone assignment and transfer management with effective dates, active/inactive status, and historical zone accountability.
- [x] Add audited Assistant General Supervisor zone assignment management, including multi-zone scope where policy permits, transfers, and historical accountability.
- [x] Add General Supervisor account management and governed escalation/review scope without exposing unrelated operational data.
- [x] Define strict role-scoped conversation permissions: Administrators can contact users; Zone Supervisors can contact their assigned Site Supervisors; Assistant and General Supervisors can contact authorized operational roles; all conversations are access-checked at creation and read time.
- [x] Add private direct conversations and governed group conversations with retained membership history, read state, delivery timestamp, retained message audit trail, and bounded group membership governance.
- [x] Add secure document, PDF, image, and voice-message attachments using protected object storage, file-type/size validation, metadata controls, and authorized user-bound download access.
- [x] Add real-time message delivery and inbox UX with safe polling fallback, conversation search, unread counts, responsive WhatsApp-style layout, and no user-scope leakage.
- [x] Add unit/API/UI regression tests for user lifecycle, password changes, role changes, supervisor transfers, conversation permissions, group membership, attachment authorization, realtime fallback, and audits; validate, document, commit, and push.

## Operations Navigation Scrolling Fix

- [x] Make the Operations navigation section independently vertically scrollable so long role-specific menus never overlap the Workspace links on desktop or mobile.
- [x] Keep Workspace links and the sidebar scope summary consistently positioned and accessible after Operations navigation scrolling.
- [x] Validate the corrected desktop and mobile sidebar behavior, then commit and push the fix.

## Premium Operations Scroll Indicator

- [x] Replace the default Operations scrollbar with a refined, low-visual-noise premium indicator that remains usable with mouse, touch, keyboard, and assistive technology.
- [x] Validate, commit, and push the scrollbar refinement.

## Administrator Site Location Picker

- [x] Replace manual latitude/longitude entry in site creation and editing with a map-popup point picker that fills precise coordinates automatically.
- [x] Allow administrators to reopen the picker and correct an existing site pin before saving an update.
- [x] Validate, commit, and push the site location-picker workflow.

## Site Location Picker Credential Fix

- [x] Trace and correct the map-popup failure to load the administrator-configured Mapbox credential.
- [x] Add a clear in-popup loading/error state and validate the configured-token map rendering before committing and pushing the fix.

## Site Pin Persistence and Current Location

- [x] Correct the map-picker coordinate propagation so a clicked or dragged pin saves its selected latitude and longitude instead of zero values.
- [x] Center the picker on the browser’s current location after permission, while retaining an existing site pin or Zanzibar as the fallback.
- [x] Validate, commit, and push the corrected location workflow.

## Persisted Site Pin Display Fix

- [x] Trace why successful site-coordinate PATCH requests reload as “No point selected.”
- [x] Correct the coordinate field mapping and API response handling, validate persistence after reload, then commit and push the fix.
