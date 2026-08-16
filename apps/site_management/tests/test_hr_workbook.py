from __future__ import annotations

import io

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from openpyxl import load_workbook

from apps.accounts.factories import UserFactory
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
    sheet.append(
        [
            "Asha",
            "Mussa",
            "bad_id_type",
            "ID-1",
            "female",
            "1990-01-01",
            "Stone Town",
            "",
            "",
            "",
            "",
            "2026-08-16",
            "",
            "",
            "",
            "",
        ]
    )
    buffer = io.BytesIO()
    workbook.save(buffer)
    uploaded = SimpleUploadedFile(
        "invalid.xlsx",
        buffer.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    result = preview_cleaner_workbook(uploaded)
    assert result["total_rows"] == 1
    assert result["accepted_rows"] == 0
    assert result["rejected_rows"] == 1
    assert "id_type is not an allowed value" in result["errors"][0]["errors"]


def _workbook_with_row(row: list[object]) -> SimpleUploadedFile:
    import io

    from openpyxl import load_workbook

    wb = load_workbook(io.BytesIO(build_cleaner_workbook_template()))
    wb["Cleaners"].append(row)
    buffer = io.BytesIO()
    wb.save(buffer)
    return SimpleUploadedFile(
        "cleaners.xlsx",
        buffer.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


_VALID_ROW = [
    "Fatma",
    "Ali",
    "nida",
    "HRNA0001",
    "female",
    "1991-05-05",
    "Stone Town",
    "+255700000001",
    "Omar",
    "Brother",
    "+255700000002",
    "2026-08-16",
    "",
    "",
    "",
    "",
]


@pytest.mark.django_db(transaction=True)
def test_hr_preview_accepts_valid_row() -> None:
    result = preview_cleaner_workbook(_workbook_with_row(list(_VALID_ROW)))
    assert result["total_rows"] == 1
    assert result["accepted_rows"] == 1
    assert result["rejected_rows"] == 0


@pytest.mark.django_db(transaction=True)
def test_hr_import_creates_cleaner_and_trainee(site, admin_user) -> None:
    from apps.site_management.hr_services import import_cleaner_workbook
    from apps.site_management.models import Cleaner, TraineeProgram

    row = list(_VALID_ROW)
    row[12] = site.code
    row[13] = "full_time"
    result = import_cleaner_workbook(uploaded_file=_workbook_with_row(row), actor=admin_user)
    assert result["committed"] is True
    assert len(result["created_cleaner_ids"]) == 1
    cleaner = Cleaner.objects.get(id_number="HRNA0001")
    assert cleaner.status == "trainee"
    assert TraineeProgram.objects.filter(cleaner=cleaner).exists()


@pytest.mark.django_db(transaction=True)
def test_hr_import_rejects_duplicates_and_bad_dates() -> None:
    from apps.site_management.hr_services import import_cleaner_workbook
    from apps.site_management.models import Cleaner

    # Two identical identities -> the duplicate is rejected on preview.
    wb = load_workbook(io.BytesIO(build_cleaner_workbook_template()))
    wb["Cleaners"].append(_VALID_ROW)
    wb["Cleaners"].append(_VALID_ROW)
    buffer = io.BytesIO()
    wb.save(buffer)
    preview = preview_cleaner_workbook(
        SimpleUploadedFile(
            "dup.xlsx",
            buffer.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    )
    assert preview["accepted_rows"] == 1
    assert preview["rejected_rows"] == 1

    # Invalid date -> rejected, and a rejected preview blocks import.
    bad = list(_VALID_ROW)
    bad[5] = "not-a-date"
    result = preview_cleaner_workbook(_workbook_with_row(bad))
    assert result["rejected_rows"] == 1
    imported = import_cleaner_workbook(
        uploaded_file=_workbook_with_row(bad), actor=UserFactory(role=RoleCode.SYSTEM_ADMIN)
    )
    assert imported["committed"] is False
    assert not Cleaner.objects.filter(id_number="HRNA0001").exists()


@pytest.mark.django_db(transaction=True)
def test_hr_import_unknown_site_code_raises(admin_user) -> None:
    from django.core.exceptions import ValidationError

    from apps.site_management.hr_services import import_cleaner_workbook

    row = list(_VALID_ROW)
    row[12] = "NO-SUCH-SITE"
    with pytest.raises(ValidationError):
        import_cleaner_workbook(uploaded_file=_workbook_with_row(row), actor=admin_user)
