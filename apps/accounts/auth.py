"""HTTP bearer authentication backed by the :class:`ApiToken` model."""

from datetime import timedelta
from typing import Any

from django.utils import timezone
from ninja.security import HttpBearer

from apps.accounts.models import ApiToken, User

_LAST_USED_REFRESH = timedelta(minutes=5)


class ApiTokenAuth(HttpBearer):
    """Resolves ``Authorization: Bearer <token>`` into an authenticated user.

    ``last_used_at`` is refreshed at most once every five minutes to avoid a
    write on every request.
    """

    def authenticate(self, request: Any, token: str) -> User | None:
        if not token:
            return None
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
