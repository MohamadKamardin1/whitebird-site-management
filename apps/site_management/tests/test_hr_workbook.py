from __future__ import annotations

import io

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from openpyxl import load_workbook

from apps.accounts.models import RoleCode
from apps.site_management.hr_services import build_cleaner_workbook_template, preview_cleaner_workbook


def test_role_codes_include_hr_and_store_manager() -> None:
    assert RoleCode.HR.value == "hr"
    assert RoleCode.STORE_MANAGER.value == "store_manager"


def test_hr_template_contains_instructions_reference_data_and_validations() -> None:
    content = build_cleaner_workbook_template()
    workbook = load_workbook(io.BytesIO(content))
    assert workbook.sheetnames == ["Instructions", "Cleaners", "ReferenceData"]
    assert workbook["ReferenceData"].sheet_state == "hidden"
    assert len(workbook["Cleaners"].data_validations.dataValidation) >= 4
    assert workbook["Cleaners"]["A1"].value == "first_name"


def test_hr_preview_returns_row_level_errors_without_committing() -> None:
    workbook = load_workbook(io.BytesIO(build_cleaner_workbook_template()))
    sheet = workbook["Cleaners"]
    sheet.append(["Asha", "Mussa", "bad_id_type", "ID-1", "female", "1990-01-01", "Stone Town", "", "", "", "", "2026-08-16", "", "", "", ""])
    buffer = io.BytesIO()
    workbook.save(buffer)
    uploaded = SimpleUploadedFile("invalid.xlsx", buffer.getvalue(), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    result = preview_cleaner_workbook(uploaded)
    assert result["total_rows"] == 1
    assert result["accepted_rows"] == 0
    assert result["rejected_rows"] == 1
    assert "id_type is not an allowed value" in result["errors"][0]["errors"]
