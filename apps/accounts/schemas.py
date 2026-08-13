"""Pydantic schemas for the accounts API."""

from __future__ import annotations

from datetime import datetime

from ninja import Field, ModelSchema, Schema

from apps.accounts.models import ApiToken, Role, User


class UserOut(ModelSchema):
    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "first_name",
            "last_name",
            "email",
            "phone",
            "role",
            "is_active",
            "date_joined",
        ]


class StaffMemberOut(Schema):
    id: int
    username: str
    full_name: str
    role: Role
    assignment_count: int


class StaffCreateIn(Schema):
    username: str = Field(min_length=3, max_length=150)
    password: str = Field(min_length=8)
    email: str = ""
    role: Role = Role.STAFF
    first_name: str = ""
    last_name: str = ""
    phone: str = ""


class LoginIn(Schema):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)
    token_name: str = "cli-login"


class LoginOut(Schema):
    token: str
    expires_at: datetime | None
    user: UserOut


class TokenCreateIn(Schema):
    name: str = Field(default="", max_length=64)
    expires_at: datetime | None = None


class TokenOut(ModelSchema):
    class Meta:
        model = ApiToken
        fields = ["id", "name", "key", "is_active", "expires_at", "last_used_at", "created_at"]


class MessageOut(Schema):
    detail: str
