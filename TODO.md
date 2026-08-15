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
