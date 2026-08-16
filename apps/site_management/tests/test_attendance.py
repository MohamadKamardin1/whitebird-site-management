"""Tests for the attendance engine."""

from datetime import date, time, timedelta

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import Client

from apps.accounts.factories import UserFactory
from apps.accounts.models import RoleCode, User
from apps.accounts.services import issue_api_token
from apps.site_management.attendance_selectors import (
    AttendanceFilter,
    attendance_history_queryset,
    attendance_summary,
    missing_attendance_sites,
)
from apps.site_management.attendance_services import (
    bulk_upsert_attendance,
    generate_daily_attendance_sheet,
    lock_attendance_if_required,
    record_single_attendance,
    return_attendance_group,
    return_attendance_record,
    review_attendance_group,
    review_attendance_record,
    submit_daily_attendance,
)
from apps.site_management.factories import (
    AttendanceRecordFactory,
    CleanerFactory,
    CleanerShiftAssignmentFactory,
    SiteFactory,
    SiteShiftFactory,
)
from apps.site_management.models import (
    AttendanceRecord,
    AttendanceReviewStatus,
    AttendanceStatus,
    CleanerAssignmentType,
    CleanerSiteAssignment,
    CleanerStatus,
    WorkMode,
)


@pytest.fixture(autouse=True)
def rbac_seeded(db: None) -> None:
    from django.core.management import call_command

    call_command("seed_rbac")


def _authed(user: User) -> Client:
    return Client(HTTP_AUTHORIZATION=f"Bearer {issue_api_token(user=user, name='test').key}")


def _active_cleaner() -> CleanerFactory:
    return CleanerFactory(status=CleanerStatus.ACTIVE)


def _assign(site, cleaner, atype="full_time", actor=None) -> CleanerSiteAssignment:
    from apps.site_management.assignment_services import assign_cleaner_to_site

    return assign_cleaner_to_site(
        cleaner=cleaner,
        site=site,
        assignment_type=CleanerAssignmentType(atype),
        start_date=date(2026, 1, 1),
        actor=actor or UserFactory(role=RoleCode.SYSTEM_ADMIN),
    )


# --------------------------------------------------------------------------- #
# Generation
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
def test_generate_full_time_sheet(site, admin_user) -> None:
    cleaner = _active_cleaner()
    _assign(site, cleaner, actor=admin_user)
    records = generate_daily_attendance_sheet(site_id=site.pk, day=date(2026, 3, 1), actor=admin_user)
    assert len(records) == 1
    assert records[0].status == AttendanceStatus.SCHEDULED
    assert records[0].review_status == AttendanceReviewStatus.DRAFT


@pytest.mark.django_db
def test_generate_is_idempotent(site, admin_user) -> None:
    cleaner = _active_cleaner()
    _assign(site, cleaner, actor=admin_user)
    generate_daily_attendance_sheet(site_id=site.pk, day=date(2026, 3, 1), actor=admin_user)
    generate_daily_attendance_sheet(site_id=site.pk, day=date(2026, 3, 1), actor=admin_user)
    assert AttendanceRecord.objects.filter(site=site, attendance_date=date(2026, 3, 1)).count() == 1


@pytest.mark.django_db
def test_generate_shift_sheet_per_shift(site, admin_user) -> None:
    site.work_mode = WorkMode.FULL_TIME_AND_SHIFT
    site.save(update_fields=["work_mode"])
    shift_a = SiteShiftFactory(site=site)
    shift_b = SiteShiftFactory(site=site, shift_name="Evening")
    cleaner = _active_cleaner()
    assignment = _assign(site, cleaner, atype="shift", actor=admin_user)
    CleanerShiftAssignmentFactory(assignment=assignment, shift=shift_a, effective_from=date(2026, 1, 1))
    CleanerShiftAssignmentFactory(assignment=assignment, shift=shift_b, effective_from=date(2026, 1, 1))
    records = generate_daily_attendance_sheet(site_id=site.pk, day=date(2026, 3, 1), actor=admin_user)
    shifts = {r.shift_id for r in records}
    assert shifts == {shift_a.pk, shift_b.pk}
    assert len(records) == 2

    filtered = generate_daily_attendance_sheet(
        site_id=site.pk, day=date(2026, 3, 1), shift_id=shift_a.pk, actor=admin_user
    )
    assert len(filtered) == 1


