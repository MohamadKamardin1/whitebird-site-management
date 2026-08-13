"""User and API token models."""

import secrets
from typing import Any

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone

from apps.common.models import TimeStampedModel


class Role(models.TextChoices):
    """Platform-level roles.

    Roles gate authorization and therefore live in code rather than the
    database. Domain *catalog* data (site types, statuses, asset categories)
    is configuration-driven through dedicated models.
    """

    ADMIN = "admin", "Administrator"
    MANAGER = "manager", "Manager"
    STAFF = "staff", "Staff"
    VIEWER = "viewer", "Viewer"


class User(AbstractUser):
    role = models.CharField(max_length=16, choices=Role.choices, default=Role.STAFF)
    phone = models.CharField(max_length=32, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "User"
        verbose_name_plural = "Users"
        ordering = ["-date_joined"]

    def __str__(self) -> str:
        return self.get_username()

    @property
    def is_admin(self) -> bool:
        return self.role == Role.ADMIN or self.is_superuser


class ApiToken(TimeStampedModel):
    """Bearer token for machine-to-machine access to the REST API."""

    user = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="api_tokens",
    )
    name = models.CharField(max_length=64, blank=True, default="")
    key = models.CharField(max_length=128, unique=True, editable=False, db_index=True)
    is_active = models.BooleanField(default=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    last_used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "API token"
        verbose_name_plural = "API tokens"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"token:{self.pk} ({self.user})"

    def save(self, *args: Any, **kwargs: Any) -> None:
        if not self.key:
            self.key = secrets.token_urlsafe(43)
        super().save(*args, **kwargs)

    @property
    def is_expired(self) -> bool:
        return bool(self.expires_at and self.expires_at <= timezone.now())

    @property
    def usable(self) -> bool:
        return self.is_active and not self.is_expired
