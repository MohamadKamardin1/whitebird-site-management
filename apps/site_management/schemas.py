"""Pydantic schemas for the site management API."""

from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal
from typing import Any

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
    boundary: dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True
    site_count: int = 0
    created_at: datetime


class ZoneCreateIn(Schema):
    name: str = Field(min_length=2, max_length=160)
    code: str = Field(min_length=2, max_length=12)
    description: str = ""
    boundary: dict[str, Any] = Field(default_factory=dict)


class ZoneUpdateIn(Schema):
    name: str | None = Field(default=None, min_length=2, max_length=160)
    code: str | None = Field(default=None, min_length=2, max_length=12)
    description: str | None = None
    boundary: dict[str, Any] | None = None
    is_active: bool | None = None


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


class SupervisorTimetableEntryIn(Schema):
    supervisor_id: int
    zone_id: int
    site_id: int
    effective_from: date
    effective_to: date | None = None
    work_days: list[str] = Field(min_length=1)
    off_days: list[str] = Field(default_factory=list)
    shift_slot: str = Field(pattern="^(asubuhi|mchana)$")
    relief_person_id: int | None = None
    notes: str = ""


class SupervisorTimetableEntryUpdateIn(Schema):
    effective_from: date | None = None
    effective_to: date | None = None
    work_days: list[str] | None = None
    off_days: list[str] | None = None
    shift_slot: str | None = Field(default=None, pattern="^(asubuhi|mchana)$")
    relief_person_id: int | None = None
    notes: str | None = None
    is_active: bool | None = None


class SupervisorTimetableEntryOut(Schema):
    id: int
    supervisor_id: int
    supervisor_name: str
    supervisor_role: str
    zone_id: int
    zone_name: str
    site_id: int
    site_name: str
    effective_from: date
    effective_to: date | None = None
    work_days: list[str]
    off_days: list[str]
    shift_slot: str
    relief_person_id: int | None = None
    relief_person_name: str = ""
    notes: str = ""
    is_active: bool


class SupervisorChecklistSaveIn(Schema):
    timetable_entry_id: int
    work_date: date
    checklist_kind: str = Field(pattern="^(site_zilizotembelewa|maeneo_yaliyokaguliwa|kazi_zilizofanyika|taarifa_za_vitendeakazi)$")
    table_entries: list[dict[str, Any]] = Field(default_factory=list)
    notes: str = ""


class SupervisorChecklistReviewIn(Schema):
    action: str = Field(pattern="^(reviewed|returned)$")
    reason: str = ""


class SupervisorChecklistOut(Schema):
    id: int
    timetable_entry_id: int
    supervisor_id: int
    supervisor_name: str
    supervisor_role: str
    site_id: int
    site_name: str
    zone_id: int
    zone_name: str
    work_date: date
    shift_slot: str
    checklist_kind: str
    table_entries: list[dict[str, Any]]
    notes: str = ""
    status: str
    submitted_at: datetime | None = None
    return_reason: str = ""
    snapshot: dict[str, Any] = Field(default_factory=dict)


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
    verb: str = ""
    title: str
    body: str = ""
    object_type: str = ""
    object_id: str = ""
    link: str = ""
    is_read: bool
    read_at: datetime | None = None
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


class CleanerSiteAssignmentOut(Schema):
    id: int
    cleaner_id: int
    cleaner_name: str
    site_id: int
    site_name: str
    assignment_type: str
    start_date: date
    end_date: date | None = None
    status: str
    assigned_by: str | None = None
    notes: str
    created_at: datetime
    updated_at: datetime


class CleanerSiteAssignmentCreateIn(Schema):
    cleaner_id: int
    site_id: int
    assignment_type: str = Field(pattern="^(full_time|shift)$")
    start_date: date
    end_date: date | None = None
    notes: str = ""


class CleanerSiteAssignmentUpdateIn(Schema):
    end_date: date | None = None
    notes: str | None = None


