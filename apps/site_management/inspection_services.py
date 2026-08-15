"""Inspection engine services.

Template lifecycle, the inspection draft→submit→review→return workflow, and
transparent score calculation. All writes are transactional and audited;
submissions emit an ``InspectionSubmitted`` event and failed results invoke the
``create_issue_from_failed_result`` hook (in-platform notification + domain
event, ready for the future Issues module).
"""

from __future__ import annotations

import datetime
from decimal import Decimal
from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.core.files import validate_file_extension, validate_file_size
from apps.core.models import AuditLog
from apps.core.services import model_data, publish_domain_event, record_audit

from .models import (
    Inspection,
    InspectionItemType,
    InspectionOverallStatus,
    InspectionResult,
    InspectionTemplate,
    InspectionTemplateItem,
    InspectionWorkflowStatus,
    Site,
    SiteArea,
    Cleaner,
    SiteShift,
)
from .policies import can_review_inspection, ensure
from .services import create_notification

EVENT_INSPECTION_SUBMITTED = "InspectionSubmitted"
EVENT_INSPECTION_ISSUE = "InspectionIssueDetected"

PASS_THRESHOLD = Decimal("70")


def _emit(event_type: str, inspection: Inspection, actor: User, payload: dict[str, Any] | None = None) -> None:
    publish_domain_event(
        event_type=event_type,
        aggregate_type="site_management.inspection",
        aggregate_id=inspection.pk,
        payload=payload
        or {
            "inspection_id": inspection.pk,
            "site_id": inspection.site_id,
            "area_id": inspection.area_id,
        },
        created_by=actor,
    )


def _audit(
    action: AuditLog.Action,
    inspection: Inspection,
    actor: User,
    summary: str,
    *,
    before: dict[str, Any] | None = None,
) -> None:
    record_audit(
        action=action,
        actor=actor,
        entity=inspection,
        summary=summary,
        before_data=before,
        after_data=model_data(inspection),
    )


def _ensure_editable(inspection: Inspection) -> None:
    if not inspection.is_editable:
        raise ValidationError(
            "Submitted inspections are immutable; return them before editing.", code="inspection_immutable"
        )


# --------------------------------------------------------------------------- #
# Templates
# --------------------------------------------------------------------------- #


def create_template(
    *,
    template_name: str,
    actor: User,
    description: str = "",
    site: Site | None = None,
    area: SiteArea | None = None,
    frequency: str = "manual",
    items: list[dict[str, Any]] | None = None,
) -> InspectionTemplate:
    """Create an inspection template (optionally with its items)."""
    with transaction.atomic():
        if area is not None and (site is None or area.site_id != site.pk):
            raise ValidationError("An area requires the template's site.", code="area_site_mismatch")
        template = InspectionTemplate(
            template_name=template_name,
            description=description,
            site=site,
            area=area,
            frequency=frequency,
            created_by=actor,
            updated_by=actor,
        )
        template.full_clean()
        template.save()
        for row in items or []:
            _create_template_item(template, row, actor)
        record_audit(
            action=AuditLog.Action.CREATE,
            actor=actor,
            entity=template,
            summary=f"Created inspection template {template.template_name}",
            after_data=model_data(template),
        )
    return template


def _create_template_item(template: InspectionTemplate, row: dict[str, Any], actor: User) -> InspectionTemplateItem:
    item = InspectionTemplateItem(
        template=template,
        item_label=row["item_label"],
        item_type=row["item_type"],
        required=bool(row.get("required", True)),
        sequence=int(row.get("sequence", 0)),
        help_text=row.get("help_text", ""),
    )
    item.full_clean()
    item.save()
    record_audit(
        action=AuditLog.Action.CREATE,
        actor=actor,
        entity=item,
        summary=f"Added template item {item.item_label}",
    )
    return item


