"""Site management domain models.

Design notes
------------
* Site *types*, *statuses* and *asset categories* are configuration rows the
  admin team maintains — never hardcoded business values.
* Sites are soft-deleted (``is_active``) so historical reporting and audit
  trails survive an archive.
* Assignment roles are code-level (permission-relevant), see
  :class:`AssignmentRole`.
* The organisation hierarchy (zones, sites, supervisor assignments) is the
  backbone of the module; supervisor access is derived from *active*
  assignments.
"""

from datetime import date
from typing import Any

from constance import config
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from apps.accounts.validators import validate_phone
from apps.core.files import PrivateMediaStorage
from apps.core.managers import SoftDeleteManager
from apps.core.models import ActivatableModel, PrivateFileModel, TimeStampedModel, UserStampedModel

from .validators import validate_effective_days, validate_shift_time_logic, validate_working_days


class WorkMode(models.TextChoices):
    """How a site schedules its workforce.

    ``work_mode`` is manually configured per site (never inferred) and
    validated on every write path.
    """

    FULL_TIME = "full_time", "Full Time"
    SHIFT = "shift", "Shift"
    FULL_TIME_AND_SHIFT = "full_time_and_shift", "Full Time & Shift"


class SiteType(TimeStampedModel):
    """Configurable classification of a site (e.g. Beach Resort, Villa)."""

    name = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(max_length=120, unique=True)
    description = models.TextField(blank=True, default="")
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Site type"
        verbose_name_plural = "Site types"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class SiteStatus(TimeStampedModel):
    """Configurable lifecycle states a site can move through."""

    name = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(max_length=120, unique=True)
    description = models.TextField(blank=True, default="")
    is_active = models.BooleanField(default=True)
    order = models.PositiveSmallIntegerField(default=0)
    color = models.CharField(
        max_length=9,
        default="#6b7280",
        help_text="Hex colour (e.g. #10b981) used by client dashboards.",
    )

    class Meta:
        verbose_name = "Site status"
        verbose_name_plural = "Site statuses"
        ordering = ["order", "name"]

    def __str__(self) -> str:
        return self.name


class Zone(UserStampedModel, ActivatableModel):
    """A geographic/administrative grouping of sites (e.g. Unguja North)."""

    name = models.CharField(max_length=160)
    code = models.CharField(max_length=12, unique=True, db_index=True)
    description = models.TextField(blank=True, default="")

    class Meta:
        verbose_name = "Zone"
        verbose_name_plural = "Zones"
        ordering = ["name"]
        indexes = [models.Index(fields=["is_active", "name"])]

    def __str__(self) -> str:
        return self.name


class Site(TimeStampedModel):
    """A physical site (property/building) under management."""

    name = models.CharField(max_length=160, help_text="Site name (site_name).")
    slug = models.SlugField(max_length=160, unique=True)
    code = models.CharField(max_length=12, unique=True, db_index=True, help_text="Unique site code (site_code).")
    zone = models.ForeignKey(Zone, on_delete=models.SET_NULL, related_name="sites", null=True, blank=True)
    site_type = models.ForeignKey(SiteType, on_delete=models.PROTECT, related_name="sites", null=True, blank=True)
    status = models.ForeignKey(SiteStatus, on_delete=models.PROTECT, related_name="sites", null=True, blank=True)
    building_name = models.CharField(max_length=200, blank=True, default="")
    location = models.CharField(max_length=255, blank=True, default="")
    description = models.TextField(blank=True, default="")
    address = models.CharField(max_length=255, blank=True, default="")
    city = models.CharField(max_length=120, blank=True, default="")
    region = models.CharField(max_length=120, blank=True, default="")
    country = models.CharField(max_length=2, default="TZ")
    postal_code = models.CharField(max_length=20, blank=True, default="")
    latitude = models.FloatField(null=True, blank=True, validators=[MinValueValidator(-90), MaxValueValidator(90)])
    longitude = models.FloatField(null=True, blank=True, validators=[MinValueValidator(-180), MaxValueValidator(180)])
    capacity = models.PositiveIntegerField(default=0, help_text="Maximum concurrent guests.")
    contact_person = models.CharField(max_length=150, blank=True, default="")
    contact_email = models.EmailField(blank=True, default="")
    contact_phone = models.CharField(max_length=32, blank=True, default="")
    work_mode = models.CharField(
        max_length=24,
        choices=WorkMode.choices,
        default=WorkMode.FULL_TIME,
        db_index=True,
        help_text="Manually configured staffing schedule model.",
    )
    working_days = models.JSONField(
        default=list,
        blank=True,
        validators=[validate_working_days],
        help_text='Working weekday codes (mon..sun), e.g. ["mon","tue"]. Portable ArrayField equivalent.',
    )
    start_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True, default="")
    is_active = models.BooleanField(default=True, db_index=True, help_text="Active/inactive operational flag.")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_sites",
    )

    objects = SoftDeleteManager()

    class Meta:
        verbose_name = "Site"
        verbose_name_plural = "Sites"
        ordering = ["name"]
        indexes = [
            models.Index(fields=["status", "site_type"]),
            models.Index(fields=["is_active", "status"]),
            models.Index(fields=["zone", "is_active"]),
            models.Index(fields=["work_mode", "is_active"]),
        ]

    def __str__(self) -> str:
        return self.name

    def clean(self) -> None:
        super().clean()
        validate_working_days(self.working_days)

    @property
    def department_count(self) -> int:
        return self.departments.count()

    @property
    def asset_count(self) -> int:
        return self.assets.count()

    @property
    def staff_count(self) -> int:
        return self.staff_assignments.count()

    @property
    def supervisor_count(self) -> int:
        return self.supervisor_assignments.filter(is_active=True).count()

    @property
    def has_operational_history(self) -> bool:
        """True when the site holds operational records.

        Guards the admin against accidental hard deletion (see ``SiteAdmin``).
        """
        return (
            self.departments.exists()
            or self.assets.exists()
            or self.staff_assignments.exists()
            or self.supervisor_assignments.exists()
        )


class Department(TimeStampedModel):
    """An operational unit within a site (e.g. Housekeeping, Front Office)."""

    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name="departments")
    name = models.CharField(max_length=160)
    description = models.TextField(blank=True, default="")
    manager = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="managed_departments",
    )
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_departments",
    )

    objects = SoftDeleteManager()

    class Meta:
        verbose_name = "Department"
        verbose_name_plural = "Departments"
        ordering = ["site__name", "name"]
        constraints = [models.UniqueConstraint(fields=["site", "name"], name="uniq_department_site_name")]

    def __str__(self) -> str:
        return f"{self.name} @ {self.site.name}"


