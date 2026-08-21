"""Selectors and serializers for cleaner records with protected personal data.

ID numbers and phone numbers are masked for callers who lack the sensitive
cleaner-document permission. No cleaner data is cached — PII never lives in
Redis.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.db.models import OuterRef, Q, QuerySet, Subquery

from apps.accounts.models import RoleCode, User

from .models import (
    Cleaner,
    CleanerAssignmentStatus,
    CleanerDocument,
    CleanerSiteAssignment,
    TraineeProgram,
    TraineeProgramStatus,
)

SENSITIVE_DOCUMENT_PERMISSION = "accounts.view_sensitive_cleaner_documents"


def mask_value(value: str, *, keep: int = 4) -> str:
    """Mask a sensitive string, retaining only its final characters."""
    value = (value or "").strip()
    if not value:
        return ""
    if len(value) <= keep:
        return "*" * len(value)
    return f"{'*' * (len(value) - keep)}{value[-keep:]}"


def can_view_full_cleaner_profile(user: User, cleaner: Cleaner | None = None) -> bool:
    """Allow unmasked ordinary cleaner profile data only to System Administrators."""
    return user.is_system_admin


def can_view_document(user: User, document: CleanerDocument) -> bool:
    """Documents are sensitive; viewing requires the sensitive permission."""
    return (
        user.is_system_admin
        or user.role == RoleCode.HR
        or user.has_perm(SENSITIVE_DOCUMENT_PERMISSION)
    )


@dataclass(frozen=True)
class CleanerFilter:
    search: str | None = None
    status: str | None = None
    id_type: str | None = None
    gender: str | None = None


def cleaner_list_queryset(user: User, spec: CleanerFilter) -> QuerySet[Cleaner]:
    """Return role-scoped cleaner records with current site/training location annotations."""
    from django.db.models import Exists

    from .models import CleanerDocument, CleanerDocumentStatus, CleanerDocumentType

    current_assignments = CleanerSiteAssignment.objects.filter(
        cleaner_id=OuterRef("pk"),
        status__in=[CleanerAssignmentStatus.ACTIVE, CleanerAssignmentStatus.DRAFT],
    ).order_by("-start_date", "-pk")
    active_programs = TraineeProgram.objects.filter(
        cleaner_id=OuterRef("pk"),
        status__in=[TraineeProgramStatus.IN_TRAINING, TraineeProgramStatus.EXTENDED],
    ).order_by("-start_date", "-pk")
    qs: QuerySet[Cleaner] = Cleaner.objects.annotate(
        has_verified_id_flag=Exists(
            CleanerDocument.objects.filter(
                cleaner=OuterRef("pk"),
                status=CleanerDocumentStatus.VERIFIED,
                document_type__in=[
                    CleanerDocumentType.BIRTH_CERTIFICATE,
                    CleanerDocumentType.NIDA,
                    CleanerDocumentType.ZANZIBAR_ID,
                ],
            )
        ),
        current_site_id_value=Subquery(current_assignments.values("site_id")[:1]),
        current_site_name_value=Subquery(current_assignments.values("site__name")[:1]),
        trainee_program_id_value=Subquery(active_programs.values("pk")[:1]),
        trainee_site_name_value=Subquery(active_programs.values("site__name")[:1]),
    )
    if spec.search:
        qs = qs.filter(
            Q(first_name__icontains=spec.search)
            | Q(last_name__icontains=spec.search)
            | Q(id_number__icontains=spec.search)
        )
    if spec.status:
        qs = qs.filter(status=spec.status)
    if spec.id_type:
        qs = qs.filter(id_type=spec.id_type)
    if spec.gender:
        qs = qs.filter(gender=spec.gender)

    # Site supervisors see operationally assigned cleaners and trainees at
    # their site. HR and higher management retain portfolio visibility.
    if user.role == RoleCode.SITE_SUPERVISOR:
        from .scoping import visible_sites

        qs = qs.filter(
            site_assignments__site__in=visible_sites(user),
            site_assignments__status__in=[CleanerAssignmentStatus.ACTIVE, CleanerAssignmentStatus.DRAFT],
        ).distinct()
    return qs


def get_cleaner_or_none(cleaner_id: int) -> Cleaner | None:
    return Cleaner.objects.select_related("created_by", "updated_by").filter(pk=cleaner_id).first()


def cleaner_documents(cleaner_id: int) -> list[CleanerDocument]:
    return list(
        CleanerDocument.objects.filter(cleaner_id=cleaner_id)
        .select_related("cleaner", "verified_by")
        .order_by("-created_at")
    )


def get_cleaner_document_or_none(cleaner_id: int, document_id: int) -> CleanerDocument | None:
    return (
        CleanerDocument.objects.filter(pk=document_id, cleaner_id=cleaner_id)
        .select_related("cleaner", "verified_by")
        .first()
    )


def cleaner_serialize(cleaner: Cleaner, user: User) -> dict[str, Any]:
    """Shape a cleaner for API output, masking PII for non-privileged users."""
    full = can_view_full_cleaner_profile(user, cleaner)
    return {
        "id": cleaner.pk,
        "first_name": cleaner.first_name,
        "last_name": cleaner.last_name,
        "full_name": cleaner.full_name,
        "id_type": cleaner.id_type,
        "id_number": cleaner.id_number if full else mask_value(cleaner.id_number),
        "gender": cleaner.gender,
        "birth_date": cleaner.birth_date.isoformat(),
        "living_location": cleaner.living_location,
        "phone_number": cleaner.phone_number if full else mask_value(cleaner.phone_number),
        "near_person_name": cleaner.near_person_name,
        "near_person_relationship": cleaner.near_person_relationship,
        "near_person_phone": cleaner.near_person_phone if full else mask_value(cleaner.near_person_phone),
        "status": cleaner.status,
        "current_site_id": getattr(cleaner, "current_site_id_value", None),
        "current_site_name": getattr(cleaner, "current_site_name_value", None),
        "trainee_program_id": getattr(cleaner, "trainee_program_id_value", None),
        "training_site_name": getattr(cleaner, "trainee_site_name_value", None),
        "registration_date": cleaner.registration_date.isoformat(),
        "has_verified_id": (
            bool(getattr(cleaner, "has_verified_id_flag", None))
            if getattr(cleaner, "has_verified_id_flag", None) is not None
            else cleaner.has_verified_id
        ),
        "notes": cleaner.notes,
        "created_at": cleaner.created_at.isoformat(),
        "updated_at": cleaner.updated_at.isoformat(),
    }


def cleaner_document_serialize(document: CleanerDocument, user: User) -> dict[str, Any]:
    """Shape a document for API output; document numbers are masked by default."""
    full = can_view_document(user, document)
    return {
        "id": document.pk,
        "cleaner_id": document.cleaner_id,
        "document_type": document.document_type,
        "document_number": document.document_number if full else mask_value(document.document_number),
        "status": document.status,
        "rejection_reason": document.rejection_reason,
        "expires_at": document.expires_at.isoformat() if document.expires_at else None,
        "is_primary_id": document.is_primary_id,
        "is_identity": document.is_identity,
        "original_filename": document.original_filename,
        "content_type": document.content_type,
        "size_bytes": document.size_bytes,
        "verified_by": document.verified_by.email if document.verified_by else None,
        "verified_at": document.verified_at.isoformat() if document.verified_at else None,
        "created_at": document.created_at.isoformat(),
    }
