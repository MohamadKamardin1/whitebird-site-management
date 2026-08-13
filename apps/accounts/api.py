"""Accounts API router."""

from __future__ import annotations

from django.core.exceptions import PermissionDenied, ValidationError
from ninja import Router

from apps.accounts.auth import ApiTokenAuth
from apps.accounts.models import ApiToken, Role, User
from apps.accounts.permissions import role_required
from apps.accounts.schemas import (
    LoginIn,
    LoginOut,
    MessageOut,
    StaffCreateIn,
    StaffMemberOut,
    TokenCreateIn,
    TokenOut,
    UserOut,
)
from apps.accounts.selectors import list_active_tokens, staff_directory, user_stats
from apps.accounts.services import (
    create_user,
    issue_api_token,
    login_and_issue_token,
    revoke_api_token,
)
from apps.core.requests import AuthenticatedRequest

router = Router(auth=ApiTokenAuth())


@router.post(
    "/login",
    auth=None,
    response=LoginOut,
    summary="Exchange credentials for a bearer token",
)
def login(request: AuthenticatedRequest, payload: LoginIn) -> LoginOut:
    try:
        token, user = login_and_issue_token(
            request=request,
            username=payload.username,
            password=payload.password,
            name=payload.token_name,
        )
    except ValidationError as exc:
        raise PermissionDenied(str(exc.messages[0])) from None
    return LoginOut(token=token.key, expires_at=token.expires_at, user=UserOut.from_orm(user))


@router.get("/me", response=UserOut, summary="Current authenticated user")
def me(request: AuthenticatedRequest) -> User:
    return request.auth


@router.get("/me/stats", response=dict, summary="Authenticated user dashboard aggregates")
def my_stats(request: AuthenticatedRequest) -> dict[str, object]:
    return user_stats(request.auth)


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
    "/staff",
    response=list[StaffMemberOut],
    summary="Staff directory (admin & managers)",
)
def staff_list(request: AuthenticatedRequest) -> list[StaffMemberOut]:
    if not role_required(Role.ADMIN, Role.MANAGER)(request.auth):
        raise PermissionDenied("Staff directory requires admin or manager role.")
    return [
        StaffMemberOut(
            id=user.id,
            username=user.username,
            full_name=user.get_full_name() or user.username,
            role=Role(user.role),
            assignment_count=user.assignment_count,  # type: ignore[attr-defined]
        )
        for user in staff_directory()
    ]


@router.post(
    "/staff",
    response=UserOut,
    summary="Create a platform user (admin only)",
)
def staff_create(request: AuthenticatedRequest, payload: StaffCreateIn) -> User:
    if not request.auth.is_admin:
        raise PermissionDenied("Admin role required.")
    return create_user(
        username=payload.username,
        password=payload.password,
        email=payload.email,
        role=payload.role,
        first_name=payload.first_name,
        last_name=payload.last_name,
        phone=payload.phone,
        actor=request.auth,
    )
