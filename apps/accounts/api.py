"""Accounts API router — authentication, token lifecycle, and staff admin."""

from __future__ import annotations

from django.contrib.auth import authenticate
from django.core.exceptions import PermissionDenied, ValidationError
from ninja import Router

from apps.accounts.auth import TokenAuth
from apps.accounts.models import ApiToken, RoleCode, User
from apps.accounts.permissions import role_required
from apps.accounts.schemas import (
    LoginIn,
    LoginOut,
    LogoutIn,
    MessageOut,
    PasswordChangeIn,
    RefreshIn,
    RefreshOut,
    StaffCreateIn,
    StaffMemberOut,
    TokenCreateIn,
    TokenOut,
    UserOut,
)
from apps.accounts.selectors import list_active_tokens, staff_directory, user_permissions, user_stats
from apps.accounts.services import (
    create_user,
    issue_api_token,
    login_and_issue_tokens,
    refresh_access_token,
    revoke_api_token,
    set_password,
)
from apps.accounts.tokens import access_token_lifetime_seconds
from apps.core.models import AuditLog
from apps.core.services import record_audit
from apps.core.requests import AuthenticatedRequest

router = Router(auth=TokenAuth())


@router.post(
    "/login",
    auth=None,
    response=LoginOut,
    summary="Exchange email and password for access + refresh tokens",
)
def login(request: AuthenticatedRequest, payload: LoginIn) -> LoginOut:
    try:
        user, access_token, refresh_token = login_and_issue_tokens(
            request=request,
            email=payload.email,
            password=payload.password,
            token_name=payload.token_name,
        )
    except ValidationError as exc:
        raise PermissionDenied(str(exc.messages[0])) from None
    return LoginOut(
        access_token=access_token,
        refresh_token=refresh_token.key,
        expires_in=access_token_lifetime_seconds(),
        user=UserOut.from_orm(user),
    )


@router.post(
    "/logout",
    auth=None,
    response=MessageOut,
    summary="Revoke a refresh token",
)
def logout(request: AuthenticatedRequest, payload: LogoutIn) -> MessageOut:
    ApiToken.objects.filter(key=payload.refresh_token).update(is_active=False)
    return MessageOut(detail="Logged out.")


@router.post(
    "/refresh",
    auth=None,
    response=RefreshOut,
    summary="Exchange a refresh token for a fresh access token",
)
def refresh(request: AuthenticatedRequest, payload: RefreshIn) -> RefreshOut:
    try:
        access_token = refresh_access_token(refresh_token_key=payload.refresh_token)
    except ValidationError as exc:
        raise PermissionDenied(str(exc.messages[0])) from None
    return RefreshOut(access_token=access_token, expires_in=access_token_lifetime_seconds())


@router.get("/me", response=UserOut, summary="Current authenticated user")
def me(request: AuthenticatedRequest) -> User:
    return request.auth


@router.get("/me/permissions", response=dict, summary="Permission set for the current user")
def my_permissions(request: AuthenticatedRequest) -> dict[str, object]:
    return user_permissions(request.auth)


@router.get("/me/stats", response=dict, summary="Authenticated user dashboard aggregates")
def my_stats(request: AuthenticatedRequest) -> dict[str, object]:
    return user_stats(request.auth)


@router.post("/password-change", response=MessageOut, summary="Change the current user's password")
def password_change(request: AuthenticatedRequest, payload: PasswordChangeIn) -> MessageOut:
    if not authenticate(
        request=request,
        username=request.auth.email,
        password=payload.current_password,
    ):
        raise PermissionDenied("Current password is incorrect.")
    try:
        set_password(user=request.auth, new_password=payload.new_password, actor=request.auth)
    except ValidationError as exc:
        raise PermissionDenied(str(exc.messages[0])) from None
    return MessageOut(detail="Password changed.")


@router.get("/tokens", response=list[TokenOut], summary="List your API tokens")
def list_tokens(request: AuthenticatedRequest) -> list[ApiToken]:
    return list(list_active_tokens(request.auth))


@router.post("/tokens", response=TokenOut, summary="Issue a new API token")
def create_token(request: AuthenticatedRequest, payload: TokenCreateIn) -> ApiToken:
    return issue_api_token(
        user=request.auth,
        name=payload.name,
        expires_at=payload.expires_at,
        actor=request.auth,
    )


@router.post("/tokens/{token_id}/revoke", response=MessageOut, summary="Revoke an API token")
def revoke_token(request: AuthenticatedRequest, token_id: int) -> MessageOut:
    token = ApiToken.objects.filter(pk=token_id, user=request.auth).first()
    if token is None:
        raise PermissionDenied("Token not found.")
    revoke_api_token(token=token, actor=request.auth)
    return MessageOut(detail="Token revoked.")


@router.get(
    "/users",
    response=list[StaffMemberOut],
    summary="User directory (disable-only administration alias)",
)
@router.get(
    "/staff",
    response=list[StaffMemberOut],
    summary="Staff directory (system admins and supervisors)",
)
def staff_list(request: AuthenticatedRequest) -> list[StaffMemberOut]:
    if not role_required(
        RoleCode.SYSTEM_ADMIN,
        RoleCode.GENERAL_SUPERVISOR,
        RoleCode.ASSISTANT_GENERAL_SUPERVISOR,
        RoleCode.ZONE_SUPERVISOR,
    )(request.auth):
        raise PermissionDenied("Staff directory requires a management role.")
    return [
        StaffMemberOut(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            role=RoleCode(user.role),
            assignment_count=user.assignment_count,  # type: ignore[attr-defined]
            is_active=user.is_active,
        )
        for user in staff_directory()
    ]


@router.post(
    "/staff",
    response=UserOut,
    summary="Create a platform user (system admin only)",
)
def staff_create(request: AuthenticatedRequest, payload: StaffCreateIn) -> User:
    if not request.auth.is_system_admin:
        raise PermissionDenied("System admin role required.")
    return create_user(
        email=payload.email,
        password=payload.password,
        role=payload.role,
        first_name=payload.first_name,
        last_name=payload.last_name,
        phone=payload.phone,
        timezone=payload.timezone,
        actor=request.auth,
    )


@router.post(
    "/users/{user_id}/disable",
    response=UserOut,
    summary="Disable a user without deleting historical records",
)
def user_disable(request: AuthenticatedRequest, user_id: int) -> User:
    if not request.auth.is_system_admin:
        raise PermissionDenied("System admin role required.")
    target = User.objects.filter(pk=user_id).first()
    if target is None:
        raise ValidationError("User not found.")
    if target.pk == request.auth.pk:
        raise ValidationError("The current administrator cannot disable their own account.")
    if target.is_active:
        target.is_active = False
        target.save(update_fields=["is_active", "updated_at"])
        record_audit(
            action=AuditLog.Action.STATUS_CHANGE,
            actor=request.auth,
            entity=target,
            summary=f"Disabled user {target.email} without deleting historical records.",
            after_data={"is_active": False, "role": target.role},
        )
    return target