class CleanerShiftAssignmentOut(Schema):
    id: int
    assignment_id: int
    shift_id: int
    shift_name: str
    effective_from: date
    effective_to: date | None = None
    is_active: bool


class ShiftAssignIn(Schema):
    shift_id: int
    effective_from: date
    effective_to: date | None = None


class CleanerAreaScheduleOut(Schema):
    id: int
    assignment_id: int
    site_area_id: int
    area_name: str
    operational_role_id: int
    role_name: str
    date: date
    start_time: time
    end_time: time
    shift_id: int | None = None
    shift_name: str | None = None
    notes: str
    is_active: bool
    crosses_midnight: bool


class AreaScheduleCreateIn(Schema):
    site_area_id: int
    operational_role_id: int
    date: date
    start_time: time
    end_time: time
    shift_id: int | None = None
    notes: str = ""


class AreaScheduleUpdateIn(Schema):
    site_area_id: int | None = None
    operational_role_id: int | None = None
    start_time: time | None = None
    end_time: time | None = None
    shift_id: int | None = None
    notes: str | None = None


class ScheduleRowOut(Schema):
    schedule_id: int
    cleaner_id: int
    cleaner_name: str
    assignment_id: int
    assignment_status: str
    site_id: int
    shift_id: int | None = None
    shift_name: str | None = None
    area_id: int
    area_name: str
    role_id: int
    role_name: str
    start_time: str
    end_time: str
    crosses_midnight: bool


class AttendanceRecordOut(Schema):
    id: int
    cleaner_id: int
    cleaner_name: str
    site_id: int
    site_name: str
    shift_id: int | None = None
    shift_name: str | None = None
    attendance_date: date
    status: str
    attendance_outcome: str
    check_in_time: time | None = None
    check_out_time: time | None = None
    notes: str
    review_status: str
    return_reason: str
    submitted_at: datetime | None = None
    is_editable: bool


class AttendanceEntryIn(Schema):
    record_id: int | None = None
    cleaner_id: int | None = None
    shift_id: int | None = None
    status: str = Field(pattern="^(scheduled|present|late|absent|sick|leave|permission|off|not_scheduled)$")
    check_in_time: time | None = None
    check_out_time: time | None = None
    notes: str = ""


class AttendanceBulkIn(Schema):
    site_id: int
    attendance_date: date
    entries: list[AttendanceEntryIn] = Field(min_length=1)
    shift_id: int | None = None


class AttendanceSingleIn(Schema):
    status: str = Field(pattern="^(scheduled|present|late|absent|sick|leave|permission|off|not_scheduled)$")
    check_in_time: time | None = None
    check_out_time: time | None = None
    notes: str = ""


class AttendanceGroupIn(Schema):
    site_id: int
    attendance_date: date
    shift_id: int | None = None
    reason: str = ""


class AttendanceReturnIn(Schema):
    site_id: int | None = None
    attendance_date: date | None = None
    shift_id: int | None = None
    record_id: int | None = None
    reason: str = ""


class AttendanceSubmitOut(Schema):
    submitted: int


class AttendanceSummaryOut(Schema):
    total_scheduled: int
    present: int
    late: int
    absent: int
    sick: int
    leave: int
    permission: int
    off: int
    attendance_rate: float


class TraineeProgramOut(Schema):
    id: int
    cleaner_id: int
    cleaner_name: str
    site_id: int
    site_name: str
    assigned_site_supervisor: str | None = None
    start_date: date
    expected_end_date: date
    actual_end_date: date | None = None
    status: str
    notes: str
    evaluation_count: int = 0
    latest_total: int | None = None


class TraineeProgramCreateIn(Schema):
    cleaner_id: int
    site_id: int
    expected_end_date: date
    start_date: date | None = None
    assigned_site_supervisor_id: int | None = None
    notes: str = ""


class TraineeProgramUpdateIn(Schema):
    assigned_site_supervisor_id: int | None = None
    notes: str | None = None


