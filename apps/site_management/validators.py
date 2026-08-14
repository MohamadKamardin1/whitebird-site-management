"""Domain validators for the site management app."""

from __future__ import annotations

from typing import Any

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

#: Valid ISO weekday codes used by ``Site.working_days``.
WORKING_DAYS: tuple[str, ...] = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


def validate_working_days(value: Any) -> None:
    """Validate a list of weekday codes (portable ArrayField equivalent)."""
    if not isinstance(value, list):
        raise ValidationError(_("working_days must be a list of day codes."), code="invalid_working_days")
    invalid = sorted(set(value) - set(WORKING_DAYS))
    if invalid:
        raise ValidationError(
            _("Invalid working days: %(days)s. Allowed: %(allowed)s.")
            % {"days": ", ".join(invalid), "allowed": ", ".join(WORKING_DAYS)},
            code="invalid_working_days",
        )
