"""Human-resources onboarding and workforce-import services."""
from __future__ import annotations

import hashlib
import io
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction
from openpyxl import Workbook, load_workbook
from openpyxl.formatting.rule import FormulaRule
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.worksheet.table import Table, TableStyleInfo

from apps.accounts.models import RoleCode, User
from apps.core.models import AuditLog
from apps.core.services import model_data, record_audit

from .models import (
    Cleaner,
    CleanerAssignmentStatus,
    CleanerAssignmentType,
    CleanerStatus,
    Gender,
    IdType,
    Site,
    TraineeProgram,
)
from .trainee_services import start_trainee_program

HEADERS = [
    "first_name", "last_name", "id_type", "id_number", "gender", "birth_date", "living_location",
    "phone_number", "near_person_name", "near_person_relationship", "near_person_phone", "registration_date",
    "site_code", "assignment_type", "shift_name", "notes",
]
REQUIRED = {"first_name", "last_name", "id_type", "id_number", "gender", "birth_date", "registration_date"}


def build_cleaner_workbook_template() -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Cleaners"
    sheet.append(HEADERS)
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = "A1:P201"
    for column, width in {"A": 18, "B": 18, "C": 20, "D": 22, "E": 14, "F": 14, "G": 24, "H": 18, "I": 20, "J": 20, "K": 18, "L": 16, "M": 16, "N": 18, "O": 18, "P": 30}.items():
        sheet.column_dimensions[column].width = width
    for cell in sheet[1]:
        cell.font = cell.font.copy(bold=True, color="FFFFFF")
        cell.fill = cell.fill.copy(fill_type="solid", fgColor="0F7667")
    table = Table(displayName="CleanerOnboardingRows", ref="A1:P201")
    table.tableStyleInfo = TableStyleInfo(name="TableStyleMedium4", showRowStripes=True, showColumnStripes=False)
    sheet.add_table(table)

    reference = workbook.create_sheet("ReferenceData")
    reference.sheet_state = "hidden"
    lists = {
        "A": ("id_type", [item.value for item in IdType]),
        "B": ("gender", [item.value for item in Gender]),
        "C": ("assignment_type", [item.value for item in CleanerAssignmentType]),
    }
    for column, (label, values) in lists.items():
        reference[f"{column}1"] = label
        for index, value in enumerate(values, 2):
            reference[f"{column}{index}"] = value
    instructions = workbook.create_sheet("Instructions", 0)
    instructions.append(["White Bird HR Cleaner Onboarding Workbook"])
    instructions.append(["Complete the Cleaners sheet. New records are always created as trainees."])
    instructions.append(["Use the dropdowns for id_type, gender, and assignment_type. Dates must be YYYY-MM-DD."])
    instructions.append(["site_code and shift_name are validated again by the server. Do not edit the hidden ReferenceData sheet."])
    instructions.append(["Upload is preview-first: invalid rows are rejected before any database changes are made."])
    for row in instructions.iter_rows():
        row[0].alignment = row[0].alignment.copy(wrap_text=True)
    instructions.column_dimensions["A"].width = 110

    validations = [
        DataValidation(type="list", formula1="=ReferenceData!$A$2:$A$4", allow_blank=False),
        DataValidation(type="list", formula1="=ReferenceData!$B$2:$B$5", allow_blank=False),
        DataValidation(type="list", formula1="=ReferenceData!$C$2:$C$3", allow_blank=True),
        DataValidation(type="date", operator="between", formula1="DATE(1940,1,1)", formula2="TODAY()", allow_blank=False),
    ]
    for validation in validations:
        sheet.add_data_validation(validation)
    validations[0].add("C2:C201")
    validations[1].add("E2:E201")
    validations[2].add("N2:N201")
    validations[3].add("F2:F201")
    validations[3].add("L2:L201")
    sheet.conditional_formatting.add("A2:P201", FormulaRule(formula=["COUNTIF($D$2:$D$201,$D2)>1"], fill=sheet["A2"].fill.copy(fill_type="solid", fgColor="FCE4D6")))
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def _normalise(value: Any) -> str:
    return str(value or "").strip()


def _parse_date(value: Any, field: str, row_number: int) -> date:
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(_normalise(value))
    except ValueError as exc:
        raise ValidationError(f"Row {row_number}: {field} must be a valid YYYY-MM-DD date.") from exc