class TraineeEvaluationOut(Schema):
    id: int
    trainee_program_id: int
    evaluation_date: date
    attendance_score: int
    performance_score: int
    behavior_score: int
    skill_score: int
    total_score: int
    comments: str
    is_final: bool
    evaluated_by: str | None = None


class TraineeEvaluationCreateIn(Schema):
    evaluation_date: date
    attendance_score: int = Field(default=0, ge=0, le=100)
    performance_score: int = Field(default=0, ge=0, le=100)
    behavior_score: int = Field(default=0, ge=0, le=100)
    skill_score: int = Field(default=0, ge=0, le=100)
    total_score: int | None = Field(default=None, ge=0, le=400)
    comments: str = ""
    is_final: bool = False


class TraineeExtendIn(Schema):
    new_expected_end_date: date
    reason: str = Field(min_length=1)


class TraineeDecisionIn(Schema):
    reason: str = Field(default="", min_length=1)
    actual_end_date: date | None = None


class TraineeSummaryOut(Schema):
    total_trainees: int
    in_training: int
    extended: int
    passed: int
    failed: int
    dropped: int


class StoreOut(Schema):
    id: int
    site_id: int
    site_name: str
    store_name: str
    location: str = ""
    managed_by: str | None = None
    managed_by_id: int | None = None
    is_active: bool = True
    item_count: int = 0
    low_stock_count: int = 0
    created_at: datetime


class StoreCreateIn(Schema):
    site_id: int
    store_name: str = Field(min_length=1, max_length=160)
    location: str = Field(default="", max_length=255)
    managed_by_id: int | None = None


class StoreUpdateIn(Schema):
    store_name: str | None = Field(default=None, min_length=1, max_length=160)
    location: str | None = Field(default=None, max_length=255)
    managed_by_id: int | None = None
    is_active: bool | None = None


class StoreItemOut(Schema):
    id: int
    store_id: int
    item_name: str
    item_code: str = ""
    unit: str = "piece"
    category: str = ""
    opening_stock: Decimal
    current_stock: Decimal
    minimum_stock_level: Decimal
    low_stock: bool = False
    is_active: bool = True
    created_at: datetime


class StoreItemCreateIn(Schema):
    item_name: str = Field(min_length=1, max_length=160)
    item_code: str = Field(default="", max_length=32)
    unit: str = Field(default="piece", max_length=32)
    category: str = Field(default="", max_length=64)
    opening_stock: Decimal = Field(default=Decimal("0"), ge=0)
    minimum_stock_level: Decimal | None = Field(default=None, ge=0)


class StoreItemUpdateIn(Schema):
    item_name: str | None = Field(default=None, min_length=1, max_length=160)
    item_code: str | None = Field(default=None, max_length=32)
    unit: str | None = Field(default=None, max_length=32)
    category: str | None = Field(default=None, max_length=64)
    minimum_stock_level: Decimal | None = Field(default=None, ge=0)
    is_active: bool | None = None


class StockMovementOut(Schema):
    id: int
    store_id: int
    store_name: str
    store_item_id: int
    item_name: str
    movement_type: str
    quantity: Decimal
    movement_date: date
    cleaner_id: int | None = None
    cleaner_name: str | None = None
    area_id: int | None = None
    area_name: str | None = None
    notes: str = ""
    recorded_by: str | None = None
    created_at: datetime


class StockMovementCreateIn(Schema):
    store_item_id: int
    movement_type: str = Field(pattern="^(opening|received|issued|returned|damaged|lost|adjustment)$")
    quantity: Decimal
    movement_date: date | None = None
    cleaner_id: int | None = None
    area_id: int | None = None
    notes: str = ""
    reason: str = ""


class StockRequestItemOut(Schema):
    id: int
    store_item_id: int
    item_name: str
    requested_quantity: Decimal
    quantity_left: Decimal = Decimal("0")
    approved_quantity: Decimal | None = None
    unit: str = ""
    notes: str = ""