@pytest.mark.django_db
def test_duplicate_records_prevented_by_constraint(site, admin_user) -> None:
    cleaner = _active_cleaner()
    _assign(site, cleaner, actor=admin_user)
    AttendanceRecordFactory(cleaner=cleaner, site=site, attendance_date=date(2026, 3, 1), status="present")
    with pytest.raises(IntegrityError):
        AttendanceRecordFactory(cleaner=cleaner, site=site, attendance_date=date(2026, 3, 1))


@pytest.mark.django_db
def test_overnight_checkout_allowed(site, admin_user) -> None:
    cleaner = _active_cleaner()
    _assign(site, cleaner, actor=admin_user)
    generate_daily_attendance_sheet(site_id=site.pk, day=date(2026, 3, 1), actor=admin_user)
    record = AttendanceRecord.objects.get(site=site, attendance_date=date(2026, 3, 1))
    updated = record_single_attendance(
        record_id=record.pk,
        status=AttendanceStatus.PRESENT,
        user=admin_user,
        check_in_time=time(22, 0),
        check_out_time=time(6, 0),
    )
    assert updated.check_out_time == time(6, 0)  # next-day checkout for overnight


@pytest.mark.django_db
def test_future_date_rejected(site, admin_user) -> None:
    cleaner = _active_cleaner()
    _assign(site, cleaner, actor=admin_user)
    generate_daily_attendance_sheet(site_id=site.pk, day=date.today(), actor=admin_user)
    with pytest.raises(ValidationError):
        bulk_upsert_attendance(
            site_id=site.pk,
            day=date.today() + timedelta(days=1),
            entries=[{"cleaner_id": cleaner.pk, "status": "present"}],
            user=admin_user,
        )


# --------------------------------------------------------------------------- #
# Bulk entry & workflow
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
def test_bulk_upsert_and_submit_flow(site, admin_user) -> None:
    cleaner = _active_cleaner()
    _assign(site, cleaner, actor=admin_user)
    generate_daily_attendance_sheet(site_id=site.pk, day=date(2026, 4, 1), actor=admin_user)

    # Not all scheduled marked -> cannot submit.
    with pytest.raises(ValidationError):
        submit_daily_attendance(site_id=site.pk, day=date(2026, 4, 1), user=admin_user)

    records = bulk_upsert_attendance(
        site_id=site.pk,
        day=date(2026, 4, 1),
        entries=[{"cleaner_id": cleaner.pk, "status": "present", "check_in_time": "08:00:00"}],
        user=admin_user,
    )
    assert records[0].status == AttendanceStatus.PRESENT

    submitted = submit_daily_attendance(site_id=site.pk, day=date(2026, 4, 1), user=admin_user)
    assert submitted == 1
    record = AttendanceRecord.objects.get(site=site, attendance_date=date(2026, 4, 1))
    assert record.review_status == AttendanceReviewStatus.SUBMITTED

    # Submitted records are no longer editable.
    with pytest.raises(ValidationError):
        bulk_upsert_attendance(
            site_id=site.pk,
            day=date(2026, 4, 1),
            entries=[{"record_id": record.pk, "status": "absent"}],
            user=admin_user,
        )


@pytest.mark.django_db
def test_return_then_edit_then_submit(site, admin_user) -> None:
    cleaner = _active_cleaner()
    _assign(site, cleaner, actor=admin_user)
    generate_daily_attendance_sheet(site_id=site.pk, day=date(2026, 5, 1), actor=admin_user)
    bulk_upsert_attendance(
        site_id=site.pk,
        day=date(2026, 5, 1),
        entries=[{"cleaner_id": cleaner.pk, "status": "late"}],
        user=admin_user,
    )
    submit_daily_attendance(site_id=site.pk, day=date(2026, 5, 1), user=admin_user)
    record = AttendanceRecord.objects.get(site=site, attendance_date=date(2026, 5, 1))

    returned = return_attendance_record(record=record, user=admin_user, reason="Wrong status")
    assert returned.review_status == AttendanceReviewStatus.RETURNED
    assert returned.return_reason == "Wrong status"

    bulk_upsert_attendance(
        site_id=site.pk,
        day=date(2026, 5, 1),
        entries=[{"record_id": record.pk, "status": "sick"}],
        user=admin_user,
    )
    record.refresh_from_db()
    assert record.status == AttendanceStatus.SICK

    returned_group = return_attendance_group(
        site_id=site.pk, day=date(2026, 5, 1), user=admin_user, reason="Re-returned"
    )
    assert returned_group >= 1


