"""Tests for the custom user admin."""

import pytest
from django.core.exceptions import ValidationError as DjangoValidationError
from django.test import Client

from apps.accounts.admin import CustomUserAdmin
from apps.accounts.factories import UserFactory
from apps.accounts.models import User
from apps.core.models import AuditLog


@pytest.mark.django_db
def test_admin_login_uses_email(admin_user: User) -> None:
    response = Client().post(
        "/admin/login/",
        data={"username": admin_user.email, "password": "admin-password-1"},
    )
    # Successful admin login redirects to the index.
    assert response.status_code == 302


@pytest.mark.django_db
def test_delete_permission_denied_for_users_with_history(admin_user: User) -> None:
    target = UserFactory()
    AuditLog.objects.create(
        actor=target,
        action="create",
        entity_type="accounts.user",
        entity_id=str(target.pk),
    )
    admin = CustomUserAdmin(model=User, admin_site=None)
    assert admin.has_delete_permission(request=None, obj=target) is False
    assert admin.has_delete_permission(request=None, obj=None) is True


@pytest.mark.django_db
def test_delete_permission_allowed_for_fresh_users(admin_user: User) -> None:
    target = UserFactory()
    admin = CustomUserAdmin(model=User, admin_site=None)
    assert admin.has_delete_permission(request=None, obj=target) is True


@pytest.mark.django_db
def test_guard_delete_raises_for_users_with_history() -> None:
    user = UserFactory()
    AuditLog.objects.create(actor=user, action="create", entity_type="x", entity_id="1")
    admin = CustomUserAdmin(model=User, admin_site=None)
    with pytest.raises(DjangoValidationError):
        admin._guard_delete(user)


@pytest.mark.django_db
def test_activate_and_deactivate_actions(admin_user: User) -> None:
    client = Client()
    client.force_login(admin_user)
    target = UserFactory(is_active=False)

    response = client.post(
        "/admin/accounts/user/",
        data={"action": "activate_users", "_selected_action": [target.pk]},
    )
    assert response.status_code == 302
    target.refresh_from_db()
    assert target.is_active is True

    response = client.post(
        "/admin/accounts/user/",
        data={"action": "deactivate_users", "_selected_action": [target.pk]},
    )
    assert response.status_code == 302
    target.refresh_from_db()
    assert target.is_active is False


@pytest.mark.django_db
def test_admin_requires_staff(admin_user: User, viewer_user: User) -> None:
    viewer = UserFactory(is_active=True, is_staff=False)
    client = Client()
    client.force_login(viewer)
    assert client.get("/admin/").status_code == 302
