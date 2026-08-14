"""Pydantic schemas for the site management API."""

from __future__ import annotations

from datetime import date, datetime, time

from ninja import Field, ModelSchema, Schema

from .models import (
    Asset,
    AssetCategory,
    Department,
    SiteStatus,
    SiteType,
    WorkMode,
)


class StatusRef(Schema):
    slug: str
    name: str
    color: str = ""


class ZoneOut(Schema):
    id: int
    name: str
    code: str
    description: str = ""
    is_active: bool = True
    site_count: int = 0
    created_at: datetime


class SiteSummaryOut(Schema):
    id: int
    name: str
    slug: str
    code: str
    zone_id: int | None = None
    zone_name: str | None = None
    site_type: str | None = None
    status: StatusRef | None = None
    work_mode: WorkMode = WorkMode.FULL_TIME
    building_name: str = ""
    location: str = ""
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
    contact_person: str = ""
    contact_email: str = ""
    contact_phone: str = ""
    working_days: list[str] = Field(default_factory=list)
    start_date: date | None = None
    notes: str = ""
    created_at: datetime
    updated_at: datetime


class SiteSupervisorOut(Schema):
    id: int
    user_id: int
    email: str
    full_name: str
    assigned_from: date
    assigned_to: date | None = None
    is_primary: bool = False
    is_active: bool = True


class SiteCreateIn(Schema):
    name: str = Field(min_length=1, max_length=160)
    zone_id: int | None = None
    site_type_id: int | None = None
    status_id: int | None = None
    description: str = ""
    building_name: str = ""
    location: str = ""
    address: str = ""
    city: str = ""
    region: str = ""
    country: str = "TZ"
    postal_code: str = ""
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    capacity: int = Field(default=0, ge=0)
    contact_person: str = ""
    contact_email: str = ""
    contact_phone: str = ""
    work_mode: WorkMode = WorkMode.FULL_TIME
    working_days: list[str] = Field(default_factory=list)
    notes: str = ""


class SiteUpdateIn(Schema):
    name: str | None = Field(default=None, max_length=160)
    zone_id: int | None = None
    site_type_id: int | None = None
    status_id: int | None = None
    description: str | None = None
    building_name: str | None = None
    location: str | None = None
    address: str | None = None
    city: str | None = None
    region: str | None = None
    country: str | None = None
    postal_code: str | None = None
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    capacity: int | None = Field(default=None, ge=0)
    contact_person: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    work_mode: WorkMode | None = None
    working_days: list[str] | None = Field(default=None, min_length=1)
    notes: str | None = None


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


class SiteShiftOut(Schema):
    id: int
    site_id: int
    shift_name: str
    shift_code: str
    start_time: time
    end_time: time
    effective_days: list[str]
    sequence: int
    description: str
    is_active: bool
    crosses_midnight: bool
    created_at: datetime
    updated_at: datetime


class SiteShiftCreateIn(Schema):
    shift_name: str = Field(min_length=1, max_length=160)
    shift_code: str = ""
    start_time: time
    end_time: time
    effective_days: list[str] = Field(min_length=1)
    sequence: int = Field(default=0, ge=0)
    description: str = ""


class SiteShiftUpdateIn(Schema):
    shift_name: str | None = Field(default=None, max_length=160)
    shift_code: str | None = None
    start_time: time | None = None
    end_time: time | None = None
    effective_days: list[str] | None = Field(default=None, min_length=1)
    sequence: int | None = Field(default=None, ge=0)
    description: str | None = None


class StatusUpdateIn(Schema):
    is_active: bool


class SiteAreaOut(Schema):
    id: int
    site_id: int
    area_name: str
    area_code: str
    floor: str
    description: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class SiteAreaCreateIn(Schema):
    area_name: str = Field(min_length=1, max_length=160)
    area_code: str = ""
    floor: str = ""
    description: str = ""


class SiteAreaUpdateIn(Schema):
    area_name: str | None = Field(default=None, max_length=160)
    area_code: str | None = None
    floor: str | None = None
    description: str | None = None


class OperationalRoleOut(Schema):
    id: int
    name: str
    code: str
    description: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class OperationalRoleCreateIn(Schema):
    name: str = Field(min_length=1, max_length=120)
    code: str = Field(min_length=1, max_length=24)
    description: str = ""


class OperationalRoleUpdateIn(Schema):
    name: str | None = Field(default=None, max_length=120)
    code: str | None = Field(default=None, max_length=24)
    description: str | None = None


class SiteWorkingRuleOut(Schema):
    site_id: int
    allowed_assignment_types: list[str]
    attendance_locked: bool
    require_shift_area_assignment: bool
    allow_temporary_transfers: bool


class CleanerOut(Schema):
    id: int
    first_name: str
    last_name: str
    full_name: str
    id_type: str
    id_number: str
    gender: str
    birth_date: date
    living_location: str
    phone_number: str
    near_person_name: str
    near_person_relationship: str
    near_person_phone: str
    status: str
    registration_date: date
    has_verified_id: bool
    notes: str
    created_at: datetime
    updated_at: datetime


class CleanerCreateIn(Schema):
    first_name: str = Field(min_length=1, max_length=150)
    last_name: str = Field(min_length=1, max_length=150)
    id_type: str = Field(pattern="^(birth_certificate|nida|zanzibar_id)$")
    id_number: str = Field(min_length=1, max_length=64)
    birth_date: date
    gender: str = Field(default="unspecified", pattern="^(male|female|other|unspecified)$")
    living_location: str = ""
    phone_number: str = ""
    near_person_name: str = ""
    near_person_relationship: str = ""
    near_person_phone: str = ""
    notes: str = ""


class CleanerUpdateIn(Schema):
    first_name: str | None = Field(default=None, max_length=150)
    last_name: str | None = Field(default=None, max_length=150)
    gender: str | None = Field(default=None, pattern="^(male|female|other|unspecified)$")
    living_location: str | None = None
    phone_number: str | None = None
    near_person_name: str | None = None
    near_person_relationship: str | None = None
    near_person_phone: str | None = None
    notes: str | None = None


class CleanerStatusIn(Schema):
    status: str = Field(pattern="^(applicant|trainee|active|inactive)$")


class CleanerDocumentOut(Schema):
    id: int
    cleaner_id: int
    document_type: str
    document_number: str
    status: str
    rejection_reason: str
    expires_at: date | None = None
    is_primary_id: bool
    is_identity: bool
    original_filename: str
    content_type: str
    size_bytes: int
    verified_by: str | None = None
    verified_at: datetime | None = None
    created_at: datetime


class DocumentReviewIn(Schema):
    reason: str = Field(default="", max_length=1000)


class DownloadUrlOut(Schema):
    download_url: str