@pytest.mark.django_db
def test_review_and_lock_workflow(site, admin_user) -> None:
    today = date.today()
    cleaner = _active_cleaner()
    _assign(site, cleaner, actor=admin_user)
    generate_daily_attendance_sheet(site_id=site.pk, day=today, actor=admin_user)
    bulk_upsert_attendance(
        site_id=site.pk,
        day=today,
        entries=[{"cleaner_id": cleaner.pk, "status": "present"}],
        user=admin_user,
    )
    submit_daily_attendance(site_id=site.pk, day=today, user=admin_user)
    record = AttendanceRecord.objects.get(site=site, attendance_date=today)

    reviewed = review_attendance_record(record=record, user=admin_user)
    assert reviewed.review_status == AttendanceReviewStatus.REVIEWED

    # Auto-lock applies to reviewed records older than the window.
    old = AttendanceRecordFactory(
        cleaner=cleaner,
        site=site,
        attendance_date=date(2020, 1, 1),
        status="present",
        review_status=AttendanceReviewStatus.REVIEWED,
    )
    locked = lock_attendance_if_required(site_id=site.pk, day=date(2020, 1, 1), user=admin_user)
    assert locked == 1
    old.refresh_from_db()
    assert old.review_status == AttendanceReviewStatus.LOCKED

    # Locked records cannot be returned.
    with pytest.raises(ValidationError):
        return_attendance_record(record=old, user=admin_user, reason="x")


@pytest.mark.django_db
def test_review_group_and_lock_on_review(site, admin_user) -> None:
    cleaner = _active_cleaner()
    _assign(site, cleaner, actor=admin_user)
    generate_daily_attendance_sheet(site_id=site.pk, day=date(2026, 7, 1), actor=admin_user)
    bulk_upsert_attendance(
        site_id=site.pk,
        day=date(2026, 7, 1),
        entries=[{"cleaner_id": cleaner.pk, "status": "present"}],
        user=admin_user,
    )
    submit_daily_attendance(site_id=site.pk, day=date(2026, 7, 1), user=admin_user)
    reviewed = review_attendance_group(site_id=site.pk, day=date(2026, 7, 1), user=admin_user)
    assert reviewed == 1


# --------------------------------------------------------------------------- #
# Selectors & summary
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
def test_summary_calculations(site, admin_user) -> None:
    c1 = _active_cleaner()
    _assign(site, c1, actor=admin_user)
    generate_daily_attendance_sheet(site_id=site.pk, day=date(2026, 8, 1), actor=admin_user)
    bulk_upsert_attendance(
        site_id=site.pk,
        day=date(2026, 8, 1),
        entries=[{"cleaner_id": c1.pk, "status": "present"}],
        user=admin_user,
    )
    AttendanceRecordFactory(cleaner=_active_cleaner(), site=site, attendance_date=date(2026, 8, 1), status="late")
    AttendanceRecordFactory(cleaner=_active_cleaner(), site=site, attendance_date=date(2026, 8, 1), status="absent")
    AttendanceRecordFactory(cleaner=_active_cleaner(), site=site, attendance_date=date(2026, 8, 1), status="sick")
    summary = attendance_summary(admin_user, AttendanceFilter(site_id=site.pk, date=date(2026, 8, 1)))
    assert summary["present"] == 1
    assert summary["late"] == 1
    assert summary["absent"] == 1
    assert summary["sick"] == 1
    assert summary["attendance_rate"] == 66.67  # (1+1)/(1+1+1)


