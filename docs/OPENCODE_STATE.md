# OpenCode Build State

Track of the 20-prompt build of the White Bird Zanzibar — Site Management
Module. Each prompt updates this file before its commit.

## Progress

| Prompt | Title                                        | Status             | Commit |
| ------ | -------------------------------------------- | ------------------ | ------ |
| 1      | Scaffold premium Django foundation           | Prompt 1 completed | —      |
| 2      | Custom user, RBAC and auth foundation        | Prompt 2 completed | —      |
| 3      | Shared kernel: audit, files, events, errors  | Prompt 3 completed | —      |
| 4      | Organisation hierarchy (zones/sites/supervisors) | **Prompt 4 completed** | see CHANGELOG |
| 5–20   | (pending)                                    | —                  | —      |

## Prompt 4 — completed ✅

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