class AssetCategory(TimeStampedModel):
    """Configurable grouping for assets (e.g. Vehicles, Electronics)."""

    name = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(max_length=120, unique=True)
    description = models.TextField(blank=True, default="")
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Asset category"
        verbose_name_plural = "Asset categories"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Asset(TimeStampedModel):
    """A physical asset tracked against a site."""

    class Condition(models.TextChoices):
        OPERATIONAL = "operational", "Operational"
        UNDER_MAINTENANCE = "under_maintenance", "Under Maintenance"
        RETIRED = "retired", "Retired"

    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name="assets")
    category = models.ForeignKey(AssetCategory, on_delete=models.PROTECT, related_name="assets", null=True, blank=True)
    name = models.CharField(max_length=160)
    serial_number = models.CharField(max_length=100, blank=True, default="", db_index=True)
    quantity = models.PositiveIntegerField(default=1)
    condition = models.CharField(max_length=24, choices=Condition.choices, default=Condition.OPERATIONAL)
    is_active = models.BooleanField(default=True)

    objects = SoftDeleteManager()

    class Meta:
        verbose_name = "Asset"
        verbose_name_plural = "Assets"
        ordering = ["site__name", "name"]
        constraints = [models.UniqueConstraint(fields=["site", "serial_number"], name="uniq_asset_site_serial")]

    def __str__(self) -> str:
        return f"{self.name} ({self.site.name})"


class AssignmentRole(models.TextChoices):
    """Role of a staff member *within a specific site*.

    Site-level roles complement the platform-level :class:`RoleCode`. Both are
    code-enforced because they drive authorization decisions.
    """

    SITE_MANAGER = "site_manager", "Site Manager"
    STAFF = "staff", "Staff"


class StaffAssignment(TimeStampedModel):
    """Links a user to a site with a site-scoped role."""

    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name="staff_assignments")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="staff_assignments")
    role = models.CharField(max_length=24, choices=AssignmentRole.choices)
    is_primary = models.BooleanField(default=False, help_text="Primary site for the user.")
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_staff",
    )

    class Meta:
        verbose_name = "Staff assignment"
        verbose_name_plural = "Staff assignments"
        ordering = ["site__name", "user__email"]
        constraints = [models.UniqueConstraint(fields=["site", "user"], name="uniq_assignment_site_user")]

    def __str__(self) -> str:
        return f"{self.user} -> {self.site.name} ({self.role})"


class AssignmentMixin(models.Model):
    """Shared fields/behaviour for supervisor assignments.

    An assignment is *active* when ``is_active`` is true and the current date
    falls inside ``[assigned_from, assigned_to]``. ``created_by``/``updated_by``
    come from ``UserStampedModel`` on the concrete models.
    """

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    assigned_from = models.DateField(db_index=True)
    assigned_to = models.DateField(null=True, blank=True, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        abstract = True

    def clean(self) -> None:
        super().clean()
        if self.assigned_from and self.assigned_to and self.assigned_to < self.assigned_from:
            raise ValidationError("assigned_to cannot be earlier than assigned_from.")

    @property
    def is_current(self) -> bool:
        today = timezone.localdate()
        return not (self.assigned_from > today or (self.assigned_to is not None and self.assigned_to < today))


class SiteSupervisorAssignment(AssignmentMixin, UserStampedModel):
    """A user assigned as supervisor of a site for a date range."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="site_supervisor_assignments"
    )
    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name="supervisor_assignments")
    is_primary = models.BooleanField(default=False, help_text="Primary supervisor of the site.")

    class Meta:
        verbose_name = "Site supervisor assignment"
        verbose_name_plural = "Site supervisor assignments"
        ordering = ["site__name", "user__email"]
        constraints = [
            models.UniqueConstraint(
                fields=["site", "user"],
                condition=models.Q(is_active=True),
                name="uniq_active_site_supervisor",
            )
        ]
        indexes = [
            models.Index(fields=["user", "is_active"]),
            models.Index(fields=["site", "is_active"]),
        ]

    def __str__(self) -> str:
        return f"{self.user} supervises {self.site.name}"

    def clean(self) -> None:
        super().clean()
        if not self.is_active:
            return
        maximum = int(config.MAX_SITE_SUPERVISORS_PER_SITE)
        active = SiteSupervisorAssignment.objects.filter(site=self.site, is_active=True)
        if self.pk is not None:
            active = active.exclude(pk=self.pk)
        if active.count() >= maximum:
            raise ValidationError(f"A site can have at most {maximum} active supervisors.")


class ZoneSupervisorAssignment(AssignmentMixin, UserStampedModel):
    """A user assigned as supervisor of a zone for a date range."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="zone_supervisor_assignments"
    )
    zone = models.ForeignKey(Zone, on_delete=models.CASCADE, related_name="supervisor_assignments")

    class Meta:
        verbose_name = "Zone supervisor assignment"
        verbose_name_plural = "Zone supervisor assignments"
        ordering = ["zone__name", "user__email"]
        constraints = [
            models.UniqueConstraint(
                fields=["zone", "user"],
                condition=models.Q(is_active=True),
                name="uniq_active_zone_supervisor",
            )
        ]
        indexes = [
            models.Index(fields=["user", "is_active"]),
            models.Index(fields=["zone", "is_active"]),
        ]

    def __str__(self) -> str:
        return f"{self.user} supervises zone {self.zone.name}"


class AssistantGeneralSupervisorAssignment(AssignmentMixin, UserStampedModel):
    """A user acting as assistant general supervisor.

    ``all_zones=True`` grants coverage of every zone (``zone`` may be null);
    otherwise ``zone`` is required.
    """

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="ags_assignments")
    zone = models.ForeignKey(Zone, on_delete=models.CASCADE, related_name="ags_assignments", null=True, blank=True)
    all_zones = models.BooleanField(default=False, help_text="Covers every zone when true.")

    class Meta:
        verbose_name = "Assistant general supervisor assignment"
        verbose_name_plural = "Assistant general supervisor assignments"
        ordering = ["user__email"]
        constraints = [
            models.UniqueConstraint(
                fields=["user"], condition=models.Q(is_active=True), name="uniq_active_ags_assignment"
            )
        ]

    def __str__(self) -> str:
        scope = "all zones" if self.all_zones else (self.zone.name if self.zone else "—")
        return f"{self.user} assists general ({scope})"

    def clean(self) -> None:
        super().clean()
        if not self.all_zones and self.zone is None:
            raise ValidationError("A zone is required when all_zones is false.")


