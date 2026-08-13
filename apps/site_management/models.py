"""Site management domain models.

Design notes
------------
* Site *types*, *statuses* and *asset categories* are configuration rows the
  admin team maintains — never hardcoded business values.
* Sites are soft-deleted (``is_active``) so historical reporting and audit
  trails survive an archive.
* Assignment roles are code-level (permission-relevant), see
  :class:`AssignmentRole`.
"""

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.core.managers import SoftDeleteManager
from apps.core.models import TimeStampedModel


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


class Site(TimeStampedModel):
    """A physical site (property/location) under management."""

    name = models.CharField(max_length=160)
    slug = models.SlugField(max_length=160, unique=True)
    code = models.CharField(max_length=12, unique=True, db_index=True)
    site_type = models.ForeignKey(SiteType, on_delete=models.PROTECT, related_name="sites", null=True, blank=True)
    status = models.ForeignKey(SiteStatus, on_delete=models.PROTECT, related_name="sites", null=True, blank=True)
    description = models.TextField(blank=True, default="")
    address = models.CharField(max_length=255, blank=True, default="")
    city = models.CharField(max_length=120, blank=True, default="")
    region = models.CharField(max_length=120, blank=True, default="")
    country = models.CharField(max_length=2, default="TZ")
    postal_code = models.CharField(max_length=20, blank=True, default="")
    latitude = models.FloatField(null=True, blank=True, validators=[MinValueValidator(-90), MaxValueValidator(90)])
    longitude = models.FloatField(null=True, blank=True, validators=[MinValueValidator(-180), MaxValueValidator(180)])
    capacity = models.PositiveIntegerField(default=0, help_text="Maximum concurrent guests.")
    contact_email = models.EmailField(blank=True, default="")
    contact_phone = models.CharField(max_length=32, blank=True, default="")
    is_active = models.BooleanField(default=True, db_index=True, help_text="Soft-delete flag.")
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
        ]

    def __str__(self) -> str:
        return self.name

    @property
    def department_count(self) -> int:
        return self.departments.count()

    @property
    def asset_count(self) -> int:
        return self.assets.count()

    @property
    def staff_count(self) -> int:
        return self.staff_assignments.count()


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
