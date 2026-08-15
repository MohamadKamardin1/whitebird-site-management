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
