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
| 5      | Site configuration (shifts/areas/roles) | **Prompt 5 completed** | see CHANGELOG |
| 6–20   | (pending)                                    | —                  | —      |

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
