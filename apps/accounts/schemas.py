"""Pydantic schemas for the accounts API."""

from __future__ import annotations

from datetime import datetime

from ninja import Field, ModelSchema, Schema

from apps.accounts.models import ApiToken, RoleCode


class UserOut(Schema):
    model_config = {"from_attributes": True}

    id: int
    email: str
    first_name: str
    last_name: str
    full_name: str
    phone: str
    role: RoleCode
    timezone: str
    is_active: bool
    last_login: datetime | None = None
    created_at: datetime


class StaffMemberOut(Schema):
    id: int
    email: str
    full_name: str
    role: RoleCode
    assignment_count: int


class StaffCreateIn(Schema):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=12, max_length=128)
    role: RoleCode = RoleCode.MANAGEMENT_VIEWER
    first_name: str = ""
    last_name: str = ""
    phone: str = ""
    timezone: str = "Africa/Dar_es_Salaam"


class LoginIn(Schema):
    email: str = Field(min_length=1)
    password: str = Field(min_length=1)
    token_name: str = "api-login"


class LoginOut(Schema):
    access_token: str
    refresh_token: str
    expires_in: int
    user: UserOut


class RefreshIn(Schema):
    refresh_token: str = Field(min_length=1)


class RefreshOut(Schema):
    access_token: str
    expires_in: int


class LogoutIn(Schema):
    refresh_token: str = Field(min_length=1)


class PasswordChangeIn(Schema):
    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=12, max_length=128)


class TokenCreateIn(Schema):
    name: str = Field(default="", max_length=64)
    expires_at: datetime | None = None


class TokenOut(ModelSchema):
    class Meta:
        model = ApiToken
        fields = ["id", "name", "key", "is_active", "expires_at", "last_used_at", "created_at"]


class MessageOut(Schema):
    detail: str
