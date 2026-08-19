"""Audited role-scoped conversation services.

The service layer deliberately owns the communication policy. API callers and
WebSocket consumers never receive a way to bypass the same membership and
organisation-scope checks used for persisted messaging actions.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from django.db import IntegrityError, transaction
from django.db.models import Q, QuerySet
from django.utils import timezone

from apps.accounts.models import RoleCode, User
from apps.core.errors import BusinessRuleError, ForbiddenActionError, NotFoundError
from apps.core.files import max_upload_bytes
from apps.core.models import AuditLog
from apps.core.services import record_audit

from .models import (
    Conversation,
    ConversationMembership,
    ConversationMessage,
    ConversationMessageAttachment,
    ConversationType,
    MessageAttachmentType,
    SiteSupervisorAssignment,
    ZoneSupervisorAssignment,
)
from .scoping import assigned_zone_ids

if TYPE_CHECKING:
    from ninja.files import UploadedFile


_ALWAYS_CONTACT_ROLES = frozenset(
    {RoleCode.SYSTEM_ADMIN, RoleCode.GENERAL_SUPERVISOR, RoleCode.ASSISTANT_GENERAL_SUPERVISOR}
)
_FILE_TYPES: dict[str, set[str]] = {
    MessageAttachmentType.DOCUMENT: {"doc", "docx", "xls", "xlsx", "csv", "txt"},
    MessageAttachmentType.PDF: {"pdf"},
    MessageAttachmentType.IMAGE: {"jpg", "jpeg", "png", "webp"},
    MessageAttachmentType.VOICE: {"mp3", "wav", "m4a", "ogg", "webm"},
}


def _active_member(conversation: Conversation, user: User) -> ConversationMembership:
    membership = ConversationMembership.objects.filter(conversation=conversation, user=user, is_active=True).first()
    if membership is None:
        raise ForbiddenActionError("You are not an active member of this conversation.")
    return membership


def get_conversation_or_404(*, conversation_id: int, user: User) -> Conversation:
    conversation = Conversation.objects.filter(pk=conversation_id, is_active=True).first()
    if conversation is None:
        raise NotFoundError("Conversation not found.")
    _active_member(conversation, user)
    return conversation


def can_start_conversation(*, actor: User, recipient: User) -> bool:
    """Return whether ``actor`` can initiate a direct thread with ``recipient``.

    System administrators and General/Assistant General Supervisors can start
    conversations with any active account. Zone Supervisors can initiate only
    with site supervisors in their actively assigned zones. Site Supervisors
    may initiate upward with a zone supervisor responsible for their assigned
    site. All other roles can reply to threads they already belong to but cannot
    create unrestricted new channels.
    """

    if actor.pk == recipient.pk or not actor.is_active or not recipient.is_active:
        return False
    if actor.is_system_admin or actor.role in _ALWAYS_CONTACT_ROLES:
        return True

    if actor.role == RoleCode.ZONE_SUPERVISOR and recipient.role == RoleCode.SITE_SUPERVISOR:
        return SiteSupervisorAssignment.objects.filter(
            user=recipient,
            is_active=True,
            site__zone_id__in=assigned_zone_ids(actor),
        ).exists()

    if actor.role == RoleCode.SITE_SUPERVISOR and recipient.role == RoleCode.ZONE_SUPERVISOR:
        recipient_zone_ids = set(
            ZoneSupervisorAssignment.objects.filter(user=recipient, is_active=True).values_list("zone_id", flat=True)
        )
        return SiteSupervisorAssignment.objects.filter(
            user=actor, is_active=True, site__zone_id__in=recipient_zone_ids
        ).exists()
    return False


def contactable_users(*, actor: User) -> QuerySet[User]:
    """Return a safe role-scoped directory for the new-message contact picker."""

    base = User.objects.filter(is_active=True).exclude(pk=actor.pk).order_by("first_name", "last_name", "email")
    if actor.is_system_admin or actor.role in _ALWAYS_CONTACT_ROLES:
        return base
    if actor.role == RoleCode.ZONE_SUPERVISOR:
        return base.filter(
            role=RoleCode.SITE_SUPERVISOR,
            site_supervisor_assignments__is_active=True,
            site_supervisor_assignments__site__zone_id__in=assigned_zone_ids(actor),
        ).distinct()
    if actor.role == RoleCode.SITE_SUPERVISOR:
        zone_ids = SiteSupervisorAssignment.objects.filter(user=actor, is_active=True).values_list("site__zone_id", flat=True)
        return base.filter(
            role=RoleCode.ZONE_SUPERVISOR,
            zone_supervisor_assignments__is_active=True,
            zone_supervisor_assignments__zone_id__in=zone_ids,
        ).distinct()
    return base.none()


def get_or_create_direct_conversation(*, user_a: User, user_b: User, actor: User) -> Conversation:
    """Create or retrieve a deterministic direct conversation after policy checks."""

    if actor.pk != user_a.pk:
        raise ForbiddenActionError("Only the initiating user can create this conversation.")
    if not can_start_conversation(actor=actor, recipient=user_b):
        raise ForbiddenActionError("You are not allowed to start a conversation with this user.")

    direct_key = ":".join(str(value) for value in sorted((user_a.pk, user_b.pk)))
    existing = Conversation.objects.filter(conversation_type=ConversationType.DIRECT, direct_key=direct_key).first()
    if existing is not None:
        return existing

    try:
        with transaction.atomic():
            conversation = Conversation.objects.create(
                conversation_type=ConversationType.DIRECT,
                direct_key=direct_key,
                created_by=actor,
                updated_by=actor,
            )
            for member in (user_a, user_b):
                ConversationMembership.objects.create(
                    conversation=conversation,
                    user=member,
                    created_by=actor,
                    updated_by=actor,
                )
            record_audit(
                action=AuditLog.Action.CREATE,
                user=actor,
                entity=conversation,
                after_data={"conversation_type": ConversationType.DIRECT, "member_ids": [user_a.pk, user_b.pk]},
                summary="Created a direct conversation.",
            )
            return conversation
    except IntegrityError:
        return Conversation.objects.get(conversation_type=ConversationType.DIRECT, direct_key=direct_key)


def create_group_conversation(*, title: str, member_ids: list[int], actor: User) -> Conversation:
    """Create a group with an auditable initial membership set."""

    cleaned_title = title.strip()
    if not cleaned_title:
        raise BusinessRuleError("A group conversation needs a title.", fields={"title": "Required."})
    requested_ids = {int(member_id) for member_id in member_ids}
    requested_ids.add(actor.pk)
    if len(requested_ids) < 3:
        raise BusinessRuleError("A group needs at least three members.", fields={"member_ids": "Add at least two contacts."})
    members = list(User.objects.filter(pk__in=requested_ids, is_active=True))
    if len(members) != len(requested_ids):
        raise BusinessRuleError("One or more selected members are inactive or do not exist.")
    denied_ids = [member.pk for member in members if member.pk != actor.pk and not can_start_conversation(actor=actor, recipient=member)]
    if denied_ids:
        raise ForbiddenActionError("You are not allowed to add one or more selected users to this group.")

    with transaction.atomic():
        conversation = Conversation.objects.create(
            conversation_type=ConversationType.GROUP,
            title=cleaned_title,
            created_by=actor,
            updated_by=actor,
        )
        ConversationMembership.objects.bulk_create(
            [
                ConversationMembership(
                    conversation=conversation,
                    user=member,
                    created_by=actor,
                    updated_by=actor,
                )
                for member in members
            ]
        )
        record_audit(
            action=AuditLog.Action.CREATE,
            user=actor,
            entity=conversation,
            after_data={"conversation_type": ConversationType.GROUP, "title": cleaned_title, "member_ids": sorted(requested_ids)},
            summary="Created a group conversation.",
        )
        return conversation


def send_message(*, conversation: Conversation, sender: User, body: str) -> ConversationMessage:
    """Append a message only when the sender is currently a conversation member."""

    _active_member(conversation, sender)
    cleaned_body = body.strip()
    if not cleaned_body:
        raise BusinessRuleError("Write a message or attach a file before sending.", fields={"body": "Required."})
    with transaction.atomic():
        now = timezone.now()
        message = ConversationMessage.objects.create(
            conversation=conversation,
            sender=sender,
            body=cleaned_body,
            delivered_at=now,
            created_by=sender,
            updated_by=sender,
        )
        conversation.last_message_at = now
        conversation.updated_by = sender
        conversation.save(update_fields=["last_message_at", "updated_by", "updated_at"])
        record_audit(
            action=AuditLog.Action.CREATE,
            user=sender,
            entity=message,
            after_data={"conversation_id": conversation.pk, "character_count": len(cleaned_body)},
            summary="Sent a conversation message.",
        )
        return message


def _validate_attachment(*, upload: UploadedFile, attachment_type: str) -> str:
    if attachment_type not in MessageAttachmentType.values:
        raise BusinessRuleError("Unsupported attachment type.", fields={"attachment_type": "Unsupported."})
    filename = upload.name or "attachment"
    extension = Path(filename).suffix.lower().lstrip(".")
    if extension not in _FILE_TYPES[attachment_type]:
        raise BusinessRuleError(
            "The selected file does not match the attachment type.",
            fields={"file": f"Expected one of: {', '.join(sorted(_FILE_TYPES[attachment_type]))}."},
        )
    if upload.size > max_upload_bytes():
        raise BusinessRuleError("The attachment is larger than the configured upload limit.", fields={"file": "File is too large."})
    return filename


def upload_attachment(
    *, message: ConversationMessage, upload: UploadedFile, attachment_type: str, actor: User, duration_seconds: int | None = None
) -> ConversationMessageAttachment:
    """Attach a validated private file to a message the actor is allowed to access."""

    _active_member(message.conversation, actor)
    filename = _validate_attachment(upload=upload, attachment_type=attachment_type)
    if duration_seconds is not None and (attachment_type != MessageAttachmentType.VOICE or duration_seconds < 1):
        raise BusinessRuleError("A duration is only valid for a voice attachment.")
    with transaction.atomic():
        attachment = ConversationMessageAttachment(
            message=message,
            attachment_type=attachment_type,
            original_filename=filename[:255],
            content_type=(upload.content_type or "")[:127],
            size_bytes=upload.size,
            duration_seconds=duration_seconds,
            uploaded_by=actor,
        )
        attachment.file.save(filename, upload, save=False)
        attachment.save()
        now = timezone.now()
        message.conversation.last_message_at = now
        message.conversation.updated_by = actor
        message.conversation.save(update_fields=["last_message_at", "updated_by", "updated_at"])
        record_audit(
            action=AuditLog.Action.CREATE,
            user=actor,
            entity=attachment,
            after_data={"message_id": message.pk, "attachment_type": attachment_type, "size_bytes": upload.size},
            summary="Attached a private file to a conversation message.",
        )
        return attachment


def create_attachment_message(
    *, conversation: Conversation, upload: UploadedFile, attachment_type: str, actor: User, duration_seconds: int | None = None
) -> ConversationMessage:
    """Create an attachment-only message atomically for straightforward clients."""

    _active_member(conversation, actor)
    filename = _validate_attachment(upload=upload, attachment_type=attachment_type)
    if duration_seconds is not None and (attachment_type != MessageAttachmentType.VOICE or duration_seconds < 1):
        raise BusinessRuleError("A duration is only valid for a voice attachment.")
    with transaction.atomic():
        now = timezone.now()
        message = ConversationMessage.objects.create(
            conversation=conversation,
            sender=actor,
            body="",
            delivered_at=now,
            created_by=actor,
            updated_by=actor,
        )
        attachment = ConversationMessageAttachment(
            message=message,
            attachment_type=attachment_type,
            original_filename=filename[:255],
            content_type=(upload.content_type or "")[:127],
            size_bytes=upload.size,
            duration_seconds=duration_seconds,
            uploaded_by=actor,
        )
        attachment.file.save(filename, upload, save=False)
        attachment.save()
        conversation.last_message_at = now
        conversation.updated_by = actor
        conversation.save(update_fields=["last_message_at", "updated_by", "updated_at"])
        record_audit(
            action=AuditLog.Action.CREATE,
            user=actor,
            entity=message,
            after_data={"conversation_id": conversation.pk, "attachment_id": attachment.pk, "attachment_type": attachment_type},
            summary="Sent a conversation attachment.",
        )
        return message


def mark_read(*, conversation: Conversation, user: User) -> ConversationMembership:
    """Persist the reader’s last-read timestamp without changing message history."""

    membership = _active_member(conversation, user)
    membership.last_read_at = timezone.now()
    membership.updated_by = user
    membership.save(update_fields=["last_read_at", "updated_by", "updated_at"])
    record_audit(
        action=AuditLog.Action.STATUS_CHANGE,
        user=user,
        entity=membership,
        after_data={"conversation_id": conversation.pk, "last_read_at": membership.last_read_at.isoformat()},
        summary="Marked a conversation as read.",
    )
    return membership