class Notification(TimeStampedModel):
    """In-platform notification targeted at a user."""

    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    title = models.CharField(max_length=160)
    body = models.TextField(blank=True, default="")
    entity_type = models.CharField(max_length=64, blank=True, default="")
    entity_id = models.CharField(max_length=36, blank=True, default="")
    is_read = models.BooleanField(default=False, db_index=True)

    class Meta:
        verbose_name = "Notification"
        verbose_name_plural = "Notifications"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"[{self.recipient}] {self.title}"


# --------------------------------------------------------------------------- #
# Site configuration: shifts, areas, operational roles, working rules
# --------------------------------------------------------------------------- #


class SiteShift(UserStampedModel):
    """A manually configured shift window for a site.

    Shift names, codes, times and effective days are fully manual — nothing is
    hardcoded. Overnight shifts (``end_time <= start_time``) are supported and
    flagged by :attr:`crosses_midnight`.
    """

    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name="shifts")
    shift_name = models.CharField(max_length=160)
    shift_code = models.CharField(max_length=16, blank=True, default="")
    start_time = models.TimeField(db_index=True)
    end_time = models.TimeField(db_index=True)
    effective_days = models.JSONField(
        default=list,
        validators=[validate_effective_days],
        help_text="Day codes the shift runs (mon..sun). At least one required.",
    )
    sequence = models.PositiveSmallIntegerField(default=0, help_text="Display order within the site.")
    description = models.TextField(blank=True, default="")
    is_active = models.BooleanField(default=True, db_index=True)

    objects = SoftDeleteManager()

    class Meta:
        verbose_name = "Site shift"
        verbose_name_plural = "Site shifts"
        ordering = ["site__name", "sequence", "start_time"]
        constraints = [
            models.UniqueConstraint(
                fields=["site", "shift_name"],
                condition=models.Q(is_active=True),
                name="uniq_active_shift_name",
            ),
            models.UniqueConstraint(
                fields=["site", "shift_code"],
                condition=models.Q(is_active=True, shift_code__gt=""),
                name="uniq_active_shift_code",
            ),
        ]
        indexes = [models.Index(fields=["site", "is_active"])]

    def __str__(self) -> str:
        return f"{self.shift_name} @ {self.site.name}"

    @property
    def crosses_midnight(self) -> bool:
        return self.end_time <= self.start_time

    @property
    def has_operational_usage(self) -> bool:
        """True once future attendance/task records reference this shift."""
        for related in ("attendance_records", "task_assignments", "job_records"):
            manager = getattr(self, related, None)
            if manager is not None and manager.exists():
                return True
        return False

    def clean(self) -> None:
        super().clean()
        validate_shift_time_logic(self.start_time, self.end_time)
        validate_effective_days(self.effective_days)


class SiteArea(UserStampedModel):
    """A physically/functionally distinct area within a site (e.g. a floor)."""

    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name="areas")
    area_name = models.CharField(max_length=160)
    area_code = models.CharField(max_length=16, blank=True, default="")
    floor = models.CharField(max_length=32, blank=True, default="")
    description = models.TextField(blank=True, default="")
    is_active = models.BooleanField(default=True, db_index=True)

    objects = SoftDeleteManager()

    class Meta:
        verbose_name = "Site area"
        verbose_name_plural = "Site areas"
        ordering = ["site__name", "area_name"]
        constraints = [models.UniqueConstraint(fields=["site", "area_name"], name="uniq_area_name_per_site")]
        indexes = [models.Index(fields=["site", "is_active"])]

    def __str__(self) -> str:
        return f"{self.area_name} @ {self.site.name}"

    @property
    def has_operational_usage(self) -> bool:
        """True once future schedules/inspections reference this area."""
        for related in ("schedules", "inspections", "task_assignments"):
            manager = getattr(self, related, None)
            if manager is not None and manager.exists():
                return True
        return False


class OperationalRole(UserStampedModel):
    """Globally configurable operational role a cleaner/trainee can hold.

    Examples (all configurable, never hardcoded): Toilet Cleaner, Floor
    Cleaner, Garbage Collector, Window Cleaner, Compound Sweeper.
    """

    name = models.CharField(max_length=120, unique=True)
    code = models.CharField(max_length=24, unique=True, db_index=True)
    description = models.TextField(blank=True, default="")
    is_active = models.BooleanField(default=True, db_index=True)

    objects = SoftDeleteManager()

    class Meta:
        verbose_name = "Operational role"
        verbose_name_plural = "Operational roles"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name

    @property
    def has_operational_usage(self) -> bool:
        """True once future assignments reference this role."""
        for related in ("role_assignments", "task_assignments"):
            manager = getattr(self, related, None)
            if manager is not None and manager.exists():
                return True
        return False


class SiteWorkingRule(UserStampedModel):
    """Per-site operational configuration flags.

    Keeps site behaviour explicit and admin-configurable instead of hardcoded
    assumptions about how a site runs.
    """

    site = models.OneToOneField(Site, on_delete=models.CASCADE, related_name="working_rule")
    allowed_assignment_types = models.JSONField(
        default=list,
        blank=True,
        help_text="Configurable assignment type codes permitted at this site.",
    )
    attendance_locked = models.BooleanField(
        default=False,
        help_text="Prevents attendance edits outside authorised flows.",
    )
    require_shift_area_assignment = models.BooleanField(
        default=False,
        help_text="Staff must be assigned to both a shift and an area.",
    )
    allow_temporary_transfers = models.BooleanField(
        default=False,
        help_text="Permits temporary staff transfers between sites.",
    )

    class Meta:
        verbose_name = "Site working rule"
        verbose_name_plural = "Site working rules"

    def __str__(self) -> str:
        return f"Working rules for {self.site.name}"


# --------------------------------------------------------------------------- #
# Cleaner registry
# --------------------------------------------------------------------------- #


class CleanerStatus(models.TextChoices):
    APPLICANT = "applicant", "Applicant"
    TRAINEE = "trainee", "Trainee"
    ACTIVE = "active", "Active"
    INACTIVE = "inactive", "Inactive"


class IdType(models.TextChoices):
    BIRTH_CERTIFICATE = "birth_certificate", "Birth Certificate"
    NIDA = "nida", "NIDA"
    ZANZIBAR_ID = "zanzibar_id", "Zanzibar ID"


class Gender(models.TextChoices):
    MALE = "male", "Male"
    FEMALE = "female", "Female"
    OTHER = "other", "Other"
    UNSPECIFIED = "unspecified", "Unspecified"


