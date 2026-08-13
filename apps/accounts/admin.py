"""Admin configuration for the accounts app."""

from typing import Any

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import ApiToken, User


@admin.register(User)
class CustomUserAdmin(UserAdmin):  # type: ignore[type-arg]
    list_display = ("username", "email", "first_name", "last_name", "role", "is_staff", "is_active")
    list_filter = ("role", "is_staff", "is_active", "date_joined")
    fieldsets = (
        (None, {"fields": ("username", "password")}),
        ("Personal info", {"fields": ("first_name", "last_name", "email")}),
        (
            "Permissions",
            {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")},
        ),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
        ("Platform", {"fields": ("role", "phone")}),
    )


@admin.register(ApiToken)
class ApiTokenAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ("user", "name", "is_active", "expires_at", "last_used_at", "created_at")
    list_filter = ("is_active", "created_at")
    search_fields = ("user__username", "name")
    readonly_fields = ("key", "last_used_at", "created_at", "updated_at")
    actions = ["revoke"]

    @admin.action(description="Revoke selected tokens")
    def revoke(self, request: Any, queryset: Any) -> None:
        queryset.update(is_active=False)
