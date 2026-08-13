"""Accounts service layer — writes and business rules.

Every mutation is a service function that: validates, mutates inside a
transaction, writes an audit entry, and (where relevant) syncs RBAC groups.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.core.models import AuditLog
from apps.core.services import record_audit

from .models import ApiToken, RoleCode, User
from .tokens import create_access_token

if TYPE_CHECKING:
    from django.http import HttpRequest


def _audit(
    action: AuditLog.Action,
    actor: User | None,
    user: User,
    summary: str,
    changes: dict[str, object] | None = None,
) -> None:
    record_audit(action=action, actor=actor, entity=user, summary=summary, changes=changes)


def create_user(
    *,
    email: str,
    password: str,
    first_name: str = "",
    last_name: str = "",
    phone: str = "",
    role: RoleCode = RoleCode.MANAGEMENT_VIEWER,
    timezone: str = "Africa/Dar_es_Salaam",
    is_active: bool = True,
    actor: User | None = None,
) -> User:
    """Create a platform user with a validated, unbreakable password."""
    if not password:
        raise ValidationError("Password is required.")
    validate_password(password)
    user = User.objects.create_user(
        email=email,
        password=password,
        first_name=first_name,
        last_name=last_name,
        phone=phone,
        role=role.value,
        timezone=timezone,
        is_active=is_active,
    )
    _audit(AuditLog.Action.CREATE, actor, user, f"Created {user.role_label} user")
    return user


def update_user(
    *,
    user: User,
    actor: User,
    first_name: str | None = None,
    last_name: str | None = None,
    phone: str | None = None,
    timezone: str | None = None,
    role: RoleCode | None = None,
    is_active: bool | None = None,
) -> User:
    """Update editable profile fields and record the change."""
    changes: dict[str, object] = {}
    fields = {
        "first_name": first_name,
        "last_name": last_name,
        "phone": phone,
        "timezone": timezone,
        "role": role.value if isinstance(role, RoleCode) else role,
        "is_active": is_active,
    }
    for field, value in fields.items():
        if value is None:
            continue
        if getattr(user, field) != value:
            changes[field] = {"from": getattr(user, field), "to": value}
            setattr(user, field, value)

    if changes:
        user.save(update_fields=[*changes.keys(), "updated_at"])
        _audit(AuditLog.Action.UPDATE, actor, user, f"Updated user {user.email}", changes=changes)
    return user


def set_password(*, user: User, new_password: str, actor: User) -> None:
    """Validate and set a new password for the user."""
    validate_password(new_password, user=user)
    user.set_password(new_password)
    user.save(update_fields=["password", "updated_at"])
    _audit(AuditLog.Action.UPDATE, actor, user, "Password changed")


def activate_user(*, user: User, actor: User) -> User:
    return update_user(user=user, actor=actor, is_active=True)


def deactivate_user(*, user: User, actor: User) -> User:
    return update_user(user=user, actor=actor, is_active=False)


def login_and_issue_tokens(
    *,
    request: HttpRequest,
    email: str,
    password: str,
    token_name: str = "login",
) -> tuple[User, str, ApiToken]:
    """Authenticate by email and issue an access token plus a refresh token.

    Raises ``django.core.exceptions.ValidationError`` on bad credentials. The
    request is forwarded to ``authenticate`` so django-axes can track failures.
    """
    user = authenticate(request=request, username=email.strip().lower(), password=password)
    if user is None:
        raise ValidationError("Invalid email or password.")
    if not user.is_active:
        raise ValidationError("Account is disabled.")

    refresh_token = issue_api_token(
        user=user,
        name=token_name,
        expires_at=timezone.now() + _refresh_token_lifetime(),
    )
    _audit(AuditLog.Action.LOGIN, user, user, "Successful API login")
    return user, create_access_token(user.pk), refresh_token


def refresh_access_token(*, refresh_token_key: str) -> str:
    """Exchange a valid refresh token for a fresh access token.

    Raises ``ValidationError`` if the token is unknown, revoked, or expired.
    """
    try:
        refresh_token = ApiToken.objects.select_related("user").get(key=refresh_token_key)
    except ApiToken.DoesNotExist:
        raise ValidationError("Invalid refresh token.") from None

    if not refresh_token.usable or not refresh_token.user.is_active:
        raise ValidationError("Refresh token is no longer valid.")

    now = timezone.now()
    last_used = refresh_token.last_used_at
    if last_used is None or now - last_used > _LAST_USED_REFRESH:
        ApiToken.objects.filter(pk=refresh_token.pk).update(last_used_at=now)

    return create_access_token(refresh_token.user_id)


def issue_api_token(
    *,
    user: User,
    name: str = "",
    expires_at: datetime | None = None,
    actor: User | None = None,
) -> ApiToken:
    """Create an API token; returns it with the plaintext key available."""
    if expires_at is not None and expires_at <= timezone.now():
        raise ValidationError("expires_at must be in the future.")
    token = ApiToken.objects.create(user=user, name=name, expires_at=expires_at)
    _audit(
        AuditLog.Action.TOKEN_CREATE,
        actor,
        user,
        f"Issued API token for {user.email}",
    )
    return token


def revoke_api_token(*, token: ApiToken, actor: User | None = None) -> None:
    """Deactivate an API token (soft revocation)."""
    token.is_active = False
    token.save(update_fields=["is_active", "updated_at"])
    _audit(
        AuditLog.Action.TOKEN_REVOKE,
        actor,
        token.user,
        f"Revoked API token for {token.user.email}",
    )


def _refresh_token_lifetime() -> timedelta:
    ttl = int(getattr(settings, "REFRESH_TOKEN_TTL_SECONDS", 60 * 60 * 24 * 7))
    return timedelta(seconds=ttl)


_LAST_USED_REFRESH = timedelta(minutes=5)