class Cleaner(UserStampedModel):
    """Master data for a cleaner/applicant/trainee.

    ID numbers are stored upper-case/trimmed; the ``(id_type, id_number)``
    pair is unique. Privacy: full ID numbers and phone numbers are masked in
    list responses unless the caller holds the sensitive-document permission.
    """

    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    id_type = models.CharField(max_length=24, choices=IdType.choices, db_index=True)
    id_number = models.CharField(max_length=64, db_index=True)
    gender = models.CharField(max_length=16, choices=Gender.choices, default=Gender.UNSPECIFIED)
    birth_date = models.DateField()
    living_location = models.CharField(max_length=255, blank=True, default="")
    phone_number = models.CharField(max_length=16, blank=True, default="", validators=[validate_phone])
    near_person_name = models.CharField(max_length=150, blank=True, default="")
    near_person_relationship = models.CharField(max_length=120, blank=True, default="")
    near_person_phone = models.CharField(max_length=16, blank=True, default="", validators=[validate_phone])
    profile_photo = models.ImageField(
        storage=PrivateMediaStorage(),
        upload_to="cleaners/photos/%Y/%m/",
        null=True,
        blank=True,
    )
    status = models.CharField(
        max_length=16, choices=CleanerStatus.choices, default=CleanerStatus.APPLICANT, db_index=True
    )
    registration_date = models.DateField(default=date.today, db_index=True)
    notes = models.TextField(blank=True, default="")

    class Meta:
        verbose_name = "Cleaner"
        verbose_name_plural = "Cleaners"
        ordering = ["last_name", "first_name"]
        constraints = [models.UniqueConstraint(fields=["id_type", "id_number"], name="uniq_cleaner_id_type_number")]
        indexes = [models.Index(fields=["status", "registration_date"])]

    def __str__(self) -> str:
        return self.full_name

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def has_verified_id(self) -> bool:
        """True when at least one verified identity document exists."""
        return self.documents.filter(
            status=CleanerDocumentStatus.VERIFIED,
            document_type__in=[
                CleanerDocumentType.BIRTH_CERTIFICATE,
                CleanerDocumentType.NIDA,
                CleanerDocumentType.ZANZIBAR_ID,
            ],
        ).exists()

    @property
    def has_operational_history(self) -> bool:
        """True when documents or future operational records reference this cleaner."""
        if self.documents.exists():
            return True
        for related in ("attendance_records", "task_assignments"):
            manager = getattr(self, related, None)
            if manager is not None and manager.exists():
                return True
        return False

    def clean(self) -> None:
        super().clean()
        if self.birth_date and self.birth_date > timezone.localdate():
            raise ValidationError("birth_date cannot be in the future.", code="future_birth_date")
        min_age = int(config.MIN_CLEANER_AGE)
        age = _age_years(self.birth_date)
        if age is not None and age < min_age:
            raise ValidationError(f"Cleaner must be at least {min_age} years old.", code="underage")

    def save(self, *args: Any, **kwargs: Any) -> None:
        self.id_number = (self.id_number or "").strip().upper()
        super().save(*args, **kwargs)


def _age_years(birth_date: date | None) -> int | None:
    if birth_date is None:
        return None
    today = timezone.localdate()
    return today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))


class CleanerDocumentType(models.TextChoices):
    BIRTH_CERTIFICATE = "birth_certificate", "Birth Certificate"
    NIDA = "nida", "NIDA"
    ZANZIBAR_ID = "zanzibar_id", "Zanzibar ID"
    PROFILE_PHOTO = "profile_photo", "Profile Photo"
    OTHER = "other", "Other"


class CleanerDocumentStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    VERIFIED = "verified", "Verified"
    REJECTED = "rejected", "Rejected"


class CleanerDocument(PrivateFileModel):
    """A privately stored document attached to a cleaner.

    Files live on the private storage backend; access is only via signed
    download tokens. Only *verified* identity documents count toward ACTIVE
    eligibility.
    """

    cleaner = models.ForeignKey(Cleaner, on_delete=models.CASCADE, related_name="documents")
    document_type = models.CharField(max_length=24, choices=CleanerDocumentType.choices, db_index=True)
    document_number = models.CharField(max_length=64, blank=True, default="")
    file_hash = models.CharField(max_length=64, blank=True, default="", db_index=True)
    status = models.CharField(
        max_length=16, choices=CleanerDocumentStatus.choices, default=CleanerDocumentStatus.PENDING, db_index=True
    )
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True, default="")
    expires_at = models.DateField(null=True, blank=True)
    is_primary_id = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )

    class Meta:
        verbose_name = "Cleaner document"
        verbose_name_plural = "Cleaner documents"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["cleaner", "status"])]

    def __str__(self) -> str:
        return f"{self.document_type} for {self.cleaner} ({self.status})"

    @property
    def is_identity(self) -> bool:
        return self.document_type in {
            CleanerDocumentType.BIRTH_CERTIFICATE,
            CleanerDocumentType.NIDA,
            CleanerDocumentType.ZANZIBAR_ID,
        }


# --------------------------------------------------------------------------- #
# Cleaner assignment & scheduling
# --------------------------------------------------------------------------- #


class CleanerAssignmentType(models.TextChoices):
    FULL_TIME = "full_time", "Full Time"
    SHIFT = "shift", "Shift"


class CleanerAssignmentStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    ACTIVE = "active", "Active"
    ENDED = "ended", "Ended"
    SUSPENDED = "suspended", "Suspended"


def _assignment_type_matches_site(assignment_type: str, site: Site) -> bool:
    if site.work_mode == WorkMode.FULL_TIME:
        return assignment_type == CleanerAssignmentType.FULL_TIME.value
    if site.work_mode == WorkMode.SHIFT:
        return assignment_type == CleanerAssignmentType.SHIFT.value
    return assignment_type in {CleanerAssignmentType.FULL_TIME.value, CleanerAssignmentType.SHIFT.value}


class CleanerSiteAssignment(UserStampedModel):
    """Official assignment of a cleaner to a site.

    Only ACTIVE cleaners hold ACTIVE assignments; applicants/trainees are
    captured as DRAFT. History is protected — assignments are ended, never
    hard-deleted.
    """

    cleaner = models.ForeignKey(Cleaner, on_delete=models.CASCADE, related_name="site_assignments")
    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name="cleaner_assignments")
    assignment_type = models.CharField(max_length=16, choices=CleanerAssignmentType.choices)
    start_date = models.DateField(db_index=True)
    end_date = models.DateField(null=True, blank=True, db_index=True)
    status = models.CharField(
        max_length=16,
        choices=CleanerAssignmentStatus.choices,
        default=CleanerAssignmentStatus.DRAFT,
        db_index=True,
    )
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    notes = models.TextField(blank=True, default="")

    class Meta:
        verbose_name = "Cleaner site assignment"
        verbose_name_plural = "Cleaner site assignments"
        ordering = ["-start_date", "cleaner__last_name"]
        constraints = [
            models.UniqueConstraint(
                fields=["cleaner", "site"],
                condition=models.Q(status__in=[CleanerAssignmentStatus.ACTIVE, CleanerAssignmentStatus.SUSPENDED]),
                name="uniq_active_cleaner_site_assignment",
            )
        ]
        indexes = [models.Index(fields=["site", "status", "assignment_type"])]

    def __str__(self) -> str:
        return f"{self.cleaner.full_name} @ {self.site.name} ({self.status})"

    @property
    def has_operational_history(self) -> bool:
        return self.shift_assignments.exists() or self.area_schedules.exists()

    def clean(self) -> None:
        super().clean()
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValidationError("end_date cannot be earlier than start_date.", code="invalid_dates")
        if not _assignment_type_matches_site(self.assignment_type, self.site):
            raise ValidationError(
                f"Assignment type '{self.assignment_type}' does not match the site's work mode "
                f"({self.site.get_work_mode_display()}).",
                code="assignment_type_mismatch",
            )
        if self.status == CleanerAssignmentStatus.ACTIVE and self.cleaner.status != CleanerStatus.ACTIVE:
            raise ValidationError(
                "Only ACTIVE cleaners can hold ACTIVE assignments.",
                code="cleaner_not_active",
            )


