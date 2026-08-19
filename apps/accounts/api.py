"""Accounts API router — authentication, token lifecycle, and staff admin."""

from __future__ import annotations

from django.contrib.auth import authenticate
from django.core.exceptions import PermissionDenied, ValidationError
from ninja import Router

from apps.accounts.auth import TokenAuth
from apps.accounts.models import ApiToken, RoleCode, User
from apps.accounts.permissions import role_required
from apps.accounts.schemas import (
    AdminPasswordResetIn,
    AdminUserUpdateIn,
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
    UserAuditOut,
    UserDeletionOut,
)
from apps.accounts.selectors import list_active_tokens, staff_directory, user_permissions, user_stats
from apps.accounts.services import (
    create_user,
    deactivate_user,
    activate_user,
    issue_api_token,
    login_and_issue_tokens,
    refresh_access_token,
    revoke_api_token,
    permanently_delete_user,
    set_password,
    update_user,
)
from apps.accounts.tokens import access_token_lifetime_seconds
from apps.core.models import AuditLog
from apps.core.requests import AuthenticatedRequest
from apps.core.services import record_audit

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
            phone=user.phone,
            timezone=user.timezone,
            created_at=user.created_at,
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
    return deactivate_user(user=target, actor=request.auth)


def _admin_target_or_404(*, actor: User, user_id: int) -> User:
    if not actor.is_system_admin:
        raise PermissionDenied("System admin role required.")
    target = User.objects.filter(pk=user_id).first()
    if target is None:
        raise ValidationError("User not found.")
    return target


def _protect_last_active_administrator(*, target: User, requested_active: bool | None, requested_role: RoleCode | None) -> None:
    is_leaving_admin = target.is_system_admin and (requested_active is False or (requested_role and requested_role != RoleCode.SYSTEM_ADMIN))
    if is_leaving_admin and User.objects.filter(role=RoleCode.SYSTEM_ADMIN, is_active=True).exclude(pk=target.pk).count() == 0:
        raise ValidationError("At least one active System Administrator account must remain.")


@router.post("/users/{user_id}/activate", response=UserOut, summary="Activate a user account")
def user_activate(request: AuthenticatedRequest, user_id: int) -> User:
    target = _admin_target_or_404(actor=request.auth, user_id=user_id)
    return activate_user(user=target, actor=request.auth)


@router.patch("/users/{user_id}", response=UserOut, summary="Update a user profile, role, or active state")
def user_update(request: AuthenticatedRequest, user_id: int, payload: AdminUserUpdateIn) -> User:
    target = _admin_target_or_404(actor=request.auth, user_id=user_id)
    _protect_last_active_administrator(target=target, requested_active=payload.is_active, requested_role=payload.role)
    if target.pk == request.auth.pk and payload.is_active is False:
        raise ValidationError("The current administrator cannot deactivate their own account.")
    return update_user(
        user=target,
        actor=request.auth,
        first_name=payload.first_name,
        last_name=payload.last_name,
        phone=payload.phone,
        timezone=payload.timezone,
        role=payload.role,
        is_active=payload.is_active,
    )


@router.post("/users/{user_id}/password-reset", response=MessageOut, summary="Set a new password for a user")
def user_password_reset(request: AuthenticatedRequest, user_id: int, payload: AdminPasswordResetIn) -> MessageOut:
    target = _admin_target_or_404(actor=request.auth, user_id=user_id)
    set_password(user=target, new_password=payload.new_password, actor=request.auth)
    ApiToken.objects.filter(user=target, is_active=True).update(is_active=False)
    record_audit(
        action=AuditLog.Action.TOKEN_REVOKE,
        actor=request.auth,
        entity=target,
        summary="Revoked active tokens after administrator password reset",
    )
    return MessageOut(detail="Password updated and active sessions revoked.")


@router.delete("/users/{user_id}", response=UserDeletionOut, summary="Delete a user only when no historical evidence requires retention")
def user_delete(request: AuthenticatedRequest, user_id: int) -> UserDeletionOut:
    target = _admin_target_or_404(actor=request.auth, user_id=user_id)
    if target.pk == request.auth.pk:
        raise ValidationError("The current administrator cannot delete their own account.")
    _protect_last_active_administrator(target=target, requested_active=False, requested_role=None)
    target_id = target.pk
    deleted = permanently_delete_user(user=target, actor=request.auth)
    return UserDeletionOut(
        user_id=target_id,
        deleted=deleted,
        retained=not deleted,
        detail="User deleted." if deleted else "User retained for audit integrity and deactivated instead.",
    )


@router.get("/users/{user_id}/audit", response=list[UserAuditOut], summary="Read the audit history for one user")
def user_audit(request: AuthenticatedRequest, user_id: int) -> list[UserAuditOut]:
    target = _admin_target_or_404(actor=request.auth, user_id=user_id)
    return [
        UserAuditOut(
            id=entry.pk,
            action=entry.action,
            summary=entry.summary,
            actor_name=entry.user.full_name if entry.user else "System",
            created_at=entry.created_at,
            before_data=entry.before_data,
            after_data=entry.after_data,
        )
        for entry in AuditLog.objects.filter(model_name__icontains="user", object_id=str(target.pk)).select_related("user")[:200]
    ]