def update_template(
    *,
    template: InspectionTemplate,
    actor: User,
    template_name: str | None = None,
    description: str | None = None,
    frequency: str | None = None,
    items: list[dict[str, Any]] | None = None,
) -> InspectionTemplate:
    """Update template metadata and/or sync its items."""
    with transaction.atomic():
        before = model_data(template)
        if template_name is not None:
            template.template_name = template_name
        if description is not None:
            template.description = description
        if frequency is not None:
            template.frequency = frequency
        template.updated_by = actor
        template.full_clean()
        template.save()
        if items is not None:
            template.items.all().delete()
            for row in items:
                _create_template_item(template, row, actor)
        record_audit(
            action=AuditLog.Action.UPDATE,
            actor=actor,
            entity=template,
            summary=f"Updated inspection template {template.template_name}",
            before_data=before,
        )
    return template


def deactivate_template(*, template: InspectionTemplate, actor: User) -> InspectionTemplate:
    """Deactivate a template. Templates are never deleted once they exist;
    historical inspections keep the template available for reporting."""
    with transaction.atomic():
        before = model_data(template)
        template.is_active = False
        template.updated_by = actor
        template.save(update_fields=["is_active", "updated_by", "updated_at"])
        record_audit(
            action=AuditLog.Action.ARCHIVE,
            actor=actor,
            entity=template,
            summary=f"Deactivated inspection template {template.template_name}",
            before_data=before,
        )
    return template


# --------------------------------------------------------------------------- #
# Inspections
# --------------------------------------------------------------------------- #


def start_inspection(
    *,
    site: Site,
    area: SiteArea,
    template: InspectionTemplate,
    inspected_by: User,
    actor: User,
    inspection_date: datetime.date | None = None,
    shift: SiteShift | None = None,
    notes: str = "",
) -> Inspection:
    """Start a DRAFT inspection for an area using a template."""
    with transaction.atomic():
        if template.site_id and template.site_id != site.pk:
            raise ValidationError("Template is not scoped to this site.", code="template_site_mismatch")
        inspection = Inspection(
            site=site,
            area=area,
            template=template,
            inspection_date=inspection_date or datetime.date.today(),
            shift=shift,
            inspected_by=inspected_by,
            notes=notes,
            status=InspectionWorkflowStatus.DRAFT,
            created_by=actor,
            updated_by=actor,
        )
        inspection.full_clean()
        inspection.save()
        _audit(AuditLog.Action.CREATE, inspection, actor, f"Started inspection at {site.name}")
    return inspection


def add_inspection_result(
    *,
    inspection: Inspection,
    template_item: InspectionTemplateItem,
    actor: User,
    value_text: str = "",
    value_number: Decimal | None = None,
    value_boolean: bool | None = None,
    passed: bool | None = None,
    notes: str = "",
    responsible_cleaner: Cleaner | None = None,
) -> InspectionResult:
    """Add an answer to a template item for an editable inspection."""
    with transaction.atomic():
        _ensure_editable(inspection)
        result = InspectionResult(
            inspection=inspection,
            template_item=template_item,
            value_text=value_text,
            value_number=value_number,
            value_boolean=value_boolean,
            passed=passed,
            notes=notes,
            responsible_cleaner=responsible_cleaner,
            uploaded_by=actor,
        )
        result.full_clean(exclude=["file"])
        result.save()
        record_audit(
            action=AuditLog.Action.CREATE,
            actor=actor,
            entity=result,
            summary=f"Result recorded for {template_item.item_label}",
            after_data=model_data(result),
        )
    return result


def update_inspection_result(
    *,
    result: InspectionResult,
    actor: User,
    value_text: str | None = None,
    value_number: Decimal | None = None,
    value_boolean: bool | None = None,
    passed: bool | None = None,
    notes: str | None = None,
    responsible_cleaner: Cleaner | None = None,
) -> InspectionResult:
    """Edit a result while the inspection is still editable."""
    with transaction.atomic():
        _ensure_editable(Inspection.objects.get(pk=result.inspection_id))
        before = model_data(result)
        if value_text is not None:
            result.value_text = value_text
        if value_number is not None:
            result.value_number = value_number
        if value_boolean is not None:
            result.value_boolean = value_boolean
        if passed is not None:
            result.passed = passed
        if notes is not None:
            result.notes = notes
        if responsible_cleaner is not None:
            result.responsible_cleaner = responsible_cleaner
        result.full_clean(exclude=["file"])
        result.save()
        record_audit(
            action=AuditLog.Action.UPDATE,
            actor=actor,
            entity=result,
            summary=f"Updated result for {result.template_item.item_label}",
            before_data=before,
        )
    return result


