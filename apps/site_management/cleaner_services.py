"""Cleaner registry and document services.

All mutations are transactional and audited. Status transitions are enforced
here — the model alone never changes a cleaner's status. Domain events are
published through the outbox (``transaction.on_commit``).
"""

from __future__ import annotations

import hashlib
from datetime import date, datetime
from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.core.files import validate_file_extension, validate_file_size
from apps.core.models import AuditLog
from apps.core.services import model_data, publish_domain_event, record_audit

from .models import (
    Cleaner,
    CleanerDocument,
    CleanerDocumentStatus,
    CleanerDocumentType,
    CleanerStatus,
    Gender,
    IdType,
)

EVENT_CLEANER_REGISTERED = "CleanerRegistered"
EVENT_CLEANER_ACTIVATED = "CleanerActivated"
EVENT_CLEANER_DEACTIVATED = "CleanerDeactivated"

#: Allowed status transitions (target states reachable from a given state).
CLEANER_TRANSITIONS: dict[CleanerStatus, set[CleanerStatus]] = {
    CleanerStatus.APPLICANT: {CleanerStatus.TRAINEE, CleanerStatus.INACTIVE},
    CleanerStatus.TRAINEE: {CleanerStatus.ACTIVE, CleanerStatus.INACTIVE, CleanerStatus.APPLICANT},
    CleanerStatus.ACTIVE: {CleanerStatus.INACTIVE, CleanerStatus.TRAINEE},
    CleanerStatus.INACTIVE: {CleanerStatus.ACTIVE, CleanerStatus.TRAINEE, CleanerStatus.APPLICANT},
}

_IDENTITY_DOC_TYPES = {
    CleanerDocumentType.BIRTH_CERTIFICATE,
    CleanerDocumentType.NIDA,
    CleanerDocumentType.ZANZIBAR_ID,
}


def _emit_event(event_type: str, cleaner: Cleaner, actor: User | None, payload: dict[str, Any] | None = None) -> None:
    publish_domain_event(
        event_type=event_type,
        aggregate_type="site_management.cleaner",
        aggregate_id=cleaner.pk,
        payload=payload or {"cleaner_id": cleaner.pk, "full_name": cleaner.full_name},
        created_by=actor,
    )


def _cleaner_audit(
    action: AuditLog.Action,
    cleaner: Cleaner,
    actor: User,
    summary: str,
    *,
    before: dict[str, Any] | None = None,
) -> None:
    record_audit(
        action=action,
        actor=actor,
        entity=cleaner,
        summary=summary,
        before_data=before,
        after_data=model_data(cleaner),
    )


def register_cleaner(
    *,
    first_name: str,
    last_name: str,
    id_type: IdType,
    id_number: str,
    birth_date: date,
    gender: Gender = Gender.UNSPECIFIED,
    living_location: str = "",
    phone_number: str = "",
    near_person_name: str = "",
    near_person_relationship: str = "",
    near_person_phone: str = "",
    notes: str = "",
    initial_status: CleanerStatus = CleanerStatus.APPLICANT,
    actor: User,
) -> Cleaner:
    """Register a new cleaner with an audited HR-selected initial lifecycle status."""
    with transaction.atomic():
        cleaner = Cleaner(
            first_name=first_name,
            last_name=last_name,
            id_type=id_type,
            id_number=id_number,
            birth_date=birth_date,
            gender=gender,
            living_location=living_location,
            phone_number=phone_number,
            near_person_name=near_person_name,
            near_person_relationship=near_person_relationship,
            near_person_phone=near_person_phone,
            notes=notes,
            status=CleanerStatus(initial_status),
            created_by=actor,
            updated_by=actor,
        )
        cleaner.full_clean()
        cleaner.save()
        _cleaner_audit(AuditLog.Action.CREATE, cleaner, actor, f"Registered cleaner {cleaner.full_name}")
        _emit_event(EVENT_CLEANER_REGISTERED, cleaner, actor)
    return cleaner


def update_cleaner(
    *,
    cleaner: Cleaner,
    actor: User,
    first_name: str | None = None,
    last_name: str | None = None,
    gender: Gender | None = None,
    living_location: str | None = None,
    phone_number: str | None = None,
    near_person_name: str | None = None,
    near_person_relationship: str | None = None,
    near_person_phone: str | None = None,
    notes: str | None = None,
) -> Cleaner:
    """Update editable cleaner profile fields."""
    with transaction.atomic():
        before = model_data(cleaner)
        fields = {
            "first_name": first_name,
            "last_name": last_name,
            "gender": gender.value if isinstance(gender, Gender) else gender,
            "living_location": living_location,
            "phone_number": phone_number,
            "near_person_name": near_person_name,
            "near_person_relationship": near_person_relationship,
            "near_person_phone": near_person_phone,
            "notes": notes,
        }
        for field, value in fields.items():
            if value is not None:
                setattr(cleaner, field, value)
        cleaner.updated_by = actor
        cleaner.full_clean()
        cleaner.save()
        _cleaner_audit(AuditLog.Action.UPDATE, cleaner, actor, f"Updated cleaner {cleaner.full_name}", before=before)
    return cleaner


