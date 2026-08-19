"""WebSocket routes for the site-management application."""

from django.urls import path

from .realtime import ConversationConsumer

websocket_urlpatterns = [
    path("ws/site-management/v1/conversations/<int:conversation_id>/", ConversationConsumer.as_asgi()),
]