class StockRequestOut(Schema):
    id: int
    site_id: int
    site_name: str
    store_id: int
    store_name: str
    request_date: date
    requested_by: str | None = None
    status: str
    notes: str = ""
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None
    items: list[StockRequestItemOut] = Field(default_factory=list)
    created_at: datetime


class StockRequestCreateIn(Schema):
    request_date: date | None = None
    notes: str = ""
    items: list[StockRequestItemIn] = Field(min_length=1)


class StockRequestItemIn(Schema):
    store_item_id: int
    requested_quantity: Decimal = Field(gt=0)
    quantity_left: Decimal = Field(default=Decimal("0"), ge=0)
    notes: str = ""


class StockRequestReviewIn(Schema):
    approved: list[StockRequestApprovalIn] = Field(default_factory=list)
    notes: str = ""


class StockRequestApprovalIn(Schema):
    item_id: int
    approved_quantity: Decimal = Field(ge=0)


class StockRequestDecisionIn(Schema):
    reason: str = Field(default="", min_length=1)


class TemplateItemIn(Schema):
    item_label: str = Field(min_length=1, max_length=255)
    item_type: str = Field(pattern="^(yes_no|pass_fail|score|text|photo)$")
    required: bool = True
    sequence: int = Field(default=0, ge=0)
    help_text: str = Field(default="", max_length=255)


class TemplateItemOut(TemplateItemIn):
    id: int


class InspectionTemplateOut(Schema):
    id: int
    template_name: str
    description: str = ""
    site_id: int | None = None
    site_name: str | None = None
    area_id: int | None = None
    area_name: str | None = None
    frequency: str
    is_active: bool = True
    item_count: int = 0
    items: list[TemplateItemOut] = Field(default_factory=list)
    created_at: datetime


class InspectionTemplateCreateIn(Schema):
    template_name: str = Field(min_length=1, max_length=160)
    description: str = ""
    site_id: int | None = None
    area_id: int | None = None
    frequency: str = Field(default="manual", pattern="^(daily|weekly|monthly|manual)$")
    items: list[TemplateItemIn] = Field(default_factory=list)


class InspectionTemplateUpdateIn(Schema):
    template_name: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = None
    frequency: str | None = Field(default=None, pattern="^(daily|weekly|monthly|manual)$")
    items: list[TemplateItemIn] | None = None


class InspectionTemplateStatusIn(Schema):
    is_active: bool


class InspectionStartIn(Schema):
    site_id: int
    area_id: int
    template_id: int
    inspection_date: date | None = None
    shift_id: int | None = None
    inspected_by_id: int | None = None
    notes: str = ""


class InspectionUpdateIn(Schema):
    notes: str | None = None


class InspectionResultOut(Schema):
    id: int
    inspection_id: int
    template_item_id: int
    responsible_cleaner_id: int | None = None
    responsible_cleaner_name: str | None = None
    item_label: str
    item_type: str
    required: bool
    value_text: str = ""
    value_number: Decimal | None = None
    value_boolean: bool | None = None
    passed: bool | None = None
    notes: str = ""
    has_photo: bool = False


class InspectionResultCreateIn(Schema):
    template_item_id: int
    responsible_cleaner_id: int | None = None
    value_text: str = ""
    value_number: Decimal | None = Field(default=None, ge=0, le=100)
    value_boolean: bool | None = None
    passed: bool | None = None
    notes: str = ""


class InspectionResultUpdateIn(Schema):
    responsible_cleaner_id: int | None = None
    value_text: str | None = None
    value_number: Decimal | None = Field(default=None, ge=0, le=100)
    value_boolean: bool | None = None
    passed: bool | None = None
    notes: str | None = None


class InspectionOut(Schema):
    id: int
    site_id: int
    site_name: str
    area_id: int
    area_name: str
    template_id: int
    template_name: str
    inspection_date: date
    shift_id: int | None = None
    shift_name: str | None = None
    inspected_by: str | None = None
    overall_status: str = ""
    score: Decimal | None = None
    notes: str = ""
    status: str
    submitted_at: datetime | None = None
    results: list[InspectionResultOut] = Field(default_factory=list)
    created_at: datetime


