"""Inspection read selectors (role-scoped, query-efficient)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from django.db.models import Avg, Count, Max, Q, QuerySet

from apps.accounts.models import User

from .models import (
    Inspection,
    InspectionOverallStatus,
    InspectionResult,
    InspectionTemplate,
    InspectionTemplateItem,
    InspectionWorkflowStatus,
)
from .scoping import visible_sites


@dataclass(frozen=True)
class TemplateFilter:
    site_id: int | None = None
    is_active: bool | None = None
    search: str | None = None
    frequency: str | None = None


@dataclass(frozen=True)
class InspectionFilter:
    site_id: int | None = None
    area_id: int | None = None
    template_id: int | None = None
    status: str | None = None
    overall_status: str | None = None
    date_from: date | None = None
    date_to: date | None = None


def _scoped_sites(user: User) -> Q:
    if user.is_system_admin:
        return Q()
    return Q(site__in=visible_sites(user))


def template_list(user: User, spec: TemplateFilter) -> QuerySet[InspectionTemplate]:
    """Inspection templates visible to the user.

    Global templates (``site IS NULL``) are always visible; site-specific
    templates are scoped to the user's visible sites.
    """
    qs: QuerySet[InspectionTemplate] = InspectionTemplate.objects.select_related("site", "area").annotate(
        annotated_item_count=Count("items", distinct=True)
    )
    if not user.is_system_admin:
        qs = qs.filter(Q(site__isnull=True) | Q(site__in=visible_sites(user)))
    if spec.site_id:
        qs = qs.filter(Q(site__isnull=True) | Q(site_id=spec.site_id))
    if spec.is_active is not None:
        qs = qs.filter(is_active=spec.is_active)
    if spec.frequency:
        qs = qs.filter(frequency=spec.frequency)
    if spec.search:
        qs = qs.filter(Q(template_name__icontains=spec.search) | Q(description__icontains=spec.search))
    return qs


def get_template_or_none(template_id: int) -> InspectionTemplate | None:
    """A single template (including inactive ones) with items prefetched."""
    return (
        InspectionTemplate._base_manager.select_related("site", "area")
        .prefetch_related("items")
        .filter(pk=template_id)
        .first()
    )


def template_items(template_id: int) -> list[InspectionTemplateItem]:
    return list(InspectionTemplateItem.objects.filter(template_id=template_id).order_by("sequence", "pk"))


def inspection_list(user: User, spec: InspectionFilter) -> QuerySet[Inspection]:
    """Inspections in the user's scope with filters (one query)."""
    qs: QuerySet[Inspection] = Inspection.objects.select_related(
        "site", "area", "template", "shift", "inspected_by", "created_by"
    )
    if not user.is_system_admin:
        qs = qs.filter(_scoped_sites(user))
    if spec.site_id:
        qs = qs.filter(site_id=spec.site_id)
    if spec.area_id:
        qs = qs.filter(area_id=spec.area_id)
    if spec.template_id:
        qs = qs.filter(template_id=spec.template_id)
    if spec.status:
        qs = qs.filter(status=spec.status)
    if spec.overall_status:
        qs = qs.filter(overall_status=spec.overall_status)
    if spec.date_from:
        qs = qs.filter(inspection_date__gte=spec.date_from)
    if spec.date_to:
        qs = qs.filter(inspection_date__lte=spec.date_to)
    return qs


def get_inspection_or_none(inspection_id: int) -> Inspection | None:
    return (
        Inspection.objects.select_related("site", "area", "template", "shift", "inspected_by")
        .prefetch_related("results__template_item", "results__uploaded_by")
        .filter(pk=inspection_id)
        .first()
    )


def inspection_results(inspection_id: int) -> list[InspectionResult]:
    return list(
        InspectionResult.objects.filter(inspection_id=inspection_id)
        .select_related("template_item", "uploaded_by")
        .order_by("template_item__sequence", "pk")
    )


def inspection_summary(user: User, site_id: int | None = None) -> dict[str, Any]:
    """Counts per workflow/overall status plus the average score for the scope."""
    qs = inspection_list(user, InspectionFilter(site_id=site_id))
    statuses = {row["status"]: row["n"] for row in qs.values("status").order_by().annotate(n=Count("pk"))}
    overall = {
        row["overall_status"]: row["n"] for row in qs.values("overall_status").order_by().annotate(n=Count("pk"))
    }
    agg = qs.aggregate(avg_score=Avg("score"), max_date=Max("inspection_date"))
    return {
        "total_inspections": sum(statuses.values()),
        "draft": statuses.get(InspectionWorkflowStatus.DRAFT.value, 0),
        "submitted": statuses.get(InspectionWorkflowStatus.SUBMITTED.value, 0),
        "reviewed": statuses.get(InspectionWorkflowStatus.REVIEWED.value, 0),
        "returned": statuses.get(InspectionWorkflowStatus.RETURNED.value, 0),
        "passed": overall.get(InspectionOverallStatus.PASSED.value, 0),
        "failed": overall.get(InspectionOverallStatus.FAILED.value, 0),
        "needs_attention": overall.get(InspectionOverallStatus.NEEDS_ATTENTION.value, 0),
        "average_score": agg["avg_score"],
        "last_inspection_date": agg["max_date"],
    }


def area_latest_status(user: User, area_id: int) -> dict[str, Any] | None:
    """Most recent inspection overall status/score for an area in the user's scope."""
    qs = Inspection.objects.filter(area_id=area_id).exclude(status=InspectionWorkflowStatus.DRAFT)
    if not user.is_system_admin:
        qs = qs.filter(site__in=visible_sites(user))
    latest = qs.order_by("-inspection_date", "-created_at").select_related("template").first()
    if latest is None:
        return None
    return {
        "area_id": area_id,
        "inspection_id": latest.pk,
        "inspection_date": latest.inspection_date,
        "overall_status": latest.overall_status,
        "score": latest.score,
        "template_name": latest.template.template_name,
    }
