from __future__ import annotations

from datetime import date

import pytest
from django.core.exceptions import ValidationError
from django.test import Client
from django.utils import timezone

from apps.accounts.factories import UserFactory
from apps.accounts.models import RoleCode, User
from apps.accounts.services import issue_api_token
from apps.core.models import AuditLog
from apps.site_management.factories import AttendanceRecordFactory, CleanerFactory, CleanerSiteAssignmentFactory, SiteFactory, SiteSupervisorAssignmentFactory
from apps.site_management.models import AttendanceStatus, CleanerPaymentProfile, MonthlyRemunerationReport
from apps.site_management.remuneration_services import prepare_monthly_remuneration, remuneration_window_is_open


def _authed(user: User) -> Client:
    return Client(HTTP_AUTHORIZATION=f"Bearer {issue_api_token(user=user, name='remuneration').key}")


@pytest.mark.django_db
def test_remuneration_window_is_limited_to_days_15_through_25() -> None:
    assert remuneration_window_is_open(today=date(2026, 8, 15)) is True
    assert remuneration_window_is_open(today=date(2026, 8, 25)) is True
    assert remuneration_window_is_open(today=date(2026, 8, 14)) is False
    assert remuneration_window_is_open(today=date(2026, 8, 26)) is False


@pytest.mark.django_db
def test_monthly_remuneration_prefills_scoped_attendance_and_applies_reviewed_payment_changes() -> None:
    today = timezone.localdate()
    period = today.replace(day=1)
    site = SiteFactory()
    other_site = SiteFactory()
    supervisor = UserFactory(role=RoleCode.SITE_SUPERVISOR)
    SiteSupervisorAssignmentFactory(site=site, user=supervisor)
    cleaner = CleanerFactory(status="active")
    assignment = CleanerSiteAssignmentFactory(cleaner=cleaner, site=site, status="active", start_date=today)
    other_cleaner = CleanerFactory(status="active")
    CleanerSiteAssignmentFactory(cleaner=other_cleaner, site=other_site, status="active", start_date=today)
    AttendanceRecordFactory(cleaner=cleaner, site=site, attendance_date=today, status=AttendanceStatus.PRESENT)
    AttendanceRecordFactory(cleaner=cleaner, site=site, attendance_date=today.replace(day=max(1, today.day - 1)), status=AttendanceStatus.LATE)
    AttendanceRecordFactory(cleaner=cleaner, site=site, attendance_date=today.replace(day=max(1, today.day - 2)), status=AttendanceStatus.ABSENT)
    CleanerPaymentProfile.objects.create(cleaner=cleaner, yas_zantel_phone="0777000000", pbz_account_number="PBZ-OLD-123", created_by=supervisor, updated_by=supervisor)

    report = prepare_monthly_remuneration(actor=supervisor, site=site, period=period, today=today)
    assert report.lines.count() == 1
    line = report.lines.get()
    assert line.assignment_id == assignment.pk
    assert line.present_days == 2
    assert line.absent_days == 1
    assert line.start_work_date == today

    client = _authed(supervisor)
    detail = client.get(f"/api/site-management/v1/remuneration/sites/{site.pk}?period={period.isoformat()}")
    assert detail.status_code == 200, detail.content
    row = detail.json()["lines"][0]
    assert row["last_phone_masked"].endswith("000")
    assert "0777000000" not in row["last_phone_masked"]
    assert row["last_account_masked"].endswith("123")

    updated = client.patch(
        f"/api/site-management/v1/remuneration/reports/{report.pk}/lines/{line.pk}",
        data={"proposed_yas_zantel_phone": "0777111111", "proposed_pbz_account_number": "PBZ-NEW-456"},
        content_type="application/json",
    )
    assert updated.status_code == 200, updated.content
    submitted = client.post(f"/api/site-management/v1/remuneration/reports/{report.pk}/submit")
    assert submitted.status_code == 200, submitted.content
    assert submitted.json()["status"] == "submitted"
    report.refresh_from_db()
    assert report.snapshot["form_heading"] == "FOMU. TAARIFA ZA WAFANYAKAZI KWA AJILI YA MALIPO(MWEZI)"

    hr = UserFactory(role=RoleCode.HR)
    reviewed = _authed(hr).post(
        f"/api/site-management/v1/remuneration/reports/{report.pk}/review",
        data={"action": "reviewed", "reason": ""},
        content_type="application/json",
    )
    assert reviewed.status_code == 200, reviewed.content
    profile = CleanerPaymentProfile.objects.get(cleaner=cleaner)
    assert profile.yas_zantel_phone == "0777111111"
    assert profile.pbz_account_number == "PBZ-NEW-456"
    assert AuditLog.objects.filter(summary__contains="Approved remuneration payment-contact update").exists()

    with pytest.raises(ValidationError):
        prepare_monthly_remuneration(actor=supervisor, site=site, period=period, today=period.replace(day=14))
    assert MonthlyRemunerationReport.objects.filter(site=other_site).count() == 0