class CleanerShiftAssignment(UserStampedModel):
    """Binds a shift to a site assignment (shift-based cleaners only)."""

    assignment = models.ForeignKey(CleanerSiteAssignment, on_delete=models.CASCADE, related_name="shift_assignments")
    shift = models.ForeignKey(SiteShift, on_delete=models.CASCADE, related_name="cleaner_assignments")
    effective_from = models.DateField(db_index=True)
    effective_to = models.DateField(null=True, blank=True, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        verbose_name = "Cleaner shift assignment"
        verbose_name_plural = "Cleaner shift assignments"
        ordering = ["-effective_from"]
        constraints = [
            models.UniqueConstraint(
                fields=["assignment", "shift"],
                condition=models.Q(is_active=True),
                name="uniq_active_assignment_shift",
            )
        ]
        indexes = [models.Index(fields=["assignment", "is_active"])]

    def __str__(self) -> str:
        return f"{self.assignment.cleaner.full_name} -> {self.shift.shift_name}"

    def clean(self) -> None:
        super().clean()
        if self.assignment.site_id != self.shift.site_id:
            raise ValidationError("Shift must belong to the assignment's site.", code="shift_site_mismatch")
        if self.assignment.assignment_type != CleanerAssignmentType.SHIFT:
            raise ValidationError("Shift assignments require a SHIFT-type assignment.", code="not_shift_assignment")
        if self.effective_from and self.effective_to and self.effective_to < self.effective_from:
            raise ValidationError("effective_to cannot be earlier than effective_from.", code="invalid_dates")


class CleanerAreaSchedule(UserStampedModel):
    """A dated area/task/time responsibility for an assigned cleaner.

    Supports overnight schedules (``end_time <= start_time``) and multiple
    area assignments per day as long as time ranges do not overlap.
    """

    assignment = models.ForeignKey(CleanerSiteAssignment, on_delete=models.CASCADE, related_name="area_schedules")
    site_area = models.ForeignKey(SiteArea, on_delete=models.CASCADE, related_name="area_schedules")
    operational_role = models.ForeignKey(OperationalRole, on_delete=models.PROTECT, related_name="area_schedules")
    date = models.DateField(db_index=True)
    start_time = models.TimeField()
    end_time = models.TimeField()
    shift = models.ForeignKey(
        SiteShift, on_delete=models.SET_NULL, null=True, blank=True, related_name="area_schedules"
    )
    notes = models.TextField(blank=True, default="")
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        verbose_name = "Cleaner area schedule"
        verbose_name_plural = "Cleaner area schedules"
        ordering = ["date", "start_time"]
        indexes = [
            models.Index(fields=["site_area", "date"]),
            models.Index(fields=["assignment", "date"]),
            models.Index(fields=["date", "is_active"]),
        ]

    def __str__(self) -> str:
        return f"{self.assignment.cleaner.full_name} {self.date} {self.site_area.area_name}"

    @property
    def crosses_midnight(self) -> bool:
        return self.end_time <= self.start_time

    def clean(self) -> None:
        super().clean()
        if self.site_area.site_id != self.assignment.site_id:
            raise ValidationError("Area must belong to the assignment's site.", code="area_site_mismatch")
        if self.shift_id and self.shift is not None and self.shift.site_id != self.assignment.site_id:
            raise ValidationError("Shift must belong to the assignment's site.", code="shift_site_mismatch")


# --------------------------------------------------------------------------- #
# Attendance
# --------------------------------------------------------------------------- #


class AttendanceStatus(models.TextChoices):
    SCHEDULED = "scheduled", "Scheduled"
    PRESENT = "present", "Present"
    LATE = "late", "Late"
    ABSENT = "absent", "Absent"
    SICK = "sick", "Sick"
    LEAVE = "leave", "Leave"
    PERMISSION = "permission", "Permission"
    OFF = "off", "Off"
    NOT_SCHEDULED = "not_scheduled", "Not Scheduled"


class AttendanceReviewStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    SUBMITTED = "submitted", "Submitted"
    REVIEWED = "reviewed", "Reviewed"
    RETURNED = "returned", "Returned"
    LOCKED = "locked", "Locked"


class AttendanceRecord(UserStampedModel):
    """Daily attendance record for a cleaner at a site.

    Uniqueness: one record per cleaner+date (full-time), or per
    cleaner+shift+date (shift sites), enforced by partial unique constraints.
    """

    cleaner = models.ForeignKey(Cleaner, on_delete=models.CASCADE, related_name="attendance_records")
    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name="attendance_records")
    shift = models.ForeignKey(
        SiteShift, on_delete=models.SET_NULL, null=True, blank=True, related_name="attendance_records"
    )
    attendance_date = models.DateField(db_index=True)
    status = models.CharField(
        max_length=16, choices=AttendanceStatus.choices, default=AttendanceStatus.SCHEDULED, db_index=True
    )
    check_in_time = models.TimeField(null=True, blank=True)
    check_out_time = models.TimeField(null=True, blank=True)
    notes = models.TextField(blank=True, default="")
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="recorded_attendance",
    )
    submitted_at = models.DateTimeField(null=True, blank=True)
    review_status = models.CharField(
        max_length=16,
        choices=AttendanceReviewStatus.choices,
        default=AttendanceReviewStatus.DRAFT,
        db_index=True,
    )
    return_reason = models.TextField(blank=True, default="")

    class Meta:
        verbose_name = "Attendance record"
        verbose_name_plural = "Attendance records"
        ordering = ["attendance_date", "site__name", "cleaner__last_name"]
        constraints = [
            models.UniqueConstraint(
                fields=["cleaner", "site", "attendance_date"],
                condition=models.Q(shift__isnull=True),
                name="uniq_attendance_ft_per_day",
            ),
            models.UniqueConstraint(
                fields=["cleaner", "site", "shift", "attendance_date"],
                condition=models.Q(shift__isnull=False),
                name="uniq_attendance_shift_per_day",
            ),
        ]
        indexes = [
            models.Index(fields=["site", "attendance_date"]),
            models.Index(fields=["site", "attendance_date", "shift"]),
            models.Index(fields=["cleaner", "attendance_date"]),
        ]

    def __str__(self) -> str:
        return f"{self.cleaner.full_name} {self.attendance_date} ({self.status})"

    @property
    def is_editable(self) -> bool:
        return self.review_status in {
            AttendanceReviewStatus.DRAFT,
            AttendanceReviewStatus.RETURNED,
        }


