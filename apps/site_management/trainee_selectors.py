"""Trainee lifecycle read selectors (role-scoped)."""

from __future__ import annotations

from dataclasses import dataclass

from django.db.models import Avg, Count, Q, QuerySet

from apps.accounts.models import User

from .models import TraineeEvaluation, TraineeProgram, TraineeProgramStatus
from .scoping import visible_sites


@dataclass(frozen=True)
class TraineeFilter:
    site_id: int | None = None
    status: str | None = None
    search: str | None = None


def trainee_list_queryset(user: User, spec: TraineeFilter) -> QuerySet[TraineeProgram]:
    qs: QuerySet[TraineeProgram] = TraineeProgram.objects.select_related("cleaner", "site", "assigned_site_supervisor")
    if not user.is_system_admin:
        qs = qs.filter(site__in=visible_sites(user))
    if spec.site_id:
        qs = qs.filter(site_id=spec.site_id)
    if spec.status:
        qs = qs.filter(status=spec.status)
    if spec.search:
        qs = qs.filter(Q(cleaner__first_name__icontains=spec.search) | Q(cleaner__last_name__icontains=spec.search))
    return qs


def get_trainee_program_or_none(program_id: int) -> TraineeProgram | None:
    return (
        TraineeProgram.objects.select_related("cleaner", "site", "assigned_site_supervisor")
        .prefetch_related("evaluations__evaluated_by")
        .filter(pk=program_id)
        .first()
    )


def trainee_evaluations(program_id: int) -> list[TraineeEvaluation]:
    return list(
        TraineeEvaluation.objects.filter(trainee_program_id=program_id)
        .select_related("evaluated_by")
        .order_by("-evaluation_date")
    )


def trainee_summary(user: User, spec: TraineeFilter) -> dict[str, int]:
    """Counts of trainee programs by status for the visible scope."""
    qs = trainee_list_queryset(user, spec)
    grouped = {item["status"]: item["n"] for item in qs.values("status").order_by().annotate(n=Count("pk"))}
    return {
        "total_trainees": sum(grouped.values()),
        "in_training": grouped.get(TraineeProgramStatus.IN_TRAINING.value, 0),
        "extended": grouped.get(TraineeProgramStatus.EXTENDED.value, 0),
        "passed": grouped.get(TraineeProgramStatus.PASSED.value, 0),
        "failed": grouped.get(TraineeProgramStatus.FAILED.value, 0),
        "dropped": grouped.get(TraineeProgramStatus.DROPPED.value, 0),
    }


def trainee_average_score(program_id: int) -> float | None:
    """Average evaluation total for a program (used by admin listings)."""
    return (
        TraineeProgram.objects.filter(pk=program_id)
        .annotate(avg_total=Avg("evaluations__total_score"))
        .values_list("avg_total", flat=True)
        .first()
    )
