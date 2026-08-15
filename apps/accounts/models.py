"""User, role, and API token models for the White Bird platform.

The user model is email-identified (``AbstractBaseUser`` + ``PermissionsMixin``)
per Django authentication best practice. Roles gate authorization and are
code-enforced constants; the domain *catalog* data remains configuration-driven.
"""

from __future__ import annotations

import secrets
from typing import Any, ClassVar

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.core.mail import send_mail
from django.db import models
from django.utils import timezone

from apps.core.models import TimeStampedModel

from .validators import validate_phone, validate_timezone


class RoleCode(models.TextChoices):
    """Platform-level roles.

    Roles gate authorization and therefore live in code rather than the
    database. Permission-relevant role definitions are never runtime
    configuration; only reference data is.
    """

    SYSTEM_ADMIN = "system_admin", "System Admin"
    SITE_SUPERVISOR = "site_supervisor", "Site Supervisor"
    ZONE_SUPERVISOR = "zone_supervisor", "Zone Supervisor"
    ASSISTANT_GENERAL_SUPERVISOR = "assistant_general_supervisor", "Assistant General Supervisor"
    GENERAL_SUPERVISOR = "general_supervisor", "General Supervisor"
    MANAGEMENT_VIEWER = "management_viewer", "Management Viewer"


# Roles with operational management capacity over sites.
SUPERVISOR_ROLES = frozenset(
    {
        RoleCode.SITE_SUPERVISOR,
        RoleCode.ZONE_SUPERVISOR,
        RoleCode.ASSISTANT_GENERAL_SUPERVISOR,
        RoleCode.GENERAL_SUPERVISOR,
    }
)


class UserManager(BaseUserManager["User"]):
    """Manager for the email-identified user model."""

    use_in_migrations = True

    def _normalize_email(self, email: str) -> str:
        return (email or "").strip().lower()

    def create_user(self, email: str, password: str | None = None, **extra_fields: Any) -> User:
        """Create and save a regular user with the given email and password."""
        if not email:
            raise ValueError("Users must have an email address.")
        email = self._normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email: str, password: str | None = None, **extra_fields: Any) -> User:
        """Create and save a superuser with the given email and password."""
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("role", RoleCode.SYSTEM_ADMIN)
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")
        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """Email-identified platform user with a professional role model."""

    email = models.EmailField(
        unique=True,
        db_index=True,
        error_messages={"unique": "A user with that email already exists."},
    )
    phone = models.CharField(
        max_length=16,
        blank=True,
        default="",
        validators=[validate_phone],
        help_text="Tanzanian or international E.164 format, e.g. +2557xx xxx xxx.",
    )
    first_name = models.CharField(max_length=150, blank=True, default="")
    last_name = models.CharField(max_length=150, blank=True, default="")
    role = models.CharField(max_length=40, choices=RoleCode.choices, default=RoleCode.MANAGEMENT_VIEWER)
    timezone = models.CharField(
        max_length=64,
        default="Africa/Dar_es_Salaam",
        validators=[validate_timezone],
        help_text="IANA timezone used for date rendering and notifications.",
    )
    avatar = models.ImageField(upload_to="avatars/%Y/%m/", blank=True, null=True)
    is_active = models.BooleanField(
        default=True,
        help_text="Inactive accounts cannot log in and are excluded from operations.",
    )
    is_staff = models.BooleanField(
        default=False,
        help_text="Designates whether the user can log into the Django admin.",
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: ClassVar[list[str]] = []

    class Meta:
        verbose_name = "User"
        verbose_name_plural = "Users"
        ordering = ["-created_at"]
        permissions = [
            ("submit_site_report", "Can submit site reports"),
            ("review_zone_report", "Can review zone reports"),
            ("review_assistant_report", "Can review assistant general supervisor reports"),
            ("approve_general_report", "Can approve general supervisor reports"),
            ("assign_job", "Can assign jobs"),
            ("verify_job", "Can verify completed jobs"),
            ("approve_trainee", "Can approve trainees"),
            ("manage_site_configuration", "Can manage site configuration"),
            ("manage_cleaners", "Can register and onboard cleaners"),
            ("view_sensitive_cleaner_documents", "Can view sensitive cleaner documents"),
            ("export_site_management_data", "Can export site management data"),
        ]

    def __str__(self) -> str:
        return self.email

    @property
    def full_name(self) -> str:
        """Full name, falling back to the email when no names are set."""
        name = f"{self.first_name} {self.last_name}".strip()
        return name or self.email

    def get_full_name(self) -> str:
        return self.full_name

    def get_short_name(self) -> str:
        return self.first_name or self.email

    def email_user(self, subject: str, message: str, from_email: str | None = None) -> None:
        send_mail(subject, message, from_email, [self.email])

    def save(self, *args: Any, **kwargs: Any) -> None:
        # Enforce case-insensitive unique emails at the model layer.
        if self.email:
            self.email = self.email.strip().lower()
        super().save(*args, **kwargs)

    # ------------------------------------------------------------------ #
    # Role helpers
    # ------------------------------------------------------------------ #

    @property
    def is_system_admin(self) -> bool:
        return self.role == RoleCode.SYSTEM_ADMIN or self.is_superuser

    @property
    def is_site_supervisor(self) -> bool:
        return self.role == RoleCode.SITE_SUPERVISOR

    @property
    def is_zone_supervisor(self) -> bool:
        return self.role == RoleCode.ZONE_SUPERVISOR

    @property
    def is_assistant_general_supervisor(self) -> bool:
        return self.role == RoleCode.ASSISTANT_GENERAL_SUPERVISOR

    @property
    def is_general_supervisor(self) -> bool:
        return self.role == RoleCode.GENERAL_SUPERVISOR

    @property
    def is_management_viewer(self) -> bool:
        return self.role == RoleCode.MANAGEMENT_VIEWER

    @property
    def is_supervisor(self) -> bool:
        """True for any operational management role (not admin/viewer)."""
        return self.role in SUPERVISOR_ROLES

    @property
    def is_management_role(self) -> bool:
        """True for admins and supervisors; false for read-only viewers."""
        return self.is_system_admin or self.role in SUPERVISOR_ROLES

    @property
    def is_admin(self) -> bool:
        """Backwards-compatible alias for ``is_system_admin``."""
        return self.is_system_admin

    @property
    def role_label(self) -> str:
        return RoleCode(self.role).label

    @property
    def has_operational_history(self) -> bool:
        """True when the user holds audit, assignment, or token records.

        Guards the admin against accidental hard deletion of users with
        historical data (see ``CustomUserAdmin``).
        """
        return self.audit_logs.exists() or self.staff_assignments.exists() or self.api_tokens.exists()


class ApiToken(TimeStampedModel):
    """Revocable bearer token used as the refresh credential / machine token."""

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
        return f"token:{self.pk} ({self.user.email})"

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