# --------------------------------------------------------------------------- #
# Trainee lifecycle
# --------------------------------------------------------------------------- #


class TraineeProgramStatus(models.TextChoices):
    IN_TRAINING = "in_training", "In Training"
    EXTENDED = "extended", "Extended"
    PASSED = "passed", "Passed"
    FAILED = "failed", "Failed"
    DROPPED = "dropped", "Dropped"


class TraineeProgram(UserStampedModel):
    """A training program a cleaner must pass before becoming an official cleaner."""

    cleaner = models.ForeignKey(Cleaner, on_delete=models.CASCADE, related_name="trainee_programs")
    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name="trainee_programs")
    assigned_site_supervisor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="supervised_trainees",
    )
    start_date = models.DateField(db_index=True)
    expected_end_date = models.DateField()
    actual_end_date = models.DateField(null=True, blank=True)
    status = models.CharField(
        max_length=16,
        choices=TraineeProgramStatus.choices,
        default=TraineeProgramStatus.IN_TRAINING,
        db_index=True,
    )
    notes = models.TextField(blank=True, default="")

    class Meta:
        verbose_name = "Trainee program"
        verbose_name_plural = "Trainee programs"
        ordering = ["-start_date", "cleaner__last_name"]
        constraints = [
            models.UniqueConstraint(
                fields=["cleaner"],
                condition=models.Q(status__in=[TraineeProgramStatus.IN_TRAINING, TraineeProgramStatus.EXTENDED]),
                name="uniq_active_trainee_program",
            )
        ]
        indexes = [models.Index(fields=["site", "status"])]

    def __str__(self) -> str:
        return f"{self.cleaner.full_name} trainee @ {self.site.name} ({self.status})"

    @property
    def is_active_program(self) -> bool:
        return self.status in {TraineeProgramStatus.IN_TRAINING, TraineeProgramStatus.EXTENDED}

    def clean(self) -> None:
        super().clean()
        if (
            self.status in {TraineeProgramStatus.PASSED, TraineeProgramStatus.FAILED, TraineeProgramStatus.DROPPED}
            and not self.actual_end_date
        ):
            raise ValidationError(
                "actual_end_date is required for final program statuses.",
                code="actual_end_date_required",
            )
        if self.expected_end_date and self.expected_end_date < self.start_date:
            raise ValidationError("expected_end_date cannot be earlier than start_date.", code="invalid_dates")


class TraineeEvaluation(TimeStampedModel):
    """Periodic or final evaluation of a trainee program."""

    trainee_program = models.ForeignKey(TraineeProgram, on_delete=models.CASCADE, related_name="evaluations")
    evaluation_date = models.DateField(db_index=True)
    attendance_score = models.PositiveSmallIntegerField(default=0, validators=[MaxValueValidator(100)])
    performance_score = models.PositiveSmallIntegerField(default=0, validators=[MaxValueValidator(100)])
    behavior_score = models.PositiveSmallIntegerField(default=0, validators=[MaxValueValidator(100)])
    skill_score = models.PositiveSmallIntegerField(default=0, validators=[MaxValueValidator(100)])
    total_score = models.PositiveSmallIntegerField(null=True, blank=True, validators=[MaxValueValidator(400)])
    comments = models.TextField(blank=True, default="")
    is_final = models.BooleanField(default=False, help_text="Final evaluation required before a trainee can pass.")
    evaluated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="trainee_evaluations",
    )

    class Meta:
        verbose_name = "Trainee evaluation"
        verbose_name_plural = "Trainee evaluations"
        ordering = ["-evaluation_date"]

    def __str__(self) -> str:
        return f"Evaluation for {self.trainee_program.cleaner.full_name} on {self.evaluation_date}"

    def clean(self) -> None:
        super().clean()
        if self.total_score is None:
            self.total_score = self.attendance_score + self.performance_score + self.behavior_score + self.skill_score


# --------------------------------------------------------------------------- #
# Site store & stock requests
# --------------------------------------------------------------------------- #


class StockMovementType(models.TextChoices):
    OPENING = "opening", "Opening"
    RECEIVED = "received", "Received"
    ISSUED = "issued", "Issued"
    RETURNED = "returned", "Returned"
    DAMAGED = "damaged", "Damaged"
    LOST = "lost", "Lost"
    ADJUSTMENT = "adjustment", "Adjustment"


INCREASING_MOVEMENT_TYPES = {StockMovementType.OPENING, StockMovementType.RECEIVED, StockMovementType.RETURNED}
DECREASING_MOVEMENT_TYPES = {StockMovementType.ISSUED, StockMovementType.DAMAGED, StockMovementType.LOST}


class SiteStore(UserStampedModel, ActivatableModel):
    """A store location within a site. Sites may run one or more stores."""

    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name="stores")
    store_name = models.CharField(max_length=160)
    location = models.CharField(max_length=255, blank=True, default="")
    managed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="managed_stores",
    )

    class Meta:
        verbose_name = "Site store"
        verbose_name_plural = "Site stores"
        ordering = ["site__name", "store_name"]
        indexes = [models.Index(fields=["site", "is_active"])]

    def __str__(self) -> str:
        return f"{self.store_name} @ {self.site.name}"

    @property
    def item_count(self) -> int:
        return self.items.count()

    @property
    def low_stock_count(self) -> int:
        return self.items.filter(current_stock__lte=models.F("minimum_stock_level")).count()


