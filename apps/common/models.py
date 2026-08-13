"""Core shared models: timestamping and the audit log."""

from django.conf import settings
from django.db import models


class TimeStampedModel(models.Model):
    """Abstract base providing immutable created/updated timestamps."""

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class AuditLog(models.Model):
    """Append-only trail of who changed what, when.

    ``entity_type``/``entity_id`` form a lightweight, contenttype-free
    reference to any domain object. ``changes`` stores the before/after delta.
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

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
        help_text="User who performed the action; null for system actors.",
    )
    action = models.CharField(max_length=32, choices=Action.choices, db_index=True)
    entity_type = models.CharField(max_length=64, db_index=True)
    entity_id = models.CharField(max_length=36, db_index=True)
    summary = models.CharField(max_length=255, blank=True, default="")
    changes = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "Audit log"
        verbose_name_plural = "Audit logs"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["entity_type", "entity_id"])]

    def __str__(self) -> str:
        return f"{self.action} {self.entity_type}:{self.entity_id} by {self.actor_id}"
