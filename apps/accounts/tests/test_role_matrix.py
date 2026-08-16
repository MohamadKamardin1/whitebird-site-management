from apps.accounts.models import RoleCode, User
from apps.accounts.rbac import ROLE_GROUP_NAMES, group_permission_codenames


def test_hr_and_store_manager_are_first_class_roles() -> None:
    assert ROLE_GROUP_NAMES[RoleCode.HR] == "Human Resources"
    assert ROLE_GROUP_NAMES[RoleCode.STORE_MANAGER] == "Store Manager"
    assert ("accounts", "import_cleaners") in group_permission_codenames(RoleCode.HR)
    assert ("accounts", "manage_trainee_lifecycle") in group_permission_codenames(RoleCode.HR)
    assert ("accounts", "manage_store_inventory") in group_permission_codenames(RoleCode.STORE_MANAGER)


def test_management_role_helper_includes_workforce_and_inventory_managers() -> None:
    hr = User(email="hr@example.com", role=RoleCode.HR)
    store_manager = User(email="store@example.com", role=RoleCode.STORE_MANAGER)
    assert hr.is_management_role
    assert store_manager.is_management_role
