"""RBAC data: role → group → permission matrix.

Single source of truth consumed by the ``seed_rbac`` command and by the
role-group sync signal, keeping runtime data consistent with the code.
"""

from __future__ import annotations

from .models import RoleCode

#: Display name of the Django group that mirrors each platform role.
ROLE_GROUP_NAMES: dict[RoleCode, str] = {
    RoleCode.SYSTEM_ADMIN: "System Admin",
    RoleCode.GENERAL_SUPERVISOR: "General Supervisor",
    RoleCode.ASSISTANT_GENERAL_SUPERVISOR: "Assistant General Supervisor",
    RoleCode.ZONE_SUPERVISOR: "Zone Supervisor",
    RoleCode.SITE_SUPERVISOR: "Site Supervisor",
    RoleCode.MANAGEMENT_VIEWER: "Management Viewer",
}

_CUSTOM_PERMISSIONS = [
    "submit_site_report",
    "review_zone_report",
    "review_assistant_report",
    "approve_general_report",
    "assign_job",
    "verify_job",
    "approve_trainee",
    "manage_site_configuration",
    "manage_cleaners",
    "view_sensitive_cleaner_documents",
    "export_site_management_data",
]

# app_label -> model names whose permissions are managed by the platform.
_MODEL_REGISTRY: dict[str, list[str]] = {
    "accounts": ["user", "apitoken"],
    "site_management": [
        "site",
        "sitetype",
        "sitestatus",
        "department",
        "asset",
        "assetcategory",
        "staffassignment",
        "notification",
    ],
}


def _model_perms(app_label: str, actions: tuple[str, ...]) -> set[tuple[str, str]]:
    perms: set[tuple[str, str]] = set()
    for model in _MODEL_REGISTRY[app_label]:
        for action in actions:
            perms.add((app_label, f"{action}_{model}"))
    return perms


def _view_all() -> set[tuple[str, str]]:
    return _model_perms("accounts", ("view",)) | _model_perms("site_management", ("view",))


def _change_site_operations() -> set[tuple[str, str]]:
    return _model_perms(
        "site_management",
        ("change", "add", "view"),
    ) | {("accounts", "view_user")}


def _custom(*codenames: str) -> set[tuple[str, str]]:
    return {("accounts", codename) for codename in codenames}


ROLE_PERMISSIONS: dict[RoleCode, set[tuple[str, str]]] = {
    RoleCode.SYSTEM_ADMIN: (
        _model_perms("accounts", ("view", "add", "change", "delete"))
        | _model_perms("site_management", ("view", "add", "change", "delete"))
        | _custom(*_CUSTOM_PERMISSIONS)
    ),
    RoleCode.GENERAL_SUPERVISOR: (
        _view_all()
        | _change_site_operations()
        | _custom(
            "submit_site_report",
            "review_assistant_report",
            "approve_general_report",
            "assign_job",
            "verify_job",
            "approve_trainee",
            "manage_cleaners",
            "view_sensitive_cleaner_documents",
            "export_site_management_data",
        )
    ),
    RoleCode.ASSISTANT_GENERAL_SUPERVISOR: (
        _view_all()
        | _change_site_operations()
        | _custom(
            "submit_site_report",
            "review_assistant_report",
            "assign_job",
            "verify_job",
            "approve_trainee",
            "manage_site_configuration",
            "view_sensitive_cleaner_documents",
            "export_site_management_data",
        )
    ),
    RoleCode.ZONE_SUPERVISOR: (
        _view_all()
        | _change_site_operations()
        | _custom(
            "submit_site_report",
            "review_zone_report",
            "assign_job",
            "verify_job",
            "manage_site_configuration",
            "export_site_management_data",
        )
    ),
    RoleCode.SITE_SUPERVISOR: (
        _view_all()
        | _change_site_operations()
        | _custom(
            "submit_site_report",
            "assign_job",
            "verify_job",
            "manage_site_configuration",
        )
    ),
    RoleCode.MANAGEMENT_VIEWER: (_view_all() | _custom("export_site_management_data")),
}


def group_permission_codenames(role: RoleCode) -> set[tuple[str, str]]:
    """Return the ``(app_label, codename)`` pairs for a role's group."""
    return ROLE_PERMISSIONS[role]