@pytest.mark.django_db
def test_history_filters_and_scoping(site, admin_user, zone_user) -> None:
    from apps.site_management.assignment_services import assign_cleaner_to_site
    from apps.site_management.factories import ZoneSupervisorAssignmentFactory

    c = _active_cleaner()
    assign_cleaner_to_site(
        cleaner=c,
        site=site,
        assignment_type=CleanerAssignmentType.FULL_TIME,
        start_date=date(2026, 1, 1),
        actor=admin_user,
    )
    AttendanceRecordFactory(cleaner=c, site=site, attendance_date=date(2026, 8, 1), status="present")
    AttendanceRecordFactory(cleaner=c, site=site, attendance_date=date(2026, 8, 2), status="absent")
    other_site = SiteFactory()
    AttendanceRecordFactory(cleaner=c, site=other_site, attendance_date=date(2026, 8, 1))

    ZoneSupervisorAssignmentFactory(zone=site.zone, user=zone_user)
    qs = attendance_history_queryset(zone_user, AttendanceFilter(date_from=date(2026, 8, 1), date_to=date(2026, 8, 31)))
    assert qs.count() == 2  # zone supervisor sees only their zone's site

    absent = attendance_history_queryset(admin_user, AttendanceFilter(status="absent"))
    assert absent.count() == 1


@pytest.mark.django_db
def test_missing_attendance_sites(site, admin_user) -> None:
    c = _active_cleaner()
    _assign(site, c, actor=admin_user)
    generate_daily_attendance_sheet(site_id=site.pk, day=date(2026, 7, 1), actor=admin_user)
    missing = missing_attendance_sites(admin_user, date(2026, 7, 1))
    assert any(item["site_id"] == site.pk and item["open_records"] >= 1 for item in missing)

    bulk_upsert_attendance(
        site_id=site.pk,
        day=date(2026, 7, 1),
        entries=[{"cleaner_id": c.pk, "status": "present"}],
        user=admin_user,
    )
    submit_daily_attendance(site_id=site.pk, day=date(2026, 7, 1), user=admin_user)
    missing_after = missing_attendance_sites(admin_user, date(2026, 7, 1))
    assert not any(item["site_id"] == site.pk and item["open_records"] for item in missing_after)


@pytest.mark.django_db
def test_daily_sheet_single_query(django_assert_num_queries, site, admin_user) -> None:
    c = _active_cleaner()
    _assign(site, c, actor=admin_user)
    generate_daily_attendance_sheet(site_id=site.pk, day=date(2026, 7, 6), actor=admin_user)
    from apps.site_management.attendance_selectors import attendance_daily_sheet

    with django_assert_num_queries(1):
        rows = attendance_daily_sheet(admin_user, site.pk, date(2026, 7, 6))
        assert len(rows) == 1


# --------------------------------------------------------------------------- #
# API
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
def test_attendance_api_flow(site, admin_user, admin_client) -> None:
    today = date.today()
    c = _active_cleaner()
    _assign(site, c, actor=admin_user)
    daily = admin_client.get(
        "/api/site-management/v1/attendance/daily", {"site_id": site.pk, "date": today.isoformat()}
    )
    assert daily.status_code == 200
    assert len(daily.json()) == 1

    bulk = admin_client.post(
        "/api/site-management/v1/attendance/bulk",
        data={
            "site_id": site.pk,
            "attendance_date": today.isoformat(),
            "entries": [{"cleaner_id": c.pk, "status": "present", "check_in_time": "08:00:00"}],
        },
        content_type="application/json",
    )
    assert bulk.status_code == 200
    record_id = bulk.json()[0]["id"]

    submitted = admin_client.post(
        "/api/site-management/v1/attendance/submit",
        data={"site_id": site.pk, "attendance_date": today.isoformat()},
        content_type="application/json",
    )
    assert submitted.json()["submitted"] == 1

    reviewed = admin_client.post(
        "/api/site-management/v1/attendance/review",
        data={"site_id": site.pk, "attendance_date": today.isoformat()},
        content_type="application/json",
    )
    assert reviewed.json()["reviewed"] == 1

    returned = admin_client.post(
        "/api/site-management/v1/attendance/return",
        data={"site_id": site.pk, "attendance_date": today.isoformat(), "reason": "Fix"},
        content_type="application/json",
    )
    assert returned.json()["returned"] == 1

    single = admin_client.put(
        f"/api/site-management/v1/attendance/{record_id}",
        data={"status": "leave"},
        content_type="application/json",
    )
    assert single.status_code == 200
    assert single.json()["status"] == "leave"

    history = admin_client.get("/api/site-management/v1/attendance/history", {"site_id": site.pk})
    assert history.json()["count"] == 1

    summary = admin_client.get(
        "/api/site-management/v1/attendance/summary", {"site_id": site.pk, "date": today.isoformat()}
    )
    assert summary.json()["leave"] == 1

    missing = admin_client.get("/api/site-management/v1/attendance/missing", {"date": today.isoformat()})
    assert isinstance(missing.json(), list)


