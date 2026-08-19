"""Authenticated WebSocket delivery for persisted conversation events."""

from __future__ import annotations

import logging
from urllib.parse import parse_qs

from asgiref.sync import async_to_sync, sync_to_async
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.layers import get_channel_layer
from channels.middleware import BaseMiddleware
from django.contrib.auth.models import AnonymousUser

from apps.accounts.models import User
from apps.accounts.tokens import decode_access_token

from .models import ConversationMembership

logger = logging.getLogger(__name__)


def conversation_group_name(conversation_id: int) -> str:
    return f"conversation_{conversation_id}"


class AccessTokenAuthMiddleware(BaseMiddleware):
    """Authenticate a browser WebSocket using the same signed access token as REST.

    Browser WebSocket clients cannot send arbitrary Authorization headers. The
    short-lived signed token is therefore supplied in the connection query and
    is decoded before the socket is accepted; no caller-controlled user id is
    ever trusted.
    """

    async def __call__(self, scope, receive, send):  # type: ignore[no-untyped-def]
        query = parse_qs(scope.get("query_string", b"").decode("utf-8"))
        token = query.get("token", [""])[0]
        user_id = decode_access_token(token)
        user = await self._active_user(user_id) if user_id else None
        scope["user"] = user or AnonymousUser()
        return await super().__call__(scope, receive, send)

    @database_sync_to_async
    def _active_user(self, user_id: int) -> User | None:
        return User.objects.filter(pk=user_id, is_active=True).first()


class ConversationConsumer(AsyncJsonWebsocketConsumer):
    """Subscribe an active conversation member to metadata-only message events."""

    conversation_id: int
    group_name: str

    async def connect(self) -> None:
        self.conversation_id = int(self.scope["url_route"]["kwargs"]["conversation_id"])
        user = self.scope.get("user")
        if not getattr(user, "is_authenticated", False) or not await self._is_active_member(user.pk):
            await self.close(code=4403)
            return
        self.group_name = conversation_group_name(self.conversation_id)
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        await self.send_json({"event": "connection.ready", "conversation_id": self.conversation_id})

    async def disconnect(self, close_code: int) -> None:
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    @database_sync_to_async
    def _is_active_member(self, user_id: int) -> bool:
        return ConversationMembership.objects.filter(
            conversation_id=self.conversation_id, user_id=user_id, is_active=True
        ).exists()

    async def conversation_event(self, event: dict[str, object]) -> None:
        await self.send_json(
            {
                "event": event["event"],
                "conversation_id": event["conversation_id"],
                "message_id": event["message_id"],
                "actor_id": event["actor_id"],
            }
        )


def publish_conversation_event(*, conversation_id: int, event: str, message_id: int, actor_id: int) -> None:
    """Publish a minimal event after commit; REST remains the content source."""

    channel_layer = get_channel_layer()
    if channel_layer is None:
        return
    try:
        async_to_sync(channel_layer.group_send)(
            conversation_group_name(conversation_id),
            {
                "type": "conversation.event",
                "event": event,
                "conversation_id": conversation_id,
                "message_id": message_id,
                "actor_id": actor_id,
            },
        )
    except Exception:  # pragma: no cover - network transport resilience
        logger.exception("Unable to publish conversation realtime event", extra={"conversation_id": conversation_id})