def _rows(uploaded_file: Any) -> tuple[list[dict[str, Any]], str]:
    raw = uploaded_file.read()
    file_hash = hashlib.sha256(raw).hexdigest()
    workbook = load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
    if "Cleaners" not in workbook.sheetnames:
        raise ValidationError("Workbook must contain a Cleaners sheet.")
    sheet = workbook["Cleaners"]
    headers = [_normalise(value).lower() for value in next(sheet.iter_rows(min_row=1, max_row=1, values_only=True))]
    if headers != HEADERS:
        raise ValidationError("Cleaners sheet headers do not match the current White Bird template.")
    rows: list[dict[str, Any]] = []
    for row_number, values in enumerate(sheet.iter_rows(min_row=2, values_only=True), 2):
        if not any(value not in (None, "") for value in values):
            continue
        row = dict(zip(HEADERS, values, strict=False))
        row["_row_number"] = row_number
        rows.append(row)
    return rows, file_hash


def _validate_row(row: dict[str, Any], *, seen_ids: set[tuple[str, str]]) -> tuple[dict[str, Any] | None, list[str]]:
    number = int(row["_row_number"])
    errors: list[str] = []
    cleaned = {key: _normalise(value) for key, value in row.items() if not key.startswith("_")}
    for field in REQUIRED:
        if not cleaned.get(field):
            errors.append(f"{field} is required")
    if cleaned.get("id_type") and cleaned["id_type"] not in {item.value for item in IdType}:
        errors.append("id_type is not an allowed value")
    if cleaned.get("gender") and cleaned["gender"] not in {item.value for item in Gender}:
        errors.append("gender is not an allowed value")
    if cleaned.get("assignment_type") and cleaned["assignment_type"] not in {item.value for item in CleanerAssignmentType}:
        errors.append("assignment_type is not an allowed value")
    if cleaned.get("id_type") and cleaned.get("id_number"):
        key = (cleaned["id_type"], cleaned["id_number"].upper())
        if key in seen_ids:
            errors.append("duplicate identity appears more than once in this workbook")
        seen_ids.add(key)
    for field in ("birth_date", "registration_date"):
        if cleaned.get(field):
            try:
                cleaned[field] = _parse_date(row[field], field, number)
            except ValidationError as exc:
                errors.append(str(exc))
    return (cleaned if not errors else None), errors


def preview_cleaner_workbook(uploaded_file: Any) -> dict[str, Any]:
    rows, file_hash = _rows(uploaded_file)
    accepted: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for row in rows:
        cleaned, row_errors = _validate_row(row, seen_ids=seen)
        if row_errors:
            errors.append({"row": row["_row_number"], "errors": row_errors})
        else:
            accepted.append({"row": row["_row_number"], "data": cleaned})
    return {"file_hash": file_hash, "total_rows": len(rows), "accepted_rows": len(accepted), "rejected_rows": len(errors), "accepted": accepted, "errors": errors}


def import_cleaner_workbook(*, uploaded_file: Any, actor: User) -> dict[str, Any]:
    preview = preview_cleaner_workbook(uploaded_file)
    if preview["rejected_rows"]:
        return {**preview, "committed": False, "message": "Import stopped. Correct all rejected rows and upload again."}
    created: list[int] = []
    updated: list[int] = []
    assignment_results: list[dict[str, Any]] = []
    with transaction.atomic():
        for item in preview["accepted"]:
            data = dict(item["data"])
            row_number = item["row"]
            identity = {"id_type": data.pop("id_type"), "id_number": data.pop("id_number").upper()}
            site_code = data.pop("site_code", "")
            assignment_type = data.pop("assignment_type", "")
            shift_name = data.pop("shift_name", "")
            cleaner, was_created = Cleaner.objects.get_or_create(
                **identity,
                defaults={**data, "status": CleanerStatus.TRAINEE, "created_by": actor, "updated_by": actor},
            )
            if was_created:
                created.append(cleaner.pk)
            else:
                updated.append(cleaner.pk)
            if site_code:
                site = Site.objects.filter(code=site_code, is_active=True).first()
                if site is None:
                    raise ValidationError(f"Row {row_number}: site_code '{site_code}' does not exist or is inactive.")
                if not cleaner.trainee_programs.filter(status__in=["in_training", "extended"]).exists():
                    start_trainee_program(cleaner=cleaner, site=site, expected_end_date=date.today() + timedelta(days=90), actor=actor, notes=f"Created from HR workbook row {row_number}.")
                assignment_results.append({"row": row_number, "cleaner_id": cleaner.pk, "site_id": site.pk, "status": "trainee_program_started"})
        record_audit(action=AuditLog.Action.CREATE, actor=actor, entity=actor, summary=f"Imported HR cleaner workbook {preview['file_hash']} ({len(created)} created, {len(updated)} matched)", after_data={"file_hash": preview["file_hash"], "created": created, "updated": updated, "assignments": assignment_results})
    return {**preview, "committed": True, "created_cleaner_ids": created, "matched_cleaner_ids": updated, "assignment_results": assignment_results, "message": "HR workbook imported successfully. New cleaners remain trainees until qualification."}