def upload_result_photo(*, result: InspectionResult, uploaded_file: Any, actor: User) -> InspectionResult:
    """Attach a private photo to a PHOTO result."""
    with transaction.atomic():
        _ensure_editable(Inspection.objects.get(pk=result.inspection_id))
        if result.template_item.item_type != InspectionItemType.PHOTO:
            raise ValidationError("Photo uploads are only allowed on PHOTO items.", code="not_photo_item")
        validate_file_extension(uploaded_file)
        validate_file_size(uploaded_file)
        result.file = uploaded_file
        result.original_filename = uploaded_file.name or ""
        result.content_type = getattr(uploaded_file, "content_type", "")
        result.size_bytes = getattr(uploaded_file, "size", 0)
        result.uploaded_by = actor
        result.save()
        record_audit(
            action=AuditLog.Action.CREATE,
            actor=actor,
            entity=result,
            summary=f"Photo uploaded for {result.template_item.item_label}",
        )
    return result


def save_inspection_draft(*, inspection: Inspection, actor: User, notes: str | None = None) -> Inspection:
    """Save inspection notes and refresh the score preview."""
    with transaction.atomic():
        _ensure_editable(inspection)
        before = model_data(inspection)
        if notes is not None:
            inspection.notes = notes
        score, overall = calculate_inspection_score(inspection)
        inspection.score = score
        inspection.overall_status = overall
        inspection.updated_by = actor
        inspection.save()
        _audit(AuditLog.Action.UPDATE, inspection, actor, f"Saved inspection draft {inspection.pk}", before=before)
    return inspection


def _required_items_completed(inspection: Inspection) -> list[str]:
    """Return labels of required template items without a completed answer."""
    missing: list[str] = []
    results = {r.template_item_id: r for r in inspection.results.select_related("template_item")}
    for item in inspection.template.items.filter(required=True).select_related():
        result = results.get(item.pk)
        if result is None:
            missing.append(item.item_label)
            continue
        if (
            (item.item_type == InspectionItemType.PHOTO and not result.file)
            or (item.item_type == InspectionItemType.TEXT and not result.value_text.strip())
            or (item.item_type == InspectionItemType.SCORE and result.value_number is None)
            or (item.item_type in {InspectionItemType.YES_NO, InspectionItemType.PASS_FAIL} and result.passed is None)
        ):
            missing.append(item.item_label)
    return missing


def calculate_inspection_score(inspection: Inspection) -> tuple[Decimal | None, str]:
    """Return ``(score, overall_status)`` transparently.

    ``score`` is the average of SCORE-type answers (0–100) when any exist,
    else ``None``. ``overall_status``: FAILED if any answer failed; otherwise
    NEEDS_ATTENTION when a score exists and is below ``PASS_THRESHOLD`` (70);
    otherwise PASSED.
    """
    results = list(inspection.results.all())
    scores = [r.value_number for r in results if r.value_number is not None]
    failed = any(r.passed is False for r in results)
    if scores:
        total = sum(scores, Decimal("0"))
        score = (total / Decimal(len(scores))).quantize(Decimal("0.01"))
    else:
        score = None
    if failed:
        overall = InspectionOverallStatus.FAILED
    elif score is not None and score < PASS_THRESHOLD:
        overall = InspectionOverallStatus.NEEDS_ATTENTION
    else:
        overall = InspectionOverallStatus.PASSED
    return (score, overall)


