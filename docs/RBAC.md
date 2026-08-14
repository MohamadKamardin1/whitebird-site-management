# Role-Based Access Control

Permission-relevant roles are **code-enforced constants** (`apps.accounts.models.RoleCode`),
never database configuration, because authorization must be verifiable in code.
Each role maps to a Django group (`apps.accounts.rbac.ROLE_GROUP_NAMES`) that
carries the role's model + custom permissions; group membership is synced
automatically when a user's role changes.

## Roles

| Role                            | `RoleCode` value                      | Domain persona                 |
| ------------------------------- | ------------------------------------- | ------------------------------ |
| System Admin                    | `system_admin`                        | Platform administration        |
| General Supervisor              | `general_supervisor`                  | Top of the ops reporting chain |
| Assistant General Supervisor    | `assistant_general_supervisor`        | Deputy to the general          |
| Zone Supervisor                 | `zone_supervisor`                     | Owns a zone of sites           |
| Site Supervisor                 | `site_supervisor`                     | Owns a single site             |
| Management Viewer               | `management_viewer`                   | Read-only dashboards/reports   |

## Capability matrix

| Capability                                          | SysAdmin | General | Asst. General | Zone | Site | Viewer |
| --------------------------------------------------- | :------: | :-----: | :-----------: | :--: | :--: | :----: |
| Full platform administration (users, tokens, RBAC)  |    ✔️    |    —    |       —       |  —   |  —   |   —    |
| Create users / manage all sites                     |    ✔️    |    —    |       —       |  —   |  —   |   —    |
| Write to assigned sites                             |    ✔️    |   ✔️    |       ✔️      |  ✔️  |  ✔️  |   —    |
| Read any site                                       |    ✔️    |   ✔️    |       ✔️      |  ✔️  |  ✔️  |   —    |
| Read assigned sites only                            |    ✔️    |   ✔️    |       ✔️      |  ✔️  |  ✔️  |   ✔️   |
| View audit logs                                     |    ✔️    |   ✔️    |       ✔️      |  ✔️  |  ✔️  |   —    |
| Cross-site statistics overview                      |    ✔️    |    —    |       —       |  —   |  —   |   —    |
| API token lifecycle                                 |    ✔️    |   self  |      self     | self | self |  self  |

> `self` = the user may manage **their own** tokens only.

## Site-scoped roles (`StaffAssignment`)

Within a site, a user may carry a site-level role that grants write capacity:

| Site role      | Write on that site |
| -------------- | :----------------: |
| `site_manager` | ✔️                  |
| `staff`        | —                  |

**Effective write rule:** a user may modify a site if they are a **system
admin**, or they have an assignment to that site **and** (their platform role
is a supervisor role **or** their site role is `site_manager`).

## Custom permissions

Defined on the `User` model and assigned to groups by `seed_rbac`:

| Permission                        | Granted to                                                       |
| --------------------------------- | ---------------------------------------------------------------- |
| `submit_site_report`              | General, Assistant, Zone, Site                                    |
| `review_zone_report`              | Zone                                                              |
| `review_assistant_report`         | General, Assistant                                                |
| `approve_general_report`          | General                                                           |
| `assign_job` / `verify_job`       | General, Assistant, Zone, Site                                    |
| `approve_trainee`                 | General, Assistant                                                |
| `manage_site_configuration`       | Assistant, Zone, Site                                             |
| `view_sensitive_cleaner_documents`| General, Assistant                                                |
| `export_site_management_data`     | All roles (viewer may export read-only data)                      |

## RBAC seeding

`python manage.py seed_rbac` is **idempotent**: it creates the six groups and
assigns the exact permission set declared in `apps/accounts.rbac`. Users are
added to their role's group automatically by a `post_save` signal, so
`user.has_perm(...)` works without manual group management.

## Enforcement points

- Routers call `role_required(...)` and site-scoped `_read_access` /
  `_write_access` before any service call.
- Services assume the caller passed authorization; they never re-authorize.
- Superusers bypass all checks (`is_system_admin` includes superusers).

## Data scoping (organisation hierarchy)

Scoping selectors (`apps/site_management/scoping.py`) answer "what can this
user see/supervise?":

| Role                            | `visible_sites` / `visible_zones`        | `supervised_sites` (write)          |
| ------------------------------- | ---------------------------------------- | ----------------------------------- |
| System Admin                    | all                                      | all                                 |
| General Supervisor              | all                                      | all                                 |
| Assistant General Supervisor    | all if `all_zones`, else assigned zones  | same                                |
| Zone Supervisor                 | assigned zones' sites                    | assigned zones' sites               |
| Site Supervisor                 | actively assigned sites only             | actively assigned sites only        |
| Management Viewer               | all (read-only)                          | none                                |

Write capacity for a site (`user_can_manage_site`):

- System admin or general supervisor → yes.
- Site supervisor with an active `SiteSupervisorAssignment` → yes.
- Zone supervisor / assistant general whose scope includes the site → yes.
- Management viewer → never.

Supervisor assignments are date-windowed (`assigned_from`/`assigned_to`),
soft-deactivatable (`is_active`), and enforce one active assignment per
user+site/zone plus a constance-driven per-site supervisor cap.
