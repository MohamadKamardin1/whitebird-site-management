# OpenCode Build State

Track of the 20-prompt build of the White Bird Zanzibar — Site Management
Module. Each prompt updates this file before its commit.

## Progress

| Prompt | Title                                        | Status             | Commit |
| ------ | -------------------------------------------- | ------------------ | ------ |
| 1      | Scaffold premium Django foundation           | Prompt 1 completed | —      |
| 2      | Custom user, RBAC and auth foundation        | Prompt 2 completed | —      |
| 3      | Shared kernel: audit, files, events, errors  | **Prompt 3 completed** | see CHANGELOG |
| 4–20   | (pending)                                    | —                  | —      |

## Prompt 3 — completed ✅

Built `apps.core` into the shared kernel:

- **Base models**: `TimeStampedModel`, `UserStampedModel` (`SET_NULL` user
  refs), `ActivatableModel` (soft-delete), `CodeSlugModel`.
- **Audit logging**: redesigned `AuditLog` (`user`, `action`, `model_name`,
  `object_id`, `object_repr`, `before_data`/`after_data`, `ip_address`,
  `request_id`) + `record_audit` service with backward-compatible aliases and
  `model_data()` snapshots. `create_site`/`update_site` record real snapshots.
- **Request-ID middleware** (`X-Request-ID`, contextvar, log filter, response
  header) with `trace_id` in every structured log line.
- **Domain errors + API error contract**: `DomainError` hierarchy and Ninja
  handlers mapping to the shared `{"error": {code, message, trace_id,
  fields}}` envelope (ValidationError→422, DoesNotExist→404,
  PermissionDenied→403, ConflictError→409, BusinessRuleError, unexpected→500).
- **Pagination & sorting**: `PageParams`, `Paginated` envelope (count/next/
  previous/results), constance-driven defaults/caps, whitelisted sorting.
- **Private file foundation**: `PrivateMediaStorage` (no public URL),
  extension/size validators, `PrivateFileModel`, signed download tokens (TTL
  from constance), and a secure `/files/signed/{token}/` streaming endpoint
  that audits downloads.
- **Domain-event outbox**: `DomainEvent` model + `publish_domain_event()`
  (created via `transaction.on_commit`).
- **Cache utilities**: keys namespaced under `wbz_site`, `get_or_set`,
  versioned keys, safe delete, prefix invalidation.
- **Layering helpers**: `apps/core/policies.py` and `apps/core/validators.py`.

**Quality gates (all green):** Ruff · Mypy strict (101 files) · pytest 170
passed · coverage 92.5% ≥ 90 · `makemigrations --check` clean.