@pytest.mark.django_db
def test_attendance_permissions(site, admin_user, viewer_user) -> None:
    c = _active_cleaner()
    _assign(site, c, actor=admin_user)
    viewer = UserFactory(role=RoleCode.MANAGEMENT_VIEWER)
    client = _authed(viewer)
    # Viewer can read but cannot write.
    assert (
        client.get("/api/site-management/v1/attendance/daily", {"site_id": site.pk, "date": "2026-07-04"}).status_code
        == 200
    )
    denied = client.post(
        "/api/site-management/v1/attendance/bulk",
        data={
            "site_id": site.pk,
            "attendance_date": "2026-07-04",
            "entries": [{"cleaner_id": c.pk, "status": "present"}],
        },
        content_type="application/json",
    )
    assert denied.status_code in (401, 403)


@pytest.mark.django_db
def test_attendance_validation_errors(site, admin_user, admin_client) -> None:
    response = admin_client.post(
        "/api/site-management/v1/attendance/bulk",
        data={"site_id": site.pk, "attendance_date": "2026-07-05", "entries": []},
        content_type="application/json",
    )
    assert response.status_code in (422, 400)

    c = _active_cleaner()
    _assign(site, c, actor=admin_user)
    future = (date.today() + timedelta(days=1)).isoformat()
    # A zone supervisor (not system admin/general) cannot write future dates.
    from apps.site_management.factories import ZoneSupervisorAssignmentFactory

    zone_supervisor = UserFactory(role=RoleCode.ZONE_SUPERVISOR)
    ZoneSupervisorAssignmentFactory(zone=site.zone, user=zone_supervisor)
    response = _authed(zone_supervisor).post(
        "/api/site-management/v1/attendance/bulk",
        data={"site_id": site.pk, "attendance_date": future, "entries": [{"cleaner_id": c.pk, "status": "present"}]},
        content_type="application/json",
    )
    assert response.status_code in (422, 400)


@pytest.mark.django_db
def test_attendance_exceptions_and_review_filter(site, admin_user) -> None:
    from apps.site_management.attendance_selectors import attendance_exceptions

    c = _active_cleaner()
    _assign(site, c, actor=admin_user)
    AttendanceRecordFactory(cleaner=c, site=site, attendance_date=date(2026, 7, 10), status="late")
    AttendanceRecordFactory(cleaner=c, site=site, attendance_date=date(2026, 7, 11), status="present")
    exceptions = attendance_exceptions(admin_user, AttendanceFilter(site_id=site.pk))
    assert len(exceptions) == 1

    reviewed = attendance_history_queryset(admin_user, AttendanceFilter(review_status="draft"))
    assert reviewed.count() == 2


@pytest.mark.django_db
def test_work_mode_entry_validation(site, admin_user) -> None:
    site.work_mode = WorkMode.FULL_TIME
    site.save(update_fields=["work_mode"])
    c = _active_cleaner()
    _assign(site, c, actor=admin_user)
    generate_daily_attendance_sheet(site_id=site.pk, day=date(2026, 7, 12), actor=admin_user)
    # Full-time site cannot record against a shift.
    shift = SiteShiftFactory(site=site)
    with pytest.raises(ValidationError):
        bulk_upsert_attendance(
            site_id=site.pk,
            day=date(2026, 7, 12),
            entries=[{"cleaner_id": c.pk, "shift_id": shift.pk, "status": "present"}],
            user=admin_user,
        )

    site.work_mode = WorkMode.SHIFT
    site.save(update_fields=["work_mode"])
    with pytest.raises(ValidationError):
        bulk_upsert_attendance(
            site_id=site.pk,
            day=date(2026, 7, 12),
            entries=[{"cleaner_id": c.pk, "status": "present"}],  # shift required
            user=admin_user,
        )