class StoreItem(UserStampedModel, ActivatableModel):
    """A stocked item in a site store with running stock level and reorder point."""

    store = models.ForeignKey(SiteStore, on_delete=models.CASCADE, related_name="items")
    item_name = models.CharField(max_length=160)
    item_code = models.CharField(max_length=32, blank=True, default="")
    unit = models.CharField(max_length=32, default="piece")
    category = models.CharField(max_length=64, blank=True, default="")
    opening_stock = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    current_stock = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    minimum_stock_level = models.DecimalField(max_digits=10, decimal_places=2, default=5)

    class Meta:
        verbose_name = "Store item"
        verbose_name_plural = "Store items"
        ordering = ["store__store_name", "item_name"]
        constraints = [
            models.UniqueConstraint(fields=["store", "item_name"], name="uniq_store_item_name"),
            models.UniqueConstraint(
                fields=["store", "item_code"],
                condition=models.Q(item_code__gt=""),
                name="uniq_store_item_code",
            ),
        ]
        indexes = [models.Index(fields=["store", "is_active"])]

    def __str__(self) -> str:
        return f"{self.item_name} @ {self.store}"

    @property
    def low_stock(self) -> bool:
        """True when current stock is at or below the reorder point."""
        return self.current_stock <= self.minimum_stock_level


class StockMovement(UserStampedModel):
    """An immutable stock movement against a store item.

    ``quantity`` is the signed change applied to ``current_stock``: positive
    for OPENING/RECEIVED/RETURNED, negative for ISSUED/DAMAGED/LOST, and signed
    (positive increase / negative decrease) for ADJUSTMENT. ``abs(quantity)``
    is always the magnitude; magnitude is strictly positive.
    """

    store_item = models.ForeignKey(StoreItem, on_delete=models.CASCADE, related_name="movements")
    movement_type = models.CharField(max_length=16, choices=StockMovementType.choices, db_index=True)
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    movement_date = models.DateField(db_index=True)
    cleaner = models.ForeignKey(
        Cleaner, on_delete=models.SET_NULL, null=True, blank=True, related_name="stock_movements"
    )
    area = models.ForeignKey(SiteArea, on_delete=models.SET_NULL, null=True, blank=True, related_name="stock_movements")
    notes = models.TextField(blank=True, default="")
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="recorded_stock_movements",
    )

    class Meta:
        verbose_name = "Stock movement"
        verbose_name_plural = "Stock movements"
        ordering = ["-movement_date", "-created_at"]
        indexes = [models.Index(fields=["store_item", "movement_date"])]

    def __str__(self) -> str:
        return f"{self.movement_type} {self.quantity} {self.store_item.item_name} ({self.movement_date})"

    @property
    def absolute_quantity(self) -> Any:
        return abs(self.quantity)

    def clean(self) -> None:
        super().clean()
        if self.quantity == 0:
            raise ValidationError("Movement quantity cannot be zero.", code="zero_quantity")
        if self.movement_type != StockMovementType.ADJUSTMENT and self.quantity < 0:
            raise ValidationError("Only ADJUSTMENT movements may carry a negative quantity.", code="negative_magnitude")
        if self.cleaner_id and self.cleaner is not None:
            assigned = self.cleaner.site_assignments.filter(site_id=self.store_item.store.site_id).exists()
            if not assigned:
                raise ValidationError(
                    "Cleaner must be assigned to the item's store site.", code="cleaner_site_mismatch"
                )
        if self.area_id and self.area is not None and self.area.site_id != self.store_item.store.site_id:
            raise ValidationError("Area must belong to the item's store site.", code="area_site_mismatch")


class StockRequestStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    SUBMITTED = "submitted", "Submitted"
    ZONE_REVIEWED = "zone_reviewed", "Zone Reviewed"
    OFFICE_PROCESSED = "office_processed", "Office Processed"
    COMPLETED = "completed", "Completed"
    REJECTED = "rejected", "Rejected"


class StockRequest(UserStampedModel):
    """A request for stock, prepared at a site and consumed by office management.

    The lifecycle (DRAFT → SUBMITTED → ZONE_REVIEWED → OFFICE_PROCESSED →
    COMPLETED/REJECTED) hands off to the future Office Management module; on
    completion approved quantities are issued against the store.
    """

    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name="stock_requests")
    store = models.ForeignKey(SiteStore, on_delete=models.CASCADE, related_name="requests")
    request_date = models.DateField(db_index=True)
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="stock_requests",
    )
    status = models.CharField(
        max_length=20,
        choices=StockRequestStatus.choices,
        default=StockRequestStatus.DRAFT,
        db_index=True,
    )
    notes = models.TextField(blank=True, default="")
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_stock_requests",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Stock request"
        verbose_name_plural = "Stock requests"
        ordering = ["-request_date", "-created_at"]
        indexes = [
            models.Index(fields=["site", "status"]),
            models.Index(fields=["store", "status"]),
        ]

    def __str__(self) -> str:
        return f"Request {self.pk} @ {self.store} ({self.status})"

    def clean(self) -> None:
        super().clean()
        if self.store.site_id != self.site_id:
            raise ValidationError("Store must belong to the request's site.", code="store_site_mismatch")


class StockRequestItem(TimeStampedModel):
    """A requested item within a stock request, with optional approved quantity."""

    request = models.ForeignKey(StockRequest, on_delete=models.CASCADE, related_name="items")
    store_item = models.ForeignKey(StoreItem, on_delete=models.CASCADE, related_name="stock_request_items")
    requested_quantity = models.DecimalField(max_digits=10, decimal_places=2)
    approved_quantity = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    notes = models.TextField(blank=True, default="")

    class Meta:
        verbose_name = "Stock request item"
        verbose_name_plural = "Stock request items"
        ordering = ["request", "store_item__item_name"]

    def __str__(self) -> str:
        return f"{self.requested_quantity} x {self.store_item.item_name} (request {self.request_id})"

    def clean(self) -> None:
        super().clean()
        if self.requested_quantity <= 0:
            raise ValidationError("Requested quantity must be positive.", code="requested_quantity_invalid")
        if self.store_item.store_id != self.request.store_id:
            raise ValidationError("Item must belong to the request's store.", code="item_store_mismatch")
        if self.approved_quantity is not None and self.approved_quantity < 0:
            raise ValidationError("Approved quantity cannot be negative.", code="approved_quantity_invalid")


# --------------------------------------------------------------------------- #
# Inspections
# --------------------------------------------------------------------------- #


class InspectionFrequency(models.TextChoices):
    DAILY = "daily", "Daily"
    WEEKLY = "weekly", "Weekly"
    MONTHLY = "monthly", "Monthly"
    MANUAL = "manual", "Manual"


class InspectionItemType(models.TextChoices):
    YES_NO = "yes_no", "Yes/No"
    PASS_FAIL = "pass_fail", "Pass/Fail"
    SCORE = "score", "Score"
    TEXT = "text", "Text"
    PHOTO = "photo", "Photo"


class InspectionOverallStatus(models.TextChoices):
    PASSED = "passed", "Passed"
    FAILED = "failed", "Failed"
    NEEDS_ATTENTION = "needs_attention", "Needs Attention"


class InspectionWorkflowStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    SUBMITTED = "submitted", "Submitted"
    REVIEWED = "reviewed", "Reviewed"
    RETURNED = "returned", "Returned"


class InspectionTemplate(UserStampedModel, ActivatableModel):
    """A reusable checklist of inspection items.

    Global templates (``site IS NULL``) apply to every site; site-specific
    templates are scoped to one site. Templates are deactivated, never deleted,
    once inspections exist.
    """

    template_name = models.CharField(max_length=160)
    description = models.TextField(blank=True, default="")
    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name="inspection_templates", null=True, blank=True)
    area = models.ForeignKey(
        SiteArea, on_delete=models.CASCADE, related_name="inspection_templates", null=True, blank=True
    )
    frequency = models.CharField(
        max_length=16, choices=InspectionFrequency.choices, default=InspectionFrequency.MANUAL, db_index=True
    )

    class Meta:
        verbose_name = "Inspection template"
        verbose_name_plural = "Inspection templates"
        ordering = ["template_name"]
        indexes = [models.Index(fields=["site", "is_active"])]

    def __str__(self) -> str:
        site = self.site
        scope = f" @ {site.name}" if site is not None else " (global)"
        return f"{self.template_name}{scope}"

    @property
    def item_count(self) -> int:
        return self.items.count()

    @property
    def has_operational_history(self) -> bool:
        return self.inspections.exists()

    def clean(self) -> None:
        super().clean()
        if self.area_id and self.area is not None and self.area.site_id != self.site_id:
            raise ValidationError("Area must belong to the template's site.", code="area_site_mismatch")


class InspectionTemplateItem(TimeStampedModel):
    """A checklist row within an inspection template."""

    template = models.ForeignKey(InspectionTemplate, on_delete=models.CASCADE, related_name="items")
    item_label = models.CharField(max_length=255)
    item_type = models.CharField(max_length=16, choices=InspectionItemType.choices, db_index=True)
    required = models.BooleanField(default=True)
    sequence = models.PositiveSmallIntegerField(default=0)
    help_text = models.CharField(max_length=255, blank=True, default="")

    class Meta:
        verbose_name = "Inspection template item"
        verbose_name_plural = "Inspection template items"
        ordering = ["template", "sequence"]
        constraints = [
            models.UniqueConstraint(fields=["template", "sequence"], name="uniq_template_item_sequence"),
        ]

    def __str__(self) -> str:
        return f"{self.template.template_name}: {self.item_label}"


class Inspection(UserStampedModel):
    """A performed inspection of a site area using a template."""

    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name="inspections")
    area = models.ForeignKey(SiteArea, on_delete=models.CASCADE, related_name="inspections")
    template = models.ForeignKey(InspectionTemplate, on_delete=models.PROTECT, related_name="inspections")
    inspection_date = models.DateField(db_index=True)
    shift = models.ForeignKey(SiteShift, on_delete=models.SET_NULL, null=True, blank=True, related_name="inspections")
    inspected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="inspected_site_inspections",
    )
    overall_status = models.CharField(
        max_length=20, choices=InspectionOverallStatus.choices, blank=True, default="", db_index=True
    )
    score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    notes = models.TextField(blank=True, default="")
    status = models.CharField(
        max_length=16,
        choices=InspectionWorkflowStatus.choices,
        default=InspectionWorkflowStatus.DRAFT,
        db_index=True,
    )
    submitted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Inspection"
        verbose_name_plural = "Inspections"
        ordering = ["-inspection_date", "-created_at"]
        indexes = [
            models.Index(fields=["site", "status"]),
            models.Index(fields=["area", "inspection_date"]),
            models.Index(fields=["template", "inspection_date"]),
        ]

    def __str__(self) -> str:
        return f"Inspection {self.pk} @ {self.site.name} ({self.inspection_date})"

    @property
    def is_editable(self) -> bool:
        return self.status in {InspectionWorkflowStatus.DRAFT, InspectionWorkflowStatus.RETURNED}

    def clean(self) -> None:
        super().clean()
        if self.area.site_id != self.site_id:
            raise ValidationError("Area must belong to the inspection's site.", code="area_site_mismatch")
        if self.template.site_id and self.template.site_id != self.site_id:
            raise ValidationError(
                "Template must be global or scoped to the inspection's site.", code="template_site_mismatch"
            )
        if self.shift_id and self.shift is not None and self.shift.site_id != self.site_id:
            raise ValidationError("Shift must belong to the inspection's site.", code="shift_site_mismatch")


class InspectionResult(PrivateFileModel):
    """The answer to one template item within an inspection.

    ``file`` (from :class:`apps.core.models.PrivateFileModel`) is the private
    photo for PHOTO items; it is stored on the private backend and only served
    through signed download tokens.
    """

    inspection = models.ForeignKey(Inspection, on_delete=models.CASCADE, related_name="results")
    template_item = models.ForeignKey(InspectionTemplateItem, on_delete=models.CASCADE, related_name="results")
    value_text = models.TextField(blank=True, default="")
    value_number = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    value_boolean = models.BooleanField(null=True, blank=True)
    passed = models.BooleanField(null=True, blank=True)
    notes = models.TextField(blank=True, default="")

    class Meta:
        verbose_name = "Inspection result"
        verbose_name_plural = "Inspection results"
        ordering = ["template_item__sequence"]
        constraints = [
            models.UniqueConstraint(fields=["inspection", "template_item"], name="uniq_inspection_template_item"),
        ]

    def __str__(self) -> str:
        return f"{self.inspection_id} / {self.template_item.item_label}"

    def clean(self) -> None:
        super().clean()
        if self.template_item.template_id != self.inspection.template_id:
            raise ValidationError(
                "Template item must belong to the inspection's template.", code="item_template_mismatch"
            )
        item_type = self.template_item.item_type
        if item_type == InspectionItemType.YES_NO:
            if self.value_boolean is None:
                raise ValidationError("Yes/No items require a boolean answer.", code="boolean_required")
            self.passed = self.value_boolean
        elif item_type == InspectionItemType.PASS_FAIL:
            if self.passed is None:
                raise ValidationError("Pass/Fail items require a pass/fail answer.", code="pass_fail_required")
            self.value_boolean = self.passed
        elif item_type == InspectionItemType.SCORE:
            if self.value_number is None:
                raise ValidationError("Score items require a numeric value.", code="score_required")
            if not 0 <= self.value_number <= 100:
                raise ValidationError("Score must be between 0 and 100.", code="score_out_of_range")
            self.passed = self.value_number >= 50
        elif item_type == InspectionItemType.TEXT:
            if not self.value_text.strip():
                raise ValidationError("Text items require a text answer.", code="text_required")
