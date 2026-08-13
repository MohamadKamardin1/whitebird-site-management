"""HTTP bearer authentication for the API.

Accepts either a signed access token (stateless) or a server-side ``ApiToken``
key (long-lived machine token). ``last_used_at`` on refresh tokens is updated
at most once every five minutes to avoid a write on every request.
"""

from datetime import timedelta
from typing import Any

from django.utils import timezone
from ninja.security import HttpBearer

from .models import ApiToken, User
from .tokens import decode_access_token

_LAST_USED_REFRESH = timedelta(minutes=5)


class TokenAuth(HttpBearer):
    """Resolves ``Authorization: Bearer <token>`` into an authenticated user."""

    def authenticate(self, request: Any, token: str) -> User | None:
        if not token:
            return None

        # Stateless access token path.
        user_id = decode_access_token(token)
        if user_id is not None:
            return User.objects.filter(pk=user_id, is_active=True).first()

        # Server-side API token path (refresh / machine tokens).
        try:
            api_token = ApiToken.objects.select_related("user").get(key=token)
        except ApiToken.DoesNotExist:
            return None

        if not api_token.usable:
            return None

        user = api_token.user
        if not user.is_active:
            return None

        now = timezone.now()
        last_used = api_token.last_used_at
        if last_used is None or now - last_used > _LAST_USED_REFRESH:
            ApiToken.objects.filter(pk=api_token.pk).update(last_used_at=now)

        return user
