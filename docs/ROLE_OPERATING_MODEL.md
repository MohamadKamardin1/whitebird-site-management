# White Bird Role Operating Model

## Purpose

White Bird uses role-specific workspaces rather than presenting one generic dashboard to every user. Each role receives only the responsibilities, data scope, actions, and alerts required for its operating mandate. Backend authorization remains authoritative; the frontend menu is a usability layer and must never be treated as access control.

## Capability matrix

| Role | Primary mandate | Data scope | Core workspace | Must not own |
|---|---|---|---|---|
| **System Administrator** | Configure and govern the platform | All tenants, users, sites, zones, and reference data | Administration, users, roles, sites, zones, site configuration, shifts, audit, system health | Daily site execution, trainee performance decisions, routine stock fulfillment |
| **HR** | Own the cleaner and trainee lifecycle | All cleaner records and workforce assignments; sensitive documents according to permission | People registry, onboarding, Excel import, documents, assignments, shifts, trainee qualification, HR audit | Site cleanliness declarations, issue closure, stock fulfillment |
| **Store Manager** | Own stock catalog, inventory control, and supply fulfillment | Assigned stores/sites and all stock requests in the manager’s authorized scope | Store control, configured items, counts, reorder queue, request review, fulfillment, stock audit | HR records, trainee qualification, site inspections |
| **Site Manager / Site Supervisor** | Execute and evidence daily site operations | Assigned site(s), assigned cleaners, assigned trainees, local shifts | Today, attendance, trainee management, cleanliness, inspections, issues/jobs, local reports | Global assignments, user creation, site configuration, stock approval |
| **Zone Supervisor** | Coordinate and review sites in a zone | Assigned zone sites | Zone command centre, exceptions, site reports, jobs, issue escalation, AI brief | Workforce master-data ownership, platform configuration |
| **Assistant General Supervisor** | Coordinate cross-zone operations | Configured cross-zone scope | Cross-zone performance, unresolved exceptions, handovers, reporting quality, AI brief | Platform configuration and HR master-data ownership |
| **General Supervisor** | Own organization-wide operational performance | Organization-wide operational scope | Executive command centre, approvals, escalations, management reports, AI brief | Low-level master-data administration unless explicitly delegated |
| **Management Viewer** | Read-only oversight | Authorized read scope | Read-only summary and reporting | All mutations |

## Lifecycle rules

A cleaner is registered as a **Trainee** by default. A trainee may be assigned to a site by HR, receive a site manager, shift, attendance record, and daily performance evaluation. Only an authorized HR or designated management approval action may transition the cleaner to **Active**, and that transition requires a completed qualifying trainee program and final evaluation evidence. Historical assignments and evaluations are never deleted.

HR is the only routine owner of workforce assignment and shift configuration. Site managers may record execution against the assignments they receive, but cannot silently move a cleaner between sites or alter the workforce master record. System Administrators configure sites, zones, shift definitions, and user accounts, while HR applies operational cleaner-to-site and cleaner-to-shift assignments.

Store Managers control the supply chain after the catalog is configured. Site users submit needs using configured items and quantities; Store Managers review, approve or adjust, fulfill, and record stock movements. Every count, request, approval, and fulfillment event remains auditable.

## Dashboard architecture

The dashboard is intentionally role-specific. Site execution dashboards lead with today’s attendance, trainee follow-up, cleanliness exceptions, inspections, issues, and next actions. HR dashboards lead with onboarding pipeline, incomplete documents, trainees near due date, qualification decisions, assignment conflicts, and import results. Store Manager dashboards lead with low-stock items, open requests, pending fulfillment, stock variance, and recent movements. System Administrator dashboards lead with configuration health, user-role changes, inactive sites, zone coverage, scheduler/API health, and audit anomalies. Leadership dashboards lead with cross-site exceptions, reporting completeness, overdue work, workforce and inventory risks, and AI optimization briefs.

The side panel must be generated from this capability matrix and the authenticated role. Hiding a menu does not replace backend permission checks; every endpoint must independently enforce role and scope.

## Excel onboarding contract

The HR workbook template must include a readable `Instructions` sheet, a validated `Cleaners` sheet, and hidden or protected reference sheets for allowed values. Required fields include legal name, identity type, identity number, gender, birth date, phone, emergency contact, registration date, initial status, site assignment, assignment type, shift, and notes. Excel dropdowns and date/number validations reduce entry mistakes, but the server must revalidate every row, preview all changes, reject unsafe or duplicate rows, and return row-level errors before commit. The import result records the actor, file hash, accepted rows, rejected rows, created cleaners, updated matches, and assignment outcomes.

## Governance principles

AI summaries remain advisory and read-only. A dashboard recommendation cannot create a user, move a cleaner, qualify a trainee, approve a stock request, or change a site. Those actions must use the relevant role-owned audited workflow.