def submit_inspection(*, inspection: Inspection, actor: User) -> Inspection:
    """Submit an inspection after validating every required answer."""
    with transaction.atomic():
        if inspection.status not in {InspectionWorkflowStatus.DRAFT, InspectionWorkflowStatus.RETURNED}:
            raise ValidationError("Only draft inspections can be submitted.", code="invalid_status")
        missing = _required_items_completed(inspection)
        if missing:
            raise ValidationError(
                f"Required items are incomplete: {', '.join(missing)}.", code="required_items_incomplete"
            )
        score, overall = calculate_inspection_score(inspection)
        before = model_data(inspection)
        inspection.score = score
        inspection.overall_status = overall
        inspection.status = InspectionWorkflowStatus.SUBMITTED
        inspection.submitted_at = timezone.now()
        inspection.updated_by = actor
        inspection.save()
        _audit(
            AuditLog.Action.STATUS_CHANGE,
            inspection,
            actor,
            f"Inspection {inspection.pk} submitted ({overall})",
            before=before,
        )
        _emit(
            EVENT_INSPECTION_SUBMITTED,
            inspection,
            actor,
            {"overall_status": overall, "score": str(score) if score is not None else None},
        )
        for result in inspection.results.filter(passed=False):
            create_issue_from_failed_result(result, actor)
    return inspection


def return_inspection(*, inspection: Inspection, actor: User, reason: str) -> Inspection:
    """Return a submitted/reviewed inspection for correction."""
    with transaction.atomic():
        ensure(actor, can_review_inspection(actor, inspection), "You cannot return this inspection.")
        if inspection.status not in {InspectionWorkflowStatus.SUBMITTED, InspectionWorkflowStatus.REVIEWED}:
            raise ValidationError("Only submitted or reviewed inspections can be returned.", code="invalid_status")
        if not reason.strip():
            raise ValidationError("A reason is required to return an inspection.", code="reason_required")
        before = model_data(inspection)
        inspection.status = InspectionWorkflowStatus.RETURNED
        inspection.notes = (inspection.notes + "\n" if inspection.notes else "") + f"Returned: {reason}"
        inspection.updated_by = actor
        inspection.save()
        _audit(
            AuditLog.Action.STATUS_CHANGE,
            inspection,
            actor,
            f"Returned inspection {inspection.pk}: {reason}",
            before=before,
        )
    return inspection


def review_inspection(*, inspection: Inspection, actor: User) -> Inspection:
    """Review a submitted inspection; recompute and confirm the score/status."""
    with transaction.atomic():
        ensure(actor, can_review_inspection(actor, inspection), "You cannot review this inspection.")
        if inspection.status != InspectionWorkflowStatus.SUBMITTED:
            raise ValidationError("Only submitted inspections can be reviewed.", code="invalid_status")
        score, overall = calculate_inspection_score(inspection)
        before = model_data(inspection)
        inspection.score = score
        inspection.overall_status = overall
        inspection.status = InspectionWorkflowStatus.REVIEWED
        inspection.updated_by = actor
        inspection.save()
        _audit(AuditLog.Action.STATUS_CHANGE, inspection, actor, f"Reviewed inspection {inspection.pk}", before=before)
    return inspection


def create_issue_from_failed_result(result: InspectionResult, actor: User) -> None:
    """Hook for failed results: notifies the site supervisor and emits a domain
    event. A future Issues module will materialise these into Issue records."""
    inspection = result.inspection
    _emit(
        EVENT_INSPECTION_ISSUE,
        inspection,
        actor,
        {
            "inspection_id": inspection.pk,
            "site_id": inspection.site_id,
            "area_id": inspection.area_id,
            "result_id": result.pk,
            "item_label": result.template_item.item_label,
        },
    )
    create_notification(
        recipient=actor,
        title=f"Failed inspection item: {result.template_item.item_label}",
        body=f"{inspection.site.name} {inspection.area.area_name} — {result.template_item.item_label} failed inspection on {inspection.inspection_date}.",
        entity_type="inspection",
        entity_id=str(inspection.pk),
    )