class InspectionReturnIn(Schema):
    reason: str = Field(min_length=1)


class InspectionSummaryOut(Schema):
    total_inspections: int
    draft: int
    submitted: int
    reviewed: int
    returned: int
    passed: int
    failed: int
    needs_attention: int
    average_score: Decimal | None = None
    last_inspection_date: date | None = None


class AreaLatestStatusOut(Schema):
    area_id: int
    inspection_id: int
    inspection_date: date
    overall_status: str
    score: Decimal | None = None
    template_name: str


class IssueOut(Schema):
    id: int
    title: str
    description: str = ""
    source: str
    site_id: int
    site_name: str
    area_id: int | None = None
    area_name: str | None = None
    cleaner_id: int | None = None
    cleaner_name: str | None = None
    inspection_id: int | None = None
    issue_category: str
    priority: str
    status: str
    raised_by: str | None = None
    assigned_to: str | None = None
    assigned_to_id: int | None = None
    due_date: date | None = None
    resolved_at: datetime | None = None
    closed_at: datetime | None = None
    escalation_level: int = 0
    is_escalated: bool = False
    job_count: int = 0
    created_at: datetime


class IssueCreateIn(Schema):
    title: str = Field(min_length=1, max_length=200)
    description: str = ""
    source: str = Field(default="manual", pattern="^(inspection|attendance|store|manual|report)$")
    site_id: int
    area_id: int | None = None
    cleaner_id: int | None = None
    inspection_id: int | None = None
    issue_category: str = Field(
        default="other", pattern="^(cleaning_quality|maintenance|safety|materials|behavior|attendance|other)$"
    )
    priority: str = Field(default="medium", pattern="^(low|medium|high|urgent)$")
    due_date: date | None = None


class IssueUpdateIn(Schema):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    issue_category: str | None = Field(
        default=None, pattern="^(cleaning_quality|maintenance|safety|materials|behavior|attendance|other)$"
    )
    priority: str | None = Field(default=None, pattern="^(low|medium|high|urgent)$")
    area_id: int | None = None
    cleaner_id: int | None = None
    due_date: date | None = None


class IssueReviewIn(Schema):
    notes: str = ""


class IssueEscalateIn(Schema):
    reason: str = Field(min_length=1)


class JobOut(Schema):
    id: int
    issue_id: int | None = None
    issue_title: str | None = None
    job_title: str
    description: str = ""
    site_id: int
    site_name: str
    assigned_to_user: str | None = None
    assigned_to_user_id: int | None = None
    assigned_to_cleaner: str | None = None
    assigned_to_cleaner_id: int | None = None
    assigned_by: str | None = None
    due_date: date
    priority: str
    status: str
    completion_notes: str = ""
    has_completion_photo: bool = False
    completed_at: datetime | None = None
    verified_by: str | None = None
    verified_at: datetime | None = None
    closed_at: datetime | None = None
    created_at: datetime


class JobCreateIn(Schema):
    job_title: str = Field(min_length=1, max_length=200)
    description: str = ""
    site_id: int
    issue_id: int | None = None
    assigned_to_user_id: int | None = None
    assigned_to_cleaner_id: int | None = None
    due_date: date | None = None
    priority: str = Field(default="medium", pattern="^(low|medium|high|urgent)$")


class JobUpdateIn(Schema):
    job_title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    due_date: date | None = None
    priority: str | None = Field(default=None, pattern="^(low|medium|high|urgent)$")


class JobAssignIn(Schema):
    assigned_to_user_id: int | None = None
    assigned_to_cleaner_id: int | None = None


class JobCompleteIn(Schema):
    completion_notes: str = ""


class JobReopenIn(Schema):
    reason: str = Field(min_length=1)


