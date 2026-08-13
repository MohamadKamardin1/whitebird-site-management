"""Core shared models: base models, audit log, domain event outbox, private files.

``apps.core`` is the shared kernel — it contains no business logic. Domain
apps inherit these abstractions and use the audit/event/file services.
"""

from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models

from .files import PrivateMediaStorage
from .managers import SoftDeleteManager


class TimeStampedModel(models.Model):
    """Abstract base providing immutable created/updated timestamps."""

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class UserStampedModel(TimeStampedModel):
    """Adds created_by/updated_by audit references.

    Both FKs are nullable and ``on_delete=SET_NULL`` so historical records
    survive user deletion.
    """

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )

    class Meta:
        abstract = True


class ActivatableModel(models.Model):
    """Adds an ``is_active`` flag with soft-delete manager semantics."""

    is_active = models.BooleanField(default=True, db_index=True)
    objects = SoftDeleteManager()

    class Meta:
        abstract = True


class CodeSlugModel(models.Model):
    """Adds stable business ``code`` and human ``slug`` identifiers."""

    code = models.CharField(max_length=32, unique=True, db_index=True)
    slug = models.SlugField(max_length=120, unique=True, db_index=True)

    class Meta:
        abstract = True


class AuditLog(models.Model):
    """Append-only trail of who changed what, when, and from where.

    ``before_data``/``after_data`` hold JSON snapshots of the affected record.
    The trail is write-only from the admin; nothing here is editable.
    """

    class Action(models.TextChoices):
        CREATE = "create", "Create"
        UPDATE = "update", "Update"
        DELETE = "delete", "Delete"
        ARCHIVE = "archive", "Archive"
        RESTORE = "restore", "Restore"
        STATUS_CHANGE = "status_change", "Status Change"
        ASSIGN = "assign", "Assign"
        UNASSIGN = "unassign", "Unassign"
        LOGIN = "login", "Login"
        TOKEN_CREATE = "token_create", "Token Create"
        TOKEN_REVOKE = "token_revoke", "Token Revoke"
        FILE_DOWNLOAD = "file_download", "File Download"
        EVENT_PUBLISHED = "event_published", "Event Published"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
        help_text="User who performed the action; null for system actors.",
    )
    action = models.CharField(max_length=32, choices=Action.choices, db_index=True)
    model_name = models.CharField(max_length=96, db_index=True)
    object_id = models.CharField(max_length=36, db_index=True)
    object_repr = models.CharField(max_length=255, blank=True, default="")
    before_data = models.JSONField(default=dict, blank=True)
    after_data = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    request_id = models.CharField(max_length=64, blank=True, default="", db_index=True)
    summary = models.CharField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "Audit log"
        verbose_name_plural = "Audit logs"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["model_name", "object_id"]),
            models.Index(fields=["user", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.action} {self.model_name}:{self.object_id} by {self.user_id}"


class DomainEvent(models.Model):
    """Transactional outbox record for future Office Management integration.

    Events are created inside the producing transaction (via
    ``transaction.on_commit``) and later published to external consumers by a
    worker. No publisher is wired up yet — events are stored professionally.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PUBLISHED = "published", "Published"
        FAILED = "failed", "Failed"

    event_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_index=True)
    event_type = models.CharField(max_length=128, db_index=True)
    aggregate_type = models.CharField(max_length=128, db_index=True)
    aggregate_id = models.CharField(max_length=36, db_index=True)
    payload = models.JSONField(default=dict, blank=True)
    schema_version = models.PositiveSmallIntegerField(default=1)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING, db_index=True)
    occurred_at = models.DateTimeField(auto_now_add=True, db_index=True)
    published_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )

    class Meta:
        verbose_name = "Domain event"
        verbose_name_plural = "Domain events"
        ordering = ["-occurred_at"]
        indexes = [
            models.Index(fields=["status", "occurred_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.event_type} {self.aggregate_type}:{self.aggregate_id} ({self.status})"


class PrivateFileModel(TimeStampedModel):
    """Abstract model for records that carry a privately-stored file.

    Cleaner documents, inspection photos and job photos inherit this so the
    signed-download service can resolve their ``file`` field uniformly. The
    file is stored on the private storage backend and is never served from a
    public URL — access goes through the signed-token endpoint.
    """

    file = models.FileField(
        storage=PrivateMediaStorage(),
        upload_to="private/%Y/%m/",
        max_length=500,
        help_text="Privately stored file; never exposed via a public URL.",
    )
    original_filename = models.CharField(max_length=255, blank=True, default="")
    content_type = models.CharField(max_length=127, blank=True, default="")
    size_bytes = models.PositiveBigIntegerField(default=0)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )

    class Meta:
        abstract = True