@pytest.mark.django_db
def test_review_group_with_nothing_to_review(site, admin_user) -> None:
    with pytest.raises(ValidationError):
        review_attendance_group(site_id=site.pk, day=date(2026, 7, 13), user=admin_user)


@pytest.mark.django_db
def test_attendance_admin_workflow(admin_user) -> None:
    from django.test import Client

    from apps.site_management.attendance_services import bulk_upsert_attendance, generate_daily_attendance_sheet

    admin = UserFactory(role=RoleCode.SYSTEM_ADMIN, is_staff=True, is_superuser=True)
    client = Client()
    client.force_login(admin)
    site = SiteFactory()
    c = _active_cleaner()
    _assign(site, c, actor=admin)
    generate_daily_attendance_sheet(site_id=site.pk, day=date(2026, 7, 14), actor=admin)
    bulk_upsert_attendance(
        site_id=site.pk, day=date(2026, 7, 14), entries=[{"cleaner_id": c.pk, "status": "present"}], user=admin
    )
    record = AttendanceRecord.objects.get(site=site, attendance_date=date(2026, 7, 14))

    assert client.get("/admin/site_management/attendancerecord/").status_code == 200
    assert (
        client.post(
            "/admin/site_management/attendancerecord/",
            data={"action": "submit_records", "_selected_action": [record.pk]},
        ).status_code
        == 302
    )
    record.refresh_from_db()
    assert record.review_status == AttendanceReviewStatus.SUBMITTED

    assert (
        client.post(
            "/admin/site_management/attendancerecord/",
            data={"action": "review_records", "_selected_action": [record.pk]},
        ).status_code
        == 302
    )
    record.refresh_from_db()
    assert record.review_status == AttendanceReviewStatus.REVIEWED

    assert (
        client.post(
            "/admin/site_management/attendancerecord/",
            data={"action": "return_records", "_selected_action": [record.pk]},
        ).status_code
        == 302
    )
    record.refresh_from_db()
    assert record.review_status == AttendanceReviewStatus.RETURNED


@pytest.mark.django_db
def test_attendance_admin_readonly_and_delete_guard(admin_user) -> None:
    from apps.site_management.admin import AttendanceRecordAdmin

    site = SiteFactory()
    c = _active_cleaner()
    _assign(site, c, actor=admin_user)
    draft = AttendanceRecordFactory(cleaner=c, site=site, attendance_date=date(2026, 7, 15), status="present")
    locked = AttendanceRecordFactory(
        cleaner=c,
        site=site,
        attendance_date=date(2026, 7, 16),
        status="present",
        review_status=AttendanceReviewStatus.LOCKED,
    )
    admin = AttendanceRecordAdmin(model=AttendanceRecord, admin_site=None)
    draft_fields = admin.get_readonly_fields(None, draft)
    locked_fields = admin.get_readonly_fields(None, locked)
    assert "status" not in draft_fields
    assert "status" in locked_fields
    assert admin.has_delete_permission(None, draft) is True
    assert admin.has_delete_permission(None, locked) is False


@pytest.mark.django_db
def test_attendance_outcome_distinguishes_sign_in_sign_out_and_absence(site, admin_user) -> None:
    from apps.site_management.api import _attendance_outcome

    cleaner = _active_cleaner()
    _assign(site, cleaner, actor=admin_user)
    absent = AttendanceRecordFactory(
        cleaner=cleaner, site=site, attendance_date=date(2026, 5, 1), status=AttendanceStatus.ABSENT
    )
    signed_in = AttendanceRecordFactory(
        cleaner=cleaner,
        site=site,
        attendance_date=date(2026, 5, 2),
        status=AttendanceStatus.PRESENT,
        check_in_time=time(8, 0),
    )
    complete = AttendanceRecordFactory(
        cleaner=cleaner,
        site=site,
        attendance_date=date(2026, 5, 3),
        status=AttendanceStatus.PRESENT,
        check_in_time=time(8, 0),
        check_out_time=time(17, 0),
    )

    assert _attendance_outcome(absent) == "absent"
    assert _attendance_outcome(signed_in) == "half_present"
    assert _attendance_outcome(complete) == "present"
