"""Focused coverage for long-tail branches (report delivery, exports, policies)."""

from datetime import date
from unittest.mock import patch
from urllib.error import HTTPError

import pytest
from django.test import Client, override_settings

from apps.accounts.factories import UserFactory
from apps.accounts.models import RoleCode
from apps.accounts.services import issue_api_token
from apps.site_management.factories import (
    CleanerFactory,
    SiteFactory,
    SiteSupervisorAssignmentFactory,
)
from apps.site_management.models import (
    CleanerAssignmentStatus,
    CleanerSiteAssignment,
    CleanerStatus,
    GeneralManagementReport,
    Issue,
    IssueSource,
)


@pytest.fixture(autouse=True)
def rbac_seeded(db: None) -> None:
    from django.core.management import call_command

    call_command("seed_rbac")


def _authed(user: object) -> Client:
    return Client(HTTP_AUTHORIZATION=f"Bearer {issue_api_token(user=user, name='t').key}")


# --------------------------------------------------------------------------- #
# report_delivery long-tail branches
# --------------------------------------------------------------------------- #


def test_report_delivery_safe_helper() -> None:
    from apps.site_management.report_delivery import _safe

    assert _safe(None) == "—"
    assert _safe("") == "—"
    assert _safe("plain_text") == "plain text"
    assert _safe({"present": 1, "late": 2}) == "present: 1 · late: 2"
    assert _safe([]) == "—"
    assert _safe([1, 2, 3]) == "3 items"


def test_report_delivery_unknown_type_raises() -> None:
    from apps.site_management.report_delivery import _period_window

    with pytest.raises(ValueError):
        _period_window("quarterly", date(2026, 8, 15))


@override_settings(RESEND_API_KEY="re_test_key")
@patch("apps.site_management.report_delivery.urlopen", side_effect=HTTPError("url", 500, "boom", None, None))
def test_report_delivery_send_error(mock_urlopen) -> None:
    from apps.site_management.report_delivery import _send_resend

    with pytest.raises(RuntimeError, match="Resend delivery failed"):
        _send_resend(subject="s", filename="f.pdf", content=b"%PDF", recipient="a@b.co")
    assert mock_urlopen.called


# --------------------------------------------------------------------------- #
# exports — filter branches
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
def test_export_attendance_and_reports_filters(site, admin_user) -> None:
    from apps.site_management.export_services import attendance_export_rows, report_export_rows

    filename, rows = attendance_export_rows(admin_user, date_from=date.today(), date_to=date.today())
    assert filename.startswith("attendance-")
    assert '"date"' in next(rows)

    filename, rows = report_export_rows(admin_user, report_date=date.today())
    assert filename.startswith("reports-")
    assert '"report_date"' in next(rows)


@pytest.mark.django_db
def test_export_cleaner_scoped_for_viewer(site, viewer_user, admin_user) -> None:
    from apps.site_management.export_services import cleaner_export_rows

    cleaner = CleanerFactory(status=CleanerStatus.ACTIVE)
    CleanerSiteAssignment.objects.create(
        cleaner=cleaner,
        site=site,
        assignment_type="full_time",
        start_date=date.today(),
        status=CleanerAssignmentStatus.ACTIVE,
    )
    filename, rows = cleaner_export_rows(viewer_user)
    header = next(rows)
    body = list(rows)
    assert header.startswith('"first_name"')
    # Viewer is management-role scoped (all sites visible) so the cleaner appears.
    assert any("Cleaner" in row for row in body)


# --------------------------------------------------------------------------- #
# policies — remaining branches
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
def test_policy_branches(site, admin_user, zone_user, viewer_user, general_user) -> None:
    from apps.site_management.models import Zone
    from apps.site_management.policies import (
        can_create_inspection,
        can_export_data,
        can_record_attendance,
        can_view_management_report,
        can_view_zone,
    )

    zone = Zone.objects.create(name="Z", code="Z1")
    assert can_view_zone(zone_user, zone) is False
    assert can_view_zone(general_user, zone) is True
    assert can_record_attendance(admin_user, site, date.today()) is True
    assert can_create_inspection(admin_user, site) is True

    report = GeneralManagementReport(report_date=date.today())
    assert can_view_management_report(viewer_user, report) is True
    assert can_export_data(viewer_user, "issues") is True
    assert can_export_data(general_user, "issues") is True


@pytest.mark.django_db
def test_cleaner_list_site_supervisor_scoping(site, admin_user) -> None:
    from apps.site_management.cleaner_selectors import cleaner_list_queryset

    cleaner = CleanerFactory(status=CleanerStatus.ACTIVE)
    CleanerSiteAssignment.objects.create(
        cleaner=cleaner,
        site=site,
        assignment_type="full_time",
        start_date=date.today(),
        status=CleanerAssignmentStatus.ACTIVE,
    )
    other = SiteFactory()
    unassigned = CleanerFactory(status=CleanerStatus.ACTIVE)

    sup = UserFactory(role=RoleCode.SITE_SUPERVISOR)
    SiteSupervisorAssignmentFactory(site=site, user=sup)
    spec = type("S", (), {"search": None, "status": None, "id_type": None, "gender": None})()
    qs = cleaner_list_queryset(sup, spec)
    ids = set(qs.values_list("pk", flat=True))
    assert cleaner.pk in ids
    assert unassigned.pk not in ids


@pytest.mark.django_db
def test_export_attendance_day_param(site, admin_user) -> None:
    from apps.site_management.export_services import attendance_export_rows

    filename, rows = attendance_export_rows(admin_user, day=date.today())
    assert filename.startswith("attendance-")
    assert '"date"' in next(rows)


@pytest.mark.django_db
def test_export_issues_jobs(site, admin_user) -> None:
    from apps.site_management.export_services import issue_export_rows, job_export_rows

    Issue.objects.create(title="E", site=site, source=IssueSource.MANUAL, issue_category="other", raised_by=admin_user)
    _, irows = issue_export_rows(admin_user)
    assert '"id"' in next(irows)
    _, jrows = job_export_rows(admin_user)
    assert '"job_title"' in next(jrows)


@pytest.mark.django_db
def test_ai_integrity_checks_branches(admin_user) -> None:
    from apps.site_management.ai_optimization import _integrity_checks

    kpis = {
        "missing_site_reports": 2,
        "low_stock_items": 3,
        "open_issues": 1,
        "overdue_jobs": 2,
        "escalated_issues": 1,
        "attendance_rate": 50,
    }
    checks = _integrity_checks(user=admin_user, day=date.today(), kpis=kpis, site_count=1)
    codes = {check["code"] for check in checks}
    assert "missing_daily_reports" in codes
    assert "low_stock_items" in codes
    assert "attendance_rate_below_standard" in codes


@pytest.mark.django_db
def test_attendance_submit_blocks_unmarked(site, admin_user) -> None:
    from django.core.exceptions import ValidationError

    from apps.site_management.attendance_services import generate_daily_attendance_sheet, submit_daily_attendance

    cleaner = CleanerFactory(status=CleanerStatus.ACTIVE)
    CleanerSiteAssignment.objects.create(
        cleaner=cleaner,
        site=site,
        assignment_type="full_time",
        start_date=date.today(),
        status=CleanerAssignmentStatus.ACTIVE,
    )
    generate_daily_attendance_sheet(site_id=site.pk, day=date.today(), actor=admin_user)
    with pytest.raises(ValidationError):
        submit_daily_attendance(site_id=site.pk, day=date.today(), user=admin_user)
