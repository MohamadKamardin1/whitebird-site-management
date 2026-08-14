"""Model-aware validation for site configuration.

These validators load domain models and enforce cross-entity rules that the
field validators cannot express. They raise ``ValidationError`` so both the
admin and the API (which maps ``ValidationError`` → 422) can surface them.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.core.exceptions import ValidationError

if TYPE_CHECKING:
    from .models import Site, SiteArea, SiteShift

from .models import WorkMode


def validate_shift_belongs_to_site(site: Site, shift: SiteShift) -> None:
    """Ensure a shift belongs to the given site."""
    if shift.site_id != site.pk:
        raise ValidationError(f"Shift '{shift.shift_name}' does not belong to site '{site.name}'.")


def validate_area_belongs_to_site(site: Site, area: SiteArea) -> None:
    """Ensure an area belongs to the given site."""
    if area.site_id != site.pk:
        raise ValidationError(f"Area '{area.area_name}' does not belong to site '{site.name}'.")


def validate_site_work_mode(site: Site) -> None:
    """Validate that the site's shift configuration matches its work mode.

    * ``FULL_TIME`` sites cannot have active shifts (no shift-based staffing).
    * ``SHIFT`` sites must have at least one active shift before shift
      staffing can be configured.
    * ``FULL_TIME_AND_SHIFT`` allows both.
    """
    active_shifts = site.shifts.filter(is_active=True)
    if site.work_mode == WorkMode.FULL_TIME and active_shifts.exists():
        raise ValidationError(
            f"A FULL_TIME site ({site.name}) cannot have active shifts. Change the work mode or deactivate the shifts.",
            code="work_mode_conflict",
        )
    if site.work_mode == WorkMode.SHIFT and not active_shifts.exists():
        raise ValidationError(
            f"A SHIFT site ({site.name}) must have at least one active shift before shift staffing.",
            code="work_mode_conflict",
        )


def validate_site_configuration_consistency(site: Site) -> None:
    """Run all site-level configuration validators, including duplicate shifts."""
    validate_site_work_mode(site)

    overlapping = _find_duplicate_shifts(site)
    if overlapping:
        names = ", ".join(f"'{name}'" for name in overlapping)
        raise ValidationError(f"Site '{site.name}' has overlapping duplicate shifts: {names}.", code="duplicate_shifts")


def _find_duplicate_shifts(site: Site) -> list[str]:
    """Detect active shifts with identical times + effective days."""
    seen: dict[tuple[object, object, str], str] = {}
    duplicates: list[str] = []
    for shift in site.shifts.filter(is_active=True):
        key = (shift.start_time, shift.end_time, ",".join(sorted(shift.effective_days)))
        existing = seen.get(key)
        if existing is not None:
            duplicates.append(shift.shift_name)
        else:
            seen[key] = shift.shift_name
    return duplicates