def change_cleaner_status(*, cleaner: Cleaner, new_status: CleanerStatus, actor: User) -> Cleaner:
    """Transition a cleaner's status through the allowed state machine."""
    with transaction.atomic():
        target = CleanerStatus(new_status)
        if target == cleaner.status:
            return cleaner
        allowed = CLEANER_TRANSITIONS.get(CleanerStatus(cleaner.status), set())
        if target not in allowed:
            raise ValidationError(
                f"Cannot transition cleaner from {cleaner.status} to {target.value}.", code="invalid_transition"
            )
        if target == CleanerStatus.ACTIVE and not cleaner.has_verified_id:
            raise ValidationError(
                "A cleaner cannot become ACTIVE without at least one verified identity document.",
                code="missing_verified_id",
            )
        before = model_data(cleaner)
        cleaner.status = target
        cleaner.updated_by = actor
        cleaner.save(update_fields=["status", "updated_by", "updated_at"])
        _cleaner_audit(
            AuditLog.Action.STATUS_CHANGE,
            cleaner,
            actor,
            f"Cleaner status changed to {target.value}",
            before=before,
        )
        if target == CleanerStatus.ACTIVE:
            _emit_event(EVENT_CLEANER_ACTIVATED, cleaner, actor)
        elif target == CleanerStatus.INACTIVE:
            _emit_event(EVENT_CLEANER_DEACTIVATED, cleaner, actor)
    return cleaner


def activate_cleaner_if_eligible(*, cleaner: Cleaner, actor: User) -> Cleaner:
    """Activate a cleaner when they have a verified identity document."""
    with transaction.atomic():
        if not cleaner.has_verified_id:
            raise ValidationError(
                "Cleaner cannot be activated without a verified identity document.", code="missing_verified_id"
            )
        if cleaner.status == CleanerStatus.ACTIVE:
            return cleaner
        before = model_data(cleaner)
        cleaner.status = CleanerStatus.ACTIVE
        cleaner.updated_by = actor
        cleaner.save(update_fields=["status", "updated_by", "updated_at"])
        _cleaner_audit(AuditLog.Action.STATUS_CHANGE, cleaner, actor, "Cleaner activated", before=before)
        _emit_event(EVENT_CLEANER_ACTIVATED, cleaner, actor)
    return cleaner


def deactivate_cleaner(*, cleaner: Cleaner, actor: User) -> Cleaner:
    """Deactivate a cleaner (allowed from any status)."""
    with transaction.atomic():
        if cleaner.status == CleanerStatus.INACTIVE:
            return cleaner
        before = model_data(cleaner)
        cleaner.status = CleanerStatus.INACTIVE
        cleaner.updated_by = actor
        cleaner.save(update_fields=["status", "updated_by", "updated_at"])
        _cleaner_audit(AuditLog.Action.ARCHIVE, cleaner, actor, "Cleaner deactivated", before=before)
        _emit_event(EVENT_CLEANER_DEACTIVATED, cleaner, actor)
    return cleaner


def _file_sha256(uploaded_file: Any) -> str:
    digest = hashlib.sha256()
    for chunk in uploaded_file.chunks():
        digest.update(chunk)
    return digest.hexdigest()


def upload_cleaner_document(
    *,
    cleaner: Cleaner,
    uploaded_file: Any,
    document_type: CleanerDocumentType,
    document_number: str = "",
    expires_at: date | None = None,
    is_primary_id: bool = False,
    actor: User,
) -> CleanerDocument:
    """Upload a private cleaner document.

    Validates extension/size, computes a content hash, and rejects duplicate
    uploads of the same file for the same cleaner.
    """
    validate_file_extension(uploaded_file)
    validate_file_size(uploaded_file)

    file_hash = _file_sha256(uploaded_file)
    if cleaner.documents.filter(file_hash=file_hash).exists():
        raise ValidationError(
            "A document with identical content is already attached to this cleaner.",
            code="duplicate_document",
        )

    with transaction.atomic():
        document = CleanerDocument.objects.create(
            cleaner=cleaner,
            document_type=document_type,
            document_number=(document_number or "").strip().upper(),
            file=uploaded_file,
            original_filename=uploaded_file.name or "",
            content_type=getattr(uploaded_file, "content_type", ""),
            size_bytes=getattr(uploaded_file, "size", 0),
            file_hash=file_hash,
            status=CleanerDocumentStatus.PENDING,
            expires_at=expires_at,
            is_primary_id=is_primary_id,
            uploaded_by=actor,
            created_by=actor,
            updated_by=actor,
        )
        record_audit(
            action=AuditLog.Action.CREATE,
            actor=actor,
            entity=document,
            summary=f"Uploaded {document_type.label} for {cleaner.full_name}",
            after_data=model_data(document),
        )
    return document


def verify_cleaner_document(*, document: CleanerDocument, actor: User) -> CleanerDocument:
    """Mark a document verified; verified identity documents grant eligibility."""
    with transaction.atomic():
        if document.status == CleanerDocumentStatus.VERIFIED:
            return document
        before = model_data(document)
        document.status = CleanerDocumentStatus.VERIFIED
        document.verified_by = actor
        document.verified_at = _now()
        document.rejection_reason = ""
        document.updated_by = actor
        document.save(
            update_fields=["status", "verified_by", "verified_at", "rejection_reason", "updated_by", "updated_at"]
        )
        record_audit(
            action=AuditLog.Action.UPDATE,
            actor=actor,
            entity=document,
            summary=f"Verified {document.document_type} for {document.cleaner.full_name}",
            before_data=before,
            after_data=model_data(document),
        )
    return document


def reject_cleaner_document(*, document: CleanerDocument, actor: User, reason: str) -> CleanerDocument:
    """Reject a document with a reason."""
    with transaction.atomic():
        if document.status == CleanerDocumentStatus.REJECTED:
            return document
        before = model_data(document)
        document.status = CleanerDocumentStatus.REJECTED
        document.rejection_reason = reason
        document.updated_by = actor
        document.save(update_fields=["status", "rejection_reason", "updated_by", "updated_at"])
        record_audit(
            action=AuditLog.Action.UPDATE,
            actor=actor,
            entity=document,
            summary=f"Rejected {document.document_type} for {document.cleaner.full_name}",
            before_data=before,
            after_data=model_data(document),
        )
    return document


def _now() -> datetime:
    return timezone.now()
