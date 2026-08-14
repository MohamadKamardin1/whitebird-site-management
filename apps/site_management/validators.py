"""Domain value validators for the site management app.

These validate plain values (day codes, shift times). Model-aware validators
that import domain models live in ``apps/site_management/validation.py``.
"""

from __future__ import annotations

from datetime import time
from typing import Any

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

#: Valid ISO weekday codes used by ``Site.working_days`` and ``SiteShift.effective_days``.
WORKING_DAYS: tuple[str, ...] = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


def validate_day_codes(value: Any, *, field: str = "working_days", allow_empty: bool = True) -> None:
    """Validate a list of weekday codes (portable ArrayField equivalent)."""
    if not isinstance(value, list):
        raise ValidationError(_("%(field)s must be a list of day codes.") % {"field": field}, code="invalid_days")
    invalid = sorted(set(value) - set(WORKING_DAYS))
    if invalid:
        raise ValidationError(
            _("Invalid days: %(days)s. Allowed: %(allowed)s.")
            % {"days": ", ".join(invalid), "allowed": ", ".join(WORKING_DAYS)},
            code="invalid_days",
        )
    if not allow_empty and not value:
        raise ValidationError(_("%(field)s must include at least one day.") % {"field": field}, code="invalid_days")


def validate_working_days(value: Any) -> None:
    """Validate the ``Site.working_days`` field (empty allowed)."""
    validate_day_codes(value, field="working_days", allow_empty=True)


def validate_effective_days(value: Any) -> None:
    """Validate ``SiteShift.effective_days`` — at least one day is required."""
    validate_day_codes(value, field="effective_days", allow_empty=False)


def validate_shift_time_logic(start: time | None, end: time | None) -> None:
    """Validate shift start/end times.

    Overnight shifts (``end <= start``) are explicitly supported and valid —
    the shift simply crosses midnight. Only missing values are rejected.
    """
    if start is None or end is None:
        raise ValidationError("Shift start and end times are required.", code="invalid_shift_time")
