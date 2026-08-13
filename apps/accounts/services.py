"""Accounts service layer — writes and business rules."""

from __future__ import annotations

from datetime import datetime

from django.contrib.auth import authenticate
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.common.models import AuditLog
from apps.common.services import record_audit

from .models import ApiToken, Role, User


def create_user(
    *,
    username: str,
    password: str,
    email: str = "",
    role: Role = Role.STAFF,
    first_name: str = "",
    last_name: str = "",
    phone: str = "",
    actor: User | None = None,
) -> User:
    """Create a platform user with an unbreakable password."""
    if not password:
        raise ValidationError("Password is required.")
    user = User.objects.create_user(
        username=username,
        password=password,
        email=email,
        first_name=first_name,
        last_name=last_name,
        phone=phone,
        role=role.value,
    )
    record_audit(
        action=AuditLog.Action.CREATE,
        actor=actor,
        entity=user,
        summary=f"Created {role.label} user",
    )
    return user


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
    record_audit(
        action=AuditLog.Action.TOKEN_CREATE,
        actor=actor,
        entity=token,
        summary=f"Issued API token for {user.get_username()}",
    )
    return token


def revoke_api_token(*, token: ApiToken, actor: User | None = None) -> None:
    """Deactivate an API token (soft revocation)."""
    token.is_active = False
    token.save(update_fields=["is_active", "updated_at"])
    record_audit(
        action=AuditLog.Action.TOKEN_REVOKE,
        actor=actor,
        entity=token,
        summary=f"Revoked API token for {token.user.get_username()}",
    )


def login_and_issue_token(*, username: str, password: str, name: str = "") -> tuple[ApiToken, User]:
    """Authenticate credentials and return a (token, user) pair.

    Raises ``django.core.exceptions.ValidationError`` on bad credentials.
    """
    user = authenticate(username=username, password=password)
    if user is None:
        raise ValidationError("Invalid username or password.")
    if not user.is_active:
        raise ValidationError("Account is disabled.")

    token = issue_api_token(user=user, name=name or "login", actor=user)
    record_audit(
        action=AuditLog.Action.LOGIN,
        actor=user,
        entity=user,
        summary="Successful API login",
    )
    return token, user
