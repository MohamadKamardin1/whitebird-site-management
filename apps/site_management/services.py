"""Site service layer — transactional writes, audit, cache invalidation.

No business logic lives in routers or models; every mutation is a function
here that: validates, mutates inside a transaction, writes an audit entry,
invalidates affected caches and schedules asynchronous side effects.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.text import slugify

from apps.accounts.models import User
from apps.core.models import AuditLog
from apps.core.services import record_audit

from .models import (
    Asset,
    AssetCategory,
    AssignmentRole,
    Department,
    Notification,
    Site,
    SiteStatus,
    SiteType,
    StaffAssignment,
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
    site_type: SiteType | None = None
    status: SiteStatus | None = None
    description: str = ""
    address: str = ""
    city: str = ""
    region: str = ""
    country: str = "TZ"
    postal_code: str = ""
    latitude: float | None = None
    longitude: float | None = None
    capacity: int = 0
    contact_email: str = ""
    contact_phone: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "site_type": self.site_type,
            "status": self.status,
            "description": self.description,
            "address": self.address,
            "city": self.city,
            "region": self.region,
            "country": self.country,
            "postal_code": self.postal_code,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "capacity": self.capacity,
            "contact_email": self.contact_email,
            "contact_phone": self.contact_phone,
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
        )
    return site


def update_site(*, site: Site, draft: SiteDraft, actor: User) -> Site:
    with transaction.atomic():
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
        site.save()

        record_audit(
            action=AuditLog.Action.UPDATE,
            actor=actor,
            entity=site,
            summary=f"Updated site {site.name}",
            changes=changes,
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
    return Notification.objects.create(
        recipient=recipient,
        title=title,
        body=body,
        entity_type=entity_type,
        entity_id=entity_id,
    )


def mark_notifications_read(*, user: User, notification_ids: list[int]) -> int:
    return Notification.objects.filter(recipient=user, pk__in=notification_ids, is_read=False).update(is_read=True)


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
