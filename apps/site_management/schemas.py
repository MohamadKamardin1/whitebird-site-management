"""Pydantic schemas for the site management API."""

from __future__ import annotations

from datetime import datetime

from ninja import Field, ModelSchema, Schema

from .models import (
    Asset,
    AssetCategory,
    Department,
    SiteStatus,
    SiteType,
)


class StatusRef(Schema):
    slug: str
    name: str
    color: str = ""


class SiteSummaryOut(Schema):
    id: int
    name: str
    slug: str
    code: str
    site_type: str | None = None
    status: StatusRef | None = None
    city: str = ""
    region: str = ""
    country: str = "TZ"
    capacity: int = 0
    department_count: int = 0
    asset_count: int = 0
    staff_count: int = 0


class SiteDetailOut(SiteSummaryOut):
    description: str = ""
    address: str = ""
    postal_code: str = ""
    latitude: float | None = None
    longitude: float | None = None
    contact_email: str = ""
    contact_phone: str = ""
    created_at: datetime
    updated_at: datetime


class SiteCreateIn(Schema):
    name: str = Field(min_length=1, max_length=160)
    site_type_id: int | None = None
    status_id: int | None = None
    description: str = ""
    address: str = ""
    city: str = ""
    region: str = ""
    country: str = "TZ"
    postal_code: str = ""
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    capacity: int = Field(default=0, ge=0)
    contact_email: str = ""
    contact_phone: str = ""


class SiteUpdateIn(Schema):
    name: str | None = Field(default=None, max_length=160)
    site_type_id: int | None = None
    status_id: int | None = None
    description: str | None = None
    address: str | None = None
    city: str | None = None
    region: str | None = None
    country: str | None = None
    postal_code: str | None = None
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    capacity: int | None = Field(default=None, ge=0)
    contact_email: str | None = None
    contact_phone: str | None = None


class DepartmentOut(ModelSchema):
    class Meta:
        model = Department
        fields = [
            "id",
            "site",
            "name",
            "description",
            "manager",
            "is_active",
            "created_at",
            "updated_at",
        ]


class DepartmentCreateIn(Schema):
    name: str = Field(min_length=1, max_length=160)
    description: str = ""


class DepartmentUpdateIn(Schema):
    name: str | None = Field(default=None, max_length=160)
    description: str | None = None


class AssetOut(ModelSchema):
    class Meta:
        model = Asset
        fields = [
            "id",
            "site",
            "category",
            "name",
            "serial_number",
            "quantity",
            "condition",
            "is_active",
            "created_at",
            "updated_at",
        ]


class AssetCreateIn(Schema):
    name: str = Field(min_length=1, max_length=160)
    category_id: int | None = None
    serial_number: str = ""
    quantity: int = Field(default=1, ge=1)
    condition: Asset.Condition = Asset.Condition.OPERATIONAL


class AssetUpdateIn(Schema):
    name: str | None = Field(default=None, max_length=160)
    category_id: int | None = None
    serial_number: str | None = None
    quantity: int | None = Field(default=None, ge=1)
    condition: Asset.Condition | None = None


class AssignmentOut(Schema):
    id: int
    site_id: int
    user_id: int
    email: str
    role: str
    is_primary: bool
    created_at: datetime


class AssignmentCreateIn(Schema):
    user_id: int
    role: str = Field(default="staff", pattern="^(site_manager|staff)$")
    is_primary: bool = False


class NotificationOut(Schema):
    id: int
    title: str
    body: str
    entity_type: str
    entity_id: str
    is_read: bool
    created_at: datetime


class SiteStatsOut(Schema):
    site_id: int
    name: str
    status: str | None = None
    departments: int = 0
    assets: int = 0
    staff: int = 0
    capacity: int = 0
    occupancy_ratio: float = 0.0


class SiteTypeOut(ModelSchema):
    class Meta:
        model = SiteType
        fields = ["id", "name", "slug", "description", "is_active"]


class SiteStatusOut(ModelSchema):
    class Meta:
        model = SiteStatus
        fields = ["id", "name", "slug", "description", "is_active", "order", "color"]


class AssetCategoryOut(ModelSchema):
    class Meta:
        model = AssetCategory
        fields = ["id", "name", "slug", "description", "is_active"]


class MessageOut(Schema):
    detail: str
