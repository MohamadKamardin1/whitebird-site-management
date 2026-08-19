"""API payload builders for role-scoped conversations."""

from __future__ import annotations

from django.db.models import Q

from apps.accounts.models import User
from apps.core.files import create_file_token

from .models import Conversation, ConversationMembership, ConversationMessage, ConversationMessageAttachment, ConversationType


def member_out(membership: ConversationMembership) -> dict[str, object]:
    user = membership.user
    return {
        "id": user.pk,
        "full_name": user.full_name,
        "email": user.email,
        "role": user.role,
        "joined_at": membership.joined_at,
        "is_active": membership.is_active,
        "last_read_at": membership.last_read_at,
    }


def attachment_out(attachment: ConversationMessageAttachment, user: User) -> dict[str, object]:
    token = create_file_token(
        user_id=user.pk,
        app_label="site_management",
        model_name="conversationmessageattachment",
        object_id=attachment.pk,
    )
    return {
        "id": attachment.pk,
        "attachment_type": attachment.attachment_type,
        "original_filename": attachment.original_filename,
        "content_type": attachment.content_type,
        "size_bytes": attachment.size_bytes,
        "download_token": token,
        "download_url": f"/api/site-management/v1/files/signed/{token}/",
        "duration_seconds": attachment.duration_seconds,
        "created_at": attachment.created_at,
    }


def message_out(message: ConversationMessage, user: User) -> dict[str, object]:
    return {
        "id": message.pk,
        "conversation_id": message.conversation_id,
        "sender_id": message.sender_id,
        "sender_name": message.sender.full_name if message.sender_id else "White Bird",
        "body": message.body,
        "attachments": [attachment_out(attachment, user) for attachment in message.attachments.all()],
        "created_at": message.created_at,
        "delivered_at": message.delivered_at,
    }


def conversation_out(conversation: Conversation, user: User) -> dict[str, object]:
    membership = conversation.memberships.filter(user=user, is_active=True).first()
    if membership is None:
        raise ValueError("The requested user is not an active conversation member.")
    memberships = list(conversation.memberships.filter(is_active=True).select_related("user"))
    latest = conversation.messages.select_related("sender").prefetch_related("attachments").order_by("-created_at", "-pk").first()
    unread_messages = conversation.messages.exclude(sender=user)
    if membership.last_read_at is not None:
        unread_messages = unread_messages.filter(created_at__gt=membership.last_read_at)
    if conversation.conversation_type == ConversationType.DIRECT:
        other = next((item.user for item in memberships if item.user_id != user.pk), None)
        title = other.full_name if other else "Mazungumzo ya moja kwa moja"
    else:
        title = conversation.title
    if latest is None:
        preview = ""
    elif latest.body:
        preview = latest.body[:120]
    elif latest.attachments.exists():
        preview = "Kiambatisho"
    else:
        preview = ""
    return {
        "id": conversation.pk,
        "conversation_type": conversation.conversation_type,
        "title": title,
        "members": [member_out(item) for item in memberships],
        "last_message_at": conversation.last_message_at,
        "last_message_preview": preview,
        "unread_count": unread_messages.count(),
        "created_at": conversation.created_at,
    }


def contact_out(user: User) -> dict[str, object]:
    return {"id": user.pk, "full_name": user.full_name, "email": user.email, "role": user.role}