class IssueSummaryOut(Schema):
    total_issues: int
    open: int
    under_review: int
    assigned: int
    in_progress: int
    completed: int
    verified: int
    closed: int
    reopened: int
    escalated: int
    high_priority: int
    urgent: int
    category_counts: dict[str, int] = Field(default_factory=dict)


class JobSummaryOut(Schema):
    total_jobs: int
    open: int
    assigned: int
    in_progress: int
    completed: int
    verified: int
    closed: int
    reopened: int
    overdue: int


class DailySiteReportOut(Schema):
    id: int
    site_id: int
    site_name: str
    report_date: date
    attendance_summary: dict[str, Any] = Field(default_factory=dict)
    store_summary: dict[str, Any] = Field(default_factory=dict)
    inspection_summary: dict[str, Any] = Field(default_factory=dict)
    trainee_summary: dict[str, Any] = Field(default_factory=dict)
    issues_summary: dict[str, Any] = Field(default_factory=dict)
    general_comments: str = ""
    challenges: list[str] = Field(default_factory=list)
    status: str
    snapshot: dict[str, Any] = Field(default_factory=dict)
    submitted_at: datetime | None = None
    returned_reason: str = ""
    created_by: str | None = None


class DailySiteReportUpdateIn(Schema):
    general_comments: str = ""


class DailyReportChallengesIn(Schema):
    challenges: list[str] = Field(default_factory=list, max_length=7)


class ReportReturnIn(Schema):
    reason: str = Field(min_length=1)


class ZoneSummaryReportOut(Schema):
    id: int
    zone_id: int
    zone_name: str
    report_date: date
    summary: str = ""
    issues_extracted: list[dict[str, Any]] = Field(default_factory=list)
    site_reports: list[dict[str, Any]] = Field(default_factory=list)
    status: str
    submitted_at: datetime | None = None
    zone_supervisor: str | None = None


class AssistantSummaryOut(Schema):
    id: int
    report_date: date
    zone_ids: list[int] = Field(default_factory=list)
    summary: str = ""
    problems_extracted: list[dict[str, Any]] = Field(default_factory=list)
    recommendations: str = ""
    status: str
    submitted_at: datetime | None = None
    assistant_general_supervisor: str | None = None


class AssistantSummaryGenerateIn(Schema):
    report_date: date
    zone_ids: list[int] | None = None


class GeneralReportOut(Schema):
    id: int
    report_date: date
    final_summary: str = ""
    key_issues: list[dict[str, Any]] = Field(default_factory=list)
    assigned_jobs: list[dict[str, Any]] = Field(default_factory=list)
    recommendations: str = ""
    status: str
    submitted_at: datetime | None = None
    general_supervisor: str | None = None


class ReportStatusRow(Schema):
    site_id: int
    site_name: str
    status: str
    submitted_at: datetime | None = None
    overdue: bool = False


class ReportingStatusOut(Schema):
    report_date: str
    site_reports: list[ReportStatusRow] = Field(default_factory=list)
    missing_site_reports: list[dict[str, Any]] = Field(default_factory=list)
    zone_summary_status: str | None = None
    assistant_summary_status: str | None = None
    general_report_status: str | None = None


class MissingSiteReportOut(Schema):
    site_id: int
    site_name: str
    zone_id: int | None = None
    zone_name: str | None = None


class ZoneReportGenerateIn(Schema):
    zone_id: int
    report_date: date


class GeneralReportGenerateIn(Schema):
    report_date: date


class AssistantSummaryGenerateInDate(Schema):
    report_date: date


class ThemeOut(Schema):
    brand_name: str
    brand_primary_color: str
    brand_accent_color: str
    brand_background_color: str
    logo_url: str | None = None
    version: str = "1.0.0"


class IntegrationSettingsOut(Schema):
    deepseek_configured: bool
    deepseek_key_suffix: str = ""
    mapbox_public_token: str = ""
    updated_at: datetime | None = None


class IntegrationSettingsIn(Schema):
    deepseek_api_key: str | None = None
    mapbox_public_token: str | None = None
