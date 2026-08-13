"""Token foundation for the API.

The API uses a hybrid, secure scheme without external JWT dependencies:

* **Access tokens** are short-lived, stateless, signed payloads
  (``django.core.signing`` — HMAC with the project secret). They verify
  signature + expiry without a database lookup.
* **Refresh tokens** are server-side ``ApiToken`` rows: revocable, expiring,
  and tracked with ``last_used_at``.

If a JWT library is adopted later, only :func:`create_access_token` and
:func:`decode_access_token` change; the router and auth contract stay put.
"""

from __future__ import annotations

from django.conf import settings
from django.core import signing

ACCESS_TOKEN_SALT = "whitebird.access-token"
_ACCESS_TOKEN_MAX_AGE = 60 * 60 * 24 * 7  # hard ceiling; settings tighten it


def access_token_lifetime_seconds() -> int:
    return int(getattr(settings, "ACCESS_TOKEN_TTL_SECONDS", 1800))


def create_access_token(user_id: int) -> str:
    """Sign a short-lived access token for the given user id."""
    payload = {"uid": user_id}
    return signing.dumps(
        payload,
        salt=ACCESS_TOKEN_SALT,
        compress=True,
    )


def decode_access_token(token: str) -> int | None:
    """Return the user id encoded in an access token, or ``None`` if invalid.

    Verifies the signature and the token's age (must be within the configured
    TTL, capped at a hard ceiling of seven days).
    """
    max_age = min(access_token_lifetime_seconds(), _ACCESS_TOKEN_MAX_AGE)
    try:
        payload = signing.loads(token, salt=ACCESS_TOKEN_SALT, max_age=max_age)
    except (signing.BadSignature, signing.SignatureExpired, ValueError, TypeError):
        return None
    user_id = payload.get("uid")
    return int(user_id) if isinstance(user_id, int) else None
