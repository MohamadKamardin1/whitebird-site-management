"""Cleaner registry read selectors with privacy-aware field masking.

ID numbers and phone numbers are masked for callers who lack the sensitive
cleaner-document permission. No cleaner data is cached — PII never lives in
Redis.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.db.models import Q, QuerySet

from apps.accounts.models import User

from .models import Cleaner, CleanerDocument

SENSITIVE_DOCUMENT_PERMISSION = "accounts.view_sensitive_cleaner_documents"


def mask_value(value: str, *, keep: int = 4) -> str:
    """Mask a sensitive value, keeping the last ``keep`` characters."""
    value = (value or "").strip()
    if not value:
        return ""
    if len(value) <= keep:
        return "*" * len(value)
    return f"{'*' * (len(value) - keep)}{value[-keep:]}"


def can_view_full_cleaner_profile(user: User, cleaner: Cleaner | None = None) -> bool:
    """True when the user may see unmasked PII and sensitive document content."""
    return user.is_system_admin or user.has_perm(SENSITIVE_DOCUMENT_PERMISSION)


def can_view_document(user: User, document: CleanerDocument) -> bool:
    """Documents are sensitive; viewing requires the sensitive permission."""
    return can_view_full_cleaner_profile(user, document.cleaner)


@dataclass(frozen=True)
class CleanerFilter:
    search: str | None = None
    status: str | None = None
    id_type: str | None = None
    gender: str | None = None


def cleaner_list_queryset(user: User, spec: CleanerFilter) -> QuerySet[Cleaner]:
    """Cleaners visible to the user (all statuses; management roles only).

    The verified-identity flag is annotated with an ``Exists`` subquery so
    serializing a page never fires a per-cleaner document query (N+1).
    """
    from django.db.models import Exists, OuterRef

    from .models import CleanerDocument, CleanerDocumentStatus, CleanerDocumentType

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
        )
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
