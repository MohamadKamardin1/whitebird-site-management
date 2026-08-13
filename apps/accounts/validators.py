"""Field validators shared across the accounts app."""

from __future__ import annotations

import re
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

# Tanzania mobile: local (07xx xxx xxx) or international E.164 (+2557xx xxx xxx).
# Also accepts generic international numbers per the E.164 spec.
_PHONE_PATTERN = re.compile(r"^(?:\+?[1-9][0-9]{7,14}|0[0-9]{8,10})$")


def validate_phone(value: str) -> None:
    """Validate a Tanzania/international phone number.

    Accepts an optional leading ``+`` for international (E.164) format or a
    leading ``0`` for local Tanzanian numbers.
    """
    if not _PHONE_PATTERN.match(value):
        raise ValidationError(
            _("Enter a valid phone number, e.g. +2557xxxxxxxxx or 07xxxxxxxxx."),
            code="invalid_phone",
        )


def validate_timezone(value: str) -> None:
    """Validate that a string is a known IANA timezone name."""
    try:
        ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ValidationError(
            _("Enter a valid IANA timezone, e.g. Africa/Dar_es_Salaam."),
            code="invalid_timezone",
        ) from exc
