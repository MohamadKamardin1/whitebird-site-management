"""Site service layer — transactional writes, audit, cache invalidation.

No business logic lives in routers or models; every mutation is a function
here that: validates, mutates inside a transaction, writes an audit entry,
invalidates affected caches and schedules asynchronous side effects.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, time
from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from apps.accounts.models import RoleCode, User
from apps.core.cache import invalidate_prefix
from apps.core.models import AuditLog
from apps.core.services import model_data, record_audit

from .models import (
    Asset,
    AssetCategory,
    AssignmentRole,
    AssistantGeneralSupervisorAssignment,
    Department,
    Notification,
    OperationalRole,
    Site,
    SiteArea,
    SiteShift,
    SiteStatus,
    SiteSupervisorAssignment,
    SiteType,
    StaffAssignment,
    WorkMode,
    Zone,
    ZoneSupervisorAssignment,
)
from .selectors import invalidate_site


def _unique_slug(model: Any, base: str, *, field: str = "slug") -> str:
    candidate = slugify(base) or "item"
    unique = candidate
    counter = 2
    while model.objects.filter(**{field: unique}).exists():
        unique = f"{candidate}-{counter}"
        counter += 1
    return unique


def _unique_code(base: str) -> str:
    raw = slugify(base).upper().replace("-", "")[:8] or "SITE"
    candidate = raw
    counter = 2
    while Site.objects.filter(code=candidate).exists():
        candidate = f"{raw[:7]}{counter}"
        counter += 1
    return candidate


# --------------------------------------------------------------------------- #
# Sites
# --------------------------------------------------------------------------- #


@dataclass
class SiteDraft:
    name: str
    zone: Zone | None = None
    site_type: SiteType | None = None
    status: SiteStatus | None = None
    description: str = ""
    building_name: str = ""
    location: str = ""
    address: str = ""
    city: str = ""
    region: str = ""
    country: str = "TZ"
    postal_code: str = ""
    latitude: float | None = None
    longitude: float | None = None
    capacity: int = 0
    contact_person: str = ""
    contact_email: str = ""
    contact_phone: str = ""
    work_mode: WorkMode = WorkMode.FULL_TIME
    working_days: list[str] = field(default_factory=list)
    notes: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "zone": self.zone,
            "site_type": self.site_type,
            "status": self.status,
            "description": self.description,
            "building_name": self.building_name,
            "location": self.location,
            "address": self.address,
            "city": self.city,
            "region": self.region,
            "country": self.country,
            "postal_code": self.postal_code,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "capacity": self.capacity,
            "contact_person": self.contact_person,
            "contact_email": self.contact_email,
            "contact_phone": self.contact_phone,
            "work_mode": self.work_mode,
            "working_days": self.working_days,
            "notes": self.notes,
        }


def create_site(*, draft: SiteDraft, actor: User) -> Site:
    with transaction.atomic():
        site = Site.objects.create(
            slug=_unique_slug(Site, draft.name),
            code=_unique_code(draft.name),
            created_by=actor,
            **draft.to_dict(),
        )
        record_audit(
            action=AuditLog.Action.CREATE,
            actor=actor,
            entity=site,
            summary=f"Created site {site.name}",
            after_data=model_data(site),
        )
    return site


def update_site(*, site: Site, draft: SiteDraft, actor: User) -> Site:
    with transaction.atomic():
        before = model_data(site)
        changes: dict[str, object] = {}
        for field in draft.to_dict():
            old = getattr(site, field)
            new = getattr(draft, field)
            if old != new:
                changes[field] = {"from": _serialise(old), "to": _serialise(new)}
                setattr(site, field, new)

        status_changed = "status" in changes
        previous_status_slug = None
        status_change = changes.get("status")
        if isinstance(status_change, dict):
            previous_status_slug = status_change.get("from")

        if site.work_mode == WorkMode.FULL_TIME and site.shifts.filter(is_active=True).exists():
            raise ValidationError(
                f"A FULL_TIME site ({site.name}) cannot have active shifts. "
                "Deactivate the shifts or choose another work mode.",
                code="work_mode_conflict",
            )
        site.save()

        record_audit(
            action=AuditLog.Action.UPDATE,
            actor=actor,
            entity=site,
            summary=f"Updated site {site.name}",
            before_data=before,
            after_data=model_data(site),
        )

        if status_changed:
            _on_status_changed(site=site, actor=actor, previous_status_slug=previous_status_slug)

        invalidate_site(site.pk)
    return site


def _on_status_changed(*, site: Site, actor: User, previous_status_slug: str | None) -> None:
    record_audit(
        action=AuditLog.Action.STATUS_CHANGE,
        actor=actor,
        entity=site,
        summary=(f"Status changed: {previous_status_slug or '—'} -> {site.status.slug if site.status else '—'}"),
    )
    if site.status:
        # Lazy import breaks the services <-> tasks circular dependency.
        from .tasks import notify_site_status_change  # noqa: PLC0415

        notify_site_status_change.delay(site_id=site.pk, status_slug=site.status.slug)


def archive_site(*, site: Site, actor: User) -> Site:
    with transaction.atomic():
        site.is_active = False
        site.save(update_fields=["is_active", "updated_at"])
        record_audit(
            action=AuditLog.Action.ARCHIVE,
            actor=actor,
            entity=site,
            summary=f"Archived site {site.name}",
        )
        invalidate_site(site.pk)
    return site


def restore_site(*, site: Site, actor: User) -> Site:
    with transaction.atomic():
        site.is_active = True
        site.save(update_fields=["is_active", "updated_at"])
        record_audit(
            action=AuditLog.Action.RESTORE,
            actor=actor,
            entity=site,
            summary=f"Restored site {site.name}",
        )
        invalidate_site(site.pk)
    return site


# --------------------------------------------------------------------------- #
# Departments
# --------------------------------------------------------------------------- #


def create_department(*, site: Site, name: str, description: str = "", actor: User) -> Department:
    with transaction.atomic():
        if Department.objects.filter(site=site, name__iexact=name, is_active=True).exists():
            raise ValidationError("A department with this name already exists on the site.")
        department = Department.objects.create(site=site, name=name, description=description, created_by=actor)
        record_audit(
            action=AuditLog.Action.CREATE,
            actor=actor,
            entity=department,
            summary=f"Created department {name}",
        )
        invalidate_site(site.pk)
    return department


def update_department(
    *,
    department: Department,
    name: str | None = None,
    description: str | None = None,
    actor: User,
) -> Department:
    with transaction.atomic():
        if name is not None and name.lower() != department.name.lower():
            duplicate = Department.objects.filter(site=department.site, name__iexact=name, is_active=True).exclude(
                pk=department.pk
            )
            if duplicate.exists():
                raise ValidationError("A department with this name already exists on the site.")
            department.name = name
        if description is not None:
            department.description = description
        department.save()
        record_audit(
            action=AuditLog.Action.UPDATE,
            actor=actor,
            entity=department,
            summary=f"Updated department {department.name}",
        )
        invalidate_site(department.site_id)
    return department


def deactivate_department(*, department: Department, actor: User) -> Department:
    with transaction.atomic():
        department.is_active = False
        department.save(update_fields=["is_active", "updated_at"])
        record_audit(
            action=AuditLog.Action.DELETE,
            actor=actor,
            entity=department,
            summary=f"Deactivated department {department.name}",
        )
        invalidate_site(department.site_id)
    return department


# --------------------------------------------------------------------------- #
# Assets
# --------------------------------------------------------------------------- #


def create_asset(
    *,
    site: Site,
    name: str,
    category: AssetCategory | None,
    serial_number: str = "",
    quantity: int = 1,
    condition: Asset.Condition = Asset.Condition.OPERATIONAL,
    actor: User,
) -> Asset:
    with transaction.atomic():
        asset = Asset.objects.create(
            site=site,
            category=category,
            name=name,
            serial_number=serial_number,
            quantity=quantity,
            condition=condition,
        )
        record_audit(
            action=AuditLog.Action.CREATE,
            actor=actor,
            entity=asset,
            summary=f"Created asset {name}",
        )
        invalidate_site(site.pk)
    return asset


def update_asset(
    *,
    asset: Asset,
    name: str | None = None,
    category: AssetCategory | None = None,
    serial_number: str | None = None,
    quantity: int | None = None,
    condition: Asset.Condition | None = None,
    actor: User,
) -> Asset:
    with transaction.atomic():
        if name is not None:
            asset.name = name
        if category is not None:
            asset.category = category
        if serial_number is not None:
            asset.serial_number = serial_number
        if quantity is not None:
            asset.quantity = quantity
        if condition is not None:
            asset.condition = condition
        asset.save()
        record_audit(
            action=AuditLog.Action.UPDATE,
            actor=actor,
            entity=asset,
            summary=f"Updated asset {asset.name}",
        )
        invalidate_site(asset.site_id)
    return asset


def deactivate_asset(*, asset: Asset, actor: User) -> Asset:
    with transaction.atomic():
        asset.is_active = False
        asset.save(update_fields=["is_active", "updated_at"])
        record_audit(
            action=AuditLog.Action.DELETE,
            actor=actor,
            entity=asset,
            summary=f"Retired asset {asset.name}",
        )
        invalidate_site(asset.site_id)
    return asset


# --------------------------------------------------------------------------- #
# Staff assignments
# --------------------------------------------------------------------------- #


def assign_staff(
    *,
    site: Site,
    user: User,
    role: AssignmentRole | str = AssignmentRole.STAFF,
    is_primary: bool = False,
    actor: User,
) -> StaffAssignment:
    role_value = role.value if isinstance(role, AssignmentRole) else str(role)
    role_label = dict(AssignmentRole.choices).get(role_value, role_value)
    with transaction.atomic():
        assignment, created = StaffAssignment.objects.update_or_create(
            site=site,
            user=user,
            defaults={"role": role_value, "is_primary": is_primary, "assigned_by": actor},
        )
        record_audit(
            action=AuditLog.Action.ASSIGN,
            actor=actor,
            entity=assignment,
            summary=f"{user.get_username()} assigned to {site.name} as {role_label}",
        )
        if created:
            invalidate_site(site.pk)
            # Lazy import breaks the services <-> tasks circular dependency.
            from .tasks import notify_staff_assigned  # noqa: PLC0415

            notify_staff_assigned.delay(assignment_id=assignment.pk)
    return assignment


def unassign_staff(*, assignment: StaffAssignment, actor: User) -> None:
    with transaction.atomic():
        record_audit(
            action=AuditLog.Action.UNASSIGN,
            actor=actor,
            entity=assignment,
            summary=f"{assignment.user.get_username()} unassigned from {assignment.site.name}",
        )
        assignment.delete()
        invalidate_site(assignment.site_id)


def set_primary_assignment(*, assignment: StaffAssignment, actor: User) -> StaffAssignment:
    with transaction.atomic():
        StaffAssignment.objects.filter(user=assignment.user).update(is_primary=False)
        assignment.is_primary = True
        assignment.save(update_fields=["is_primary", "updated_at"])
        record_audit(
            action=AuditLog.Action.UPDATE,
            actor=actor,
            entity=assignment,
            summary=f"Primary site set to {assignment.site.name}",
        )
    return assignment


# --------------------------------------------------------------------------- #
# Notifications
# --------------------------------------------------------------------------- #


def create_notification(
    *,
    recipient: User,
    title: str,
    body: str = "",
    entity_type: str = "",
    entity_id: str = "",
) -> Notification:
    """Backward-compatible thin wrapper over :func:`notify`."""
    return notify(
        recipient=recipient, verb=entity_type, title=title, body=body, object_type=entity_type, object_id=entity_id
    )


def notify(
    *,
    recipient: User,
    verb: str,
    title: str | None = None,
    body: str = "",
    actor: User | None = None,
    object_type: str = "",
    object_id: str | int = "",
    link: str = "",
    dedup_key: str = "",
) -> Notification:
    """Create an in-platform notification with optional deduplication.

    When ``dedup_key`` is set, an existing *unread* notification with the same
    key for the recipient is left untouched (repeated alerts coalesce).
    """
    if dedup_key and Notification.objects.filter(recipient=recipient, dedup_key=dedup_key, is_read=False).exists():
        return Notification.objects.filter(recipient=recipient, dedup_key=dedup_key, is_read=False).first()  # type: ignore[return-value]
    return Notification.objects.create(
        recipient=recipient,
        actor=actor,
        verb=verb,
        title=title or verb.replace("_", " ").title(),
        body=body,
        object_type=object_type,
        object_id=str(object_id) if object_id else "",
        link=link,
        dedup_key=dedup_key,
    )


def notify_role(
    *,
    role: RoleCode,
    verb: str,
    object_type: str = "",
    object_id: str | int = "",
    link: str = "",
    body: str = "",
    title: str | None = None,
    dedup_key: str = "",
) -> int:
    """Notify every active user holding ``role``; returns the count created."""
    from django.db.models import Q

    recipients = User.objects.filter(is_active=True).filter(Q(role=role) | Q(is_superuser=True))
    created = 0
    for recipient in recipients:
        notify(
            recipient=recipient,
            verb=verb,
            title=title,
            body=body,
            object_type=object_type,
            object_id=object_id,
            link=link,
            dedup_key=dedup_key,
        )
        created += 1
    return created


def mark_notifications_read(*, user: User, notification_ids: list[int]) -> int:
    now = timezone.now()
    return Notification.objects.filter(recipient=user, pk__in=notification_ids, is_read=False).update(
        is_read=True, read_at=now
    )


def mark_all_notifications_read(*, user: User) -> int:
    now = timezone.now()
    return Notification.objects.filter(recipient=user, is_read=False).update(is_read=True, read_at=now)


# --------------------------------------------------------------------------- #
# Access helpers
# --------------------------------------------------------------------------- #


def scoped_site_ids(user: User) -> list[int]:
    """Site ids a non-admin user may manage, all sites for admins."""
    if user.is_system_admin:
        return list(Site.objects.filter(is_active=True).values_list("pk", flat=True))
    return list(user.staff_assignments.filter(site__is_active=True).values_list("site_id", flat=True))


def _serialise(value: object) -> object:
    if hasattr(value, "pk"):
        return value.pk
    if hasattr(value, "slug"):
        return value.slug
    return value


# --------------------------------------------------------------------------- #
# Zones
# --------------------------------------------------------------------------- #


def _unique_zone_code(base: str, *, length: int = 8) -> str:
    raw = slugify(base).upper().replace("-", "")[: length - 2] or "ZONE"
    candidate = raw
    counter = 2
    while Zone.objects.filter(code=candidate).exists():
        candidate = f"{raw[: length - 1]}{counter}"
        counter += 1
    return candidate


def create_zone(*, name: str, description: str = "", actor: User) -> Zone:
    with transaction.atomic():
        zone = Zone.objects.create(
            name=name,
            code=_unique_zone_code(name),
            description=description,
            created_by=actor,
            updated_by=actor,
        )
        record_audit(
            action=AuditLog.Action.CREATE,
            actor=actor,
            entity=zone,
            summary=f"Created zone {zone.name}",
            after_data=model_data(zone),
        )
    return zone


def update_zone(*, zone: Zone, name: str | None = None, description: str | None = None, actor: User) -> Zone:
    with transaction.atomic():
        before = model_data(zone)
        if name is not None and name != zone.name:
            zone.name = name
        if description is not None:
            zone.description = description
        zone.updated_by = actor
        zone.save(update_fields=["name", "description", "updated_by", "updated_at"])
        record_audit(
            action=AuditLog.Action.UPDATE,
            actor=actor,
            entity=zone,
            summary=f"Updated zone {zone.name}",
            before_data=before,
            after_data=model_data(zone),
        )
        invalidate_prefix("site:detail")
        invalidate_prefix("site:stats")
    return zone


def deactivate_zone(*, zone: Zone, actor: User) -> Zone:
    with transaction.atomic():
        zone.is_active = False
        zone.updated_by = actor
        zone.save(update_fields=["is_active", "updated_by", "updated_at"])
        record_audit(
            action=AuditLog.Action.ARCHIVE,
            actor=actor,
            entity=zone,
            summary=f"Deactivated zone {zone.name}",
            before_data=model_data(zone),
        )
        invalidate_prefix("site:detail")
        invalidate_prefix("site:stats")
    return zone


def restore_zone(*, zone: Zone, actor: User) -> Zone:
    with transaction.atomic():
        zone.is_active = True
        zone.updated_by = actor
        zone.save(update_fields=["is_active", "updated_by", "updated_at"])
        record_audit(
            action=AuditLog.Action.RESTORE,
            actor=actor,
            entity=zone,
            summary=f"Restored zone {zone.name}",
        )
        invalidate_prefix("site:detail")
        invalidate_prefix("site:stats")
    return zone


# --------------------------------------------------------------------------- #
# Supervisor assignments
# --------------------------------------------------------------------------- #


def assign_site_supervisor(
    *,
    site: Site,
    user: User,
    assigned_from: date,
    assigned_to: date | None = None,
    is_primary: bool = False,
    actor: User,
) -> SiteSupervisorAssignment:
    with transaction.atomic():
        assignment = SiteSupervisorAssignment(
            site=site,
            user=user,
            assigned_from=assigned_from,
            assigned_to=assigned_to,
            is_primary=is_primary,
            is_active=True,
            created_by=actor,
            updated_by=actor,
        )
        assignment.full_clean()
        if is_primary:
            SiteSupervisorAssignment.objects.filter(site=site, is_active=True).exclude(pk=assignment.pk).update(
                is_primary=False
            )
        assignment.save()
        record_audit(
            action=AuditLog.Action.ASSIGN,
            actor=actor,
            entity=assignment,
            summary=f"{user.email} assigned as supervisor of {site.name}",
            after_data=model_data(assignment),
        )
        invalidate_site(site.pk)
    return assignment


def end_site_supervisor_assignment(*, assignment: SiteSupervisorAssignment, actor: User) -> SiteSupervisorAssignment:
    with transaction.atomic():
        assignment.is_active = False
        assignment.updated_by = actor
        assignment.save(update_fields=["is_active", "updated_by", "updated_at"])
        record_audit(
            action=AuditLog.Action.UNASSIGN,
            actor=actor,
            entity=assignment,
            summary=f"Ended supervisor assignment for {assignment.user.email} at {assignment.site.name}",
            before_data=model_data(assignment),
        )
        invalidate_site(assignment.site_id)
    return assignment


def assign_zone_supervisor(
    *,
    zone: Zone,
    user: User,
    assigned_from: date,
    assigned_to: date | None = None,
    actor: User,
) -> ZoneSupervisorAssignment:
    with transaction.atomic():
        assignment = ZoneSupervisorAssignment(
            zone=zone,
            user=user,
            assigned_from=assigned_from,
            assigned_to=assigned_to,
            is_active=True,
            created_by=actor,
            updated_by=actor,
        )
        assignment.full_clean()
        assignment.save()
        record_audit(
            action=AuditLog.Action.ASSIGN,
            actor=actor,
            entity=assignment,
            summary=f"{user.email} assigned as supervisor of zone {zone.name}",
            after_data=model_data(assignment),
        )
    return assignment


def end_zone_supervisor_assignment(*, assignment: ZoneSupervisorAssignment, actor: User) -> ZoneSupervisorAssignment:
    with transaction.atomic():
        assignment.is_active = False
        assignment.updated_by = actor
        assignment.save(update_fields=["is_active", "updated_by", "updated_at"])
        record_audit(
            action=AuditLog.Action.UNASSIGN,
            actor=actor,
            entity=assignment,
            summary=f"Ended zone supervisor assignment for {assignment.user.email} in {assignment.zone.name}",
            before_data=model_data(assignment),
        )
    return assignment


def assign_assistant_general_supervisor(
    *,
    user: User,
    all_zones: bool,
    zone: Zone | None = None,
    assigned_from: date,
    assigned_to: date | None = None,
    actor: User,
) -> AssistantGeneralSupervisorAssignment:
    with transaction.atomic():
        assignment = AssistantGeneralSupervisorAssignment(
            user=user,
            all_zones=all_zones,
            zone=zone,
            assigned_from=assigned_from,
            assigned_to=assigned_to,
            is_active=True,
            created_by=actor,
            updated_by=actor,
        )
        assignment.full_clean()
        assignment.save()
        record_audit(
            action=AuditLog.Action.ASSIGN,
            actor=actor,
            entity=assignment,
            summary=f"{user.email} assigned as assistant general supervisor",
            after_data=model_data(assignment),
        )
    return assignment


def end_assistant_general_supervisor_assignment(
    *, assignment: AssistantGeneralSupervisorAssignment, actor: User
) -> AssistantGeneralSupervisorAssignment:
    with transaction.atomic():
        assignment.is_active = False
        assignment.updated_by = actor
        assignment.save(update_fields=["is_active", "updated_by", "updated_at"])
        record_audit(
            action=AuditLog.Action.UNASSIGN,
            actor=actor,
            entity=assignment,
            summary=f"Ended assistant general supervisor assignment for {assignment.user.email}",
            before_data=model_data(assignment),
        )
    return assignment


# --------------------------------------------------------------------------- #
# Site configuration: shifts, areas, operational roles
# --------------------------------------------------------------------------- #


def _validate_shift_work_mode(site: Site, active_after: int) -> None:
    """Validate a site's shift count against its work mode.

    * ``FULL_TIME`` sites cannot have any active shifts.
    * ``SHIFT`` sites must keep at least one active shift (shift staffing).
    """
    if site.work_mode == WorkMode.FULL_TIME and active_after > 0:
        raise ValidationError(
            f"A FULL_TIME site ({site.name}) cannot have active shifts. Change the work mode or deactivate shifts.",
            code="work_mode_conflict",
        )
    if site.work_mode == WorkMode.SHIFT and active_after == 0:
        raise ValidationError(
            f"A SHIFT site ({site.name}) must have at least one active shift before shift staffing.",
            code="work_mode_conflict",
        )


def create_shift(
    *,
    site: Site,
    shift_name: str,
    start_time: time,
    end_time: time,
    effective_days: list[str],
    shift_code: str = "",
    sequence: int = 0,
    description: str = "",
    actor: User,
) -> SiteShift:
    """Create a manually configured shift for a site."""
    with transaction.atomic():
        shift = SiteShift(
            site=site,
            shift_name=shift_name,
            shift_code=shift_code,
            start_time=start_time,
            end_time=end_time,
            effective_days=effective_days,
            sequence=sequence,
            description=description,
            is_active=True,
            created_by=actor,
            updated_by=actor,
        )
        shift.full_clean()
        _validate_shift_work_mode(site, active_after=1)
        shift.save()
        record_audit(
            action=AuditLog.Action.CREATE,
            actor=actor,
            entity=shift,
            summary=f"Created shift {shift_name} for {site.name}",
            after_data=model_data(shift),
        )
        invalidate_site(site.pk)
    return shift


def update_shift(
    *,
    shift: SiteShift,
    actor: User,
    shift_name: str | None = None,
    shift_code: str | None = None,
    start_time: time | None = None,
    end_time: time | None = None,
    effective_days: list[str] | None = None,
    sequence: int | None = None,
    description: str | None = None,
) -> SiteShift:
    """Update a site shift and re-validate its configuration."""
    with transaction.atomic():
        before = model_data(shift)
        if shift_name is not None:
            shift.shift_name = shift_name
        if shift_code is not None:
            shift.shift_code = shift_code
        if start_time is not None:
            shift.start_time = start_time
        if end_time is not None:
            shift.end_time = end_time
        if effective_days is not None:
            shift.effective_days = effective_days
        if sequence is not None:
            shift.sequence = sequence
        if description is not None:
            shift.description = description
        shift.updated_by = actor
        shift.full_clean()
        active_count = shift.site.shifts.filter(is_active=True).count()
        _validate_shift_work_mode(shift.site, active_after=active_count)
        shift.save()
        record_audit(
            action=AuditLog.Action.UPDATE,
            actor=actor,
            entity=shift,
            summary=f"Updated shift {shift.shift_name}",
            before_data=before,
            after_data=model_data(shift),
        )
        invalidate_site(shift.site_id)
    return shift


def deactivate_shift(*, shift: SiteShift, actor: User) -> SiteShift:
    """Deactivate a shift; refuse when it has operational usage."""
    with transaction.atomic():
        if shift.has_operational_usage:
            raise ValidationError("This shift is in use and cannot be deactivated.")
        remaining = shift.site.shifts.filter(is_active=True).exclude(pk=shift.pk).count()
        _validate_shift_work_mode(shift.site, active_after=remaining)
        shift.is_active = False
        shift.updated_by = actor
        shift.save(update_fields=["is_active", "updated_by", "updated_at"])
        record_audit(
            action=AuditLog.Action.ARCHIVE,
            actor=actor,
            entity=shift,
            summary=f"Deactivated shift {shift.shift_name}",
            before_data=model_data(shift),
        )
        invalidate_site(shift.site_id)
    return shift


def create_area(
    *,
    site: Site,
    area_name: str,
    area_code: str = "",
    floor: str = "",
    description: str = "",
    actor: User,
) -> SiteArea:
    """Create an area within a site."""
    with transaction.atomic():
        area = SiteArea(
            site=site,
            area_name=area_name,
            area_code=area_code,
            floor=floor,
            description=description,
            is_active=True,
            created_by=actor,
            updated_by=actor,
        )
        area.full_clean()
        area.save()
        record_audit(
            action=AuditLog.Action.CREATE,
            actor=actor,
            entity=area,
            summary=f"Created area {area_name} for {site.name}",
            after_data=model_data(area),
        )
        invalidate_site(site.pk)
    return area


def update_area(
    *,
    area: SiteArea,
    actor: User,
    area_name: str | None = None,
    area_code: str | None = None,
    floor: str | None = None,
    description: str | None = None,
) -> SiteArea:
    """Update a site area."""
    with transaction.atomic():
        before = model_data(area)
        if area_name is not None:
            area.area_name = area_name
        if area_code is not None:
            area.area_code = area_code
        if floor is not None:
            area.floor = floor
        if description is not None:
            area.description = description
        area.updated_by = actor
        area.full_clean()
        area.save()
        record_audit(
            action=AuditLog.Action.UPDATE,
            actor=actor,
            entity=area,
            summary=f"Updated area {area.area_name}",
            before_data=before,
            after_data=model_data(area),
        )
        invalidate_site(area.site_id)
    return area


def deactivate_area(*, area: SiteArea, actor: User) -> SiteArea:
    """Deactivate an area; refuse when schedules/inspections exist."""
    with transaction.atomic():
        if area.has_operational_usage:
            raise ValidationError("This area is in use and cannot be deactivated.")
        area.is_active = False
        area.updated_by = actor
        area.save(update_fields=["is_active", "updated_by", "updated_at"])
        record_audit(
            action=AuditLog.Action.ARCHIVE,
            actor=actor,
            entity=area,
            summary=f"Deactivated area {area.area_name}",
            before_data=model_data(area),
        )
        invalidate_site(area.site_id)
    return area


def create_operational_role(*, name: str, code: str, description: str = "", actor: User) -> OperationalRole:
    """Create a globally configurable operational role."""
    with transaction.atomic():
        role = OperationalRole(
            name=name,
            code=code,
            description=description,
            is_active=True,
            created_by=actor,
            updated_by=actor,
        )
        role.full_clean()
        role.save()
        record_audit(
            action=AuditLog.Action.CREATE,
            actor=actor,
            entity=role,
            summary=f"Created operational role {name}",
            after_data=model_data(role),
        )
    return role


def update_operational_role(
    *,
    role: OperationalRole,
    actor: User,
    name: str | None = None,
    code: str | None = None,
    description: str | None = None,
) -> OperationalRole:
    """Update an operational role."""
    with transaction.atomic():
        before = model_data(role)
        if name is not None:
            role.name = name
        if code is not None:
            role.code = code
        if description is not None:
            role.description = description
        role.updated_by = actor
        role.full_clean()
        role.save()
        record_audit(
            action=AuditLog.Action.UPDATE,
            actor=actor,
            entity=role,
            summary=f"Updated operational role {role.name}",
            before_data=before,
            after_data=model_data(role),
        )
    return role


def deactivate_operational_role(*, role: OperationalRole, actor: User) -> OperationalRole:
    """Deactivate an operational role; refuse when used in assignments."""
    with transaction.atomic():
        if role.has_operational_usage:
            raise ValidationError("This operational role is in use and cannot be deactivated.")
        role.is_active = False
        role.updated_by = actor
        role.save(update_fields=["is_active", "updated_by", "updated_at"])
        record_audit(
            action=AuditLog.Action.ARCHIVE,
            actor=actor,
            entity=role,
            summary=f"Deactivated operational role {role.name}",
            before_data=model_data(role),
        )
    return role
