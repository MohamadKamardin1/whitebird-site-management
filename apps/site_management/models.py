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

from constance import config
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from apps.core.managers import SoftDeleteManager
from apps.core.models import ActivatableModel, TimeStampedModel, UserStampedModel

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
