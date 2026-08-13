"""Admin configuration for the accounts app.

The user admin favours deactivation over deletion: users with operational
history (audit entries, assignments, tokens) cannot be hard-deleted, matching
the audit-friendly design of the platform.
"""

from __future__ import annotations

from typing import Any

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone

from .models import ApiToken, User


@admin.register(User)
class CustomUserAdmin(UserAdmin):  # type: ignore[type-arg]
    list_display = (
        "email",
        "full_name",
        "role",
        "phone",
        "is_staff",
        "is_superuser",
        "is_active",
        "created_at",
    )
    list_filter = ("role", "is_staff", "is_superuser", "is_active", "created_at")
    search_fields = ("email", "first_name", "last_name", "phone")
    ordering = ("-created_at",)
    actions = ["activate_users", "deactivate_users"]
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "password1", "password2", "role", "is_staff", "is_superuser"),
            },
        ),
    )
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (
            "Personal info",
            {"fields": ("first_name", "last_name", "phone", "timezone", "avatar")},
        ),
        (
            "Role & permissions",
            {"fields": ("role", "is_active", "is_staff", "is_superuser", "groups", "user_permissions")},
        ),
        ("Audit", {"fields": ("created_at", "updated_at", "last_login"), "classes": ("collapse",)}),
    )
    readonly_fields = ("created_at", "updated_at", "last_login")

    @admin.display(description="Full name", ordering="first_name")
    def full_name(self, obj: User) -> str:
        return obj.full_name

    @admin.action(description="Activate selected users")
    def activate_users(self, request: Any, queryset: Any) -> None:
        updated = queryset.update(is_active=True, updated_at=timezone.now())
        self.message_user(request, f"{updated} user(s) activated.")

    @admin.action(description="Deactivate selected users")
    def deactivate_users(self, request: Any, queryset: Any) -> None:
        updated = queryset.update(is_active=False, updated_at=timezone.now())
        self.message_user(request, f"{updated} user(s) deactivated.")

    def delete_model(self, request: Any, obj: User) -> None:
        self._guard_delete(obj)
        super().delete_model(request, obj)

    def delete_queryset(self, request: Any, queryset: Any) -> None:
        for obj in queryset:
            self._guard_delete(obj)
        super().delete_queryset(request, queryset)

    def _guard_delete(self, user: User) -> None:
        if user.has_operational_history:
            raise DjangoValidationError(
                f"Cannot delete {user.email}: user has audit history, assignments, or tokens. "
                "Deactivate the account instead."
            )

    def has_delete_permission(self, request: Any, obj: User | None = None) -> bool:
        if obj is None:
            return True
        return not obj.has_operational_history


@admin.register(ApiToken)
class ApiTokenAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ("user", "name", "is_active", "expires_at", "last_used_at", "created_at")
    list_filter = ("is_active", "created_at")
    search_fields = ("user__email", "name")
    readonly_fields = ("key", "last_used_at", "created_at", "updated_at")
    actions = ["revoke"]

    @admin.action(description="Revoke selected tokens")
    def revoke(self, request: Any, queryset: Any) -> None:
        queryset.update(is_active=False)
