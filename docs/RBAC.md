# Role-Based Access Control — Draft Matrix

Permission-relevant roles are **code-enforced constants** (never database
configuration), because authorization must be verifiable in code. This matrix
is the reference for every permission check and for the admin dashboard.

## Platform roles

| Capability                                     | Admin | Manager | Staff | Viewer |
| ---------------------------------------------- | :---: | :-----: | :---: | :----: |
| Full platform administration (users, tokens)   |  ✔️   |    —    |   —   |   —    |
| Manage all sites                               |  ✔️   |    —    |   —   |   —    |
| Manage assigned sites (write)                  |  ✔️   |   ✔️    |   —   |   —    |
| Read any site                                  |  ✔️   |   ✔️    |   —   |   —    |
| Read assigned sites only                       |  ✔️   |   ✔️    |  ✔️   |   ✔️   |
| Assign/unassign staff to sites                 |  ✔️   |   ✔️    |   —   |   —    |
| Manage departments / assets                    |  ✔️   |   ✔️    |   —   |   —    |
| View audit logs                                |  ✔️   |   ✔️    |   —   |   —    |
| View cross-site statistics overview            |  ✔️   |    —    |   —   |   —    |
| API token lifecycle                            |  ✔️   |  self   | self  | self   |

> `self` = the user may manage **their own** tokens only.

## Site-scoped roles (`StaffAssignment`)

Within a site, a user may carry a site-level role that grants write capacity
independent of their platform role:

| Site role       | Write on that site |
| --------------- | :----------------: |
| `site_manager`  | ✔️                  |
| `staff`         | —                  |

**Effective write rule:** a user may modify a site if they are an *admin*,
**or** they have an assignment to that site **and** (their platform role is
`manager` **or** their site role is `site_manager`).

## Domain roles (future prompts)

These domain personas map onto the platform roles for now:

| Domain persona             | Platform role  | Notes                                   |
| -------------------------- | -------------- | --------------------------------------- |
| General Supervisor         | `manager`      | + future zone-wide scope                |
| Assistant General Supervisor | `manager`     | + future escalation scope               |
| Zone Supervisor            | `manager`      | scoped to assigned sites                |
| Site Supervisor            | `manager`/`staff` + `site_manager` assignment | write on their site |
| Management Viewer          | `viewer`       | read-only                               |
| Cleaners / Trainees        | `staff`        | read-only on assigned site; task-execution scoped by future tasks |

## Enforcement points

- Routers call `role_required(...)` and site-scoped `_read_access` /
  `_write_access` before any service call.
- Services assume the caller passed authorization; they never re-authorize.
- Superusers bypass all checks (`is_admin`).
