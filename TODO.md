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
