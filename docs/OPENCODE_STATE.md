# OpenCode Build State

Track of the 20-prompt build of the White Bird Zanzibar — Site Management
Module. Each prompt updates this file before its commit.

## Progress

| Prompt | Title                                        | Status             | Commit |
| ------ | -------------------------------------------- | ------------------ | ------ |
| 1      | Scaffold premium Django foundation           | Prompt 1 completed | —      |
| 2      | Custom user, RBAC and auth foundation        | **Prompt 2 completed** | see CHANGELOG |
| 3–20   | (pending)                                    | —                  | —      |

## Prompt 2 — completed ✅

Built `apps.accounts` into a production-grade accounts system:

- **Custom user**: email-identified `AbstractBaseUser` + `PermissionsMixin`,
  case-insensitive unique email, validated Tanzania/E.164 phone, IANA
  timezone (default `Africa/Dar_es_Salaam`), optional avatar, `full_name`,
  `created_at`/`updated_at`, `last_login`, custom `UserManager`.
- **Roles**: `RoleCode` enum with the six platform roles and per-role helper
  methods (`is_system_admin`, `is_site_supervisor`, …).
- **RBAC**: Django groups per role + model/custom permissions, declarative
  matrix in `apps/accounts/rbac.py`, idempotent `seed_rbac` command, and a
  `post_save` signal that keeps users in their role group.
- **Authentication**: signed access tokens + revocable refresh tokens
  (`apps/accounts/tokens.py`), `TokenAuth` bearer scheme, email login,
  `/auth/login|refresh|logout|me|password-change`, django-axes lockout,
  password validators (min 12), session auth views + password-reset
  templates at `/accounts/`.
- **Admin**: professional `UserAdmin` (role/active filters, activate/
  deactivate actions, deletion guard for users with history, readonly audit
  fields).
- **Timezone middleware**, audit-ready services, factory-boy factories for
  every role.

**Quality gates (all green):** Ruff · Mypy strict · pytest 131 passed ·
coverage 93.1% ≥ 90 · `makemigrations --check` clean.
