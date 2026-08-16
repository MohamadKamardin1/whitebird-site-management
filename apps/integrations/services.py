"""Integration use-cases tying DeepSeek/Mapbox into the domain.

These are the only places business logic touches external providers; engines
stay provider-transport-only. Each use-case degrades gracefully when a provider
is not configured (returns ``None`` / raises a typed error for the caller to
handle).
"""

from __future__ import annotations

from typing import Any

from django.core.exceptions import ValidationError

from . import deepseek, mapbox
from .transport import ProviderError


def summarize_site_report(report: Any, *, instruction: str = "") -> str | None:
    """Produce an executive summary of a daily site report via DeepSeek."""
    if not deepseek.enabled():
        return None
    context = _report_text(report)
    try:
        return deepseek.summarize(
            context,
            instruction=instruction
            or "You are a hospitality operations assistant. Summarise this daily site report "
            "into 3-5 tight bullet points covering attendance, issues, store and inspections.",
        )
    except ProviderError:
        return None


def _report_text(report: Any) -> str:
    parts = [
        f"Site: {report.site.name}",
        f"Date: {report.report_date}",
        f"Status: {report.status}",
        f"Attendance: {report.attendance_summary}",
        f"Store: {report.store_summary}",
        f"Inspections: {report.inspection_summary}",
        f"Issues: {report.issues_summary}",
        f"Trainees: {report.trainee_summary}",
    ]
    if report.general_comments:
        parts.append(f"Comments: {report.general_comments}")
    return "\n".join(parts)


def geocode_site(site: Any) -> dict[str, Any] | None:
    """Geocode a site's name/location and persist coordinates via Mapbox."""
    if not mapbox.enabled():
        return None
    query = ", ".join(part for part in (site.name, site.city, site.region, site.country) if part)
    try:
        feature = mapbox.geocode(query)
    except ProviderError:
        return None
    if feature is None or feature.get("longitude") is None or feature.get("latitude") is None:
        raise ValidationError("Mapbox returned no coordinates for this site.", code="geocode_not_found")
    site.latitude = feature["latitude"]
    site.longitude = feature["longitude"]
    site.save(update_fields=["latitude", "longitude", "updated_at"])
    return feature
