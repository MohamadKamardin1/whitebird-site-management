"""Tests for the cleaner assignment and scheduling engine."""

from datetime import date, time, timedelta
from typing import cast

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import Client

from apps.accounts.factories import UserFactory
from apps.accounts.models import RoleCode, User
from apps.accounts.services import issue_api_token
from apps.site_management.assignment_selectors import (
    cleaner_schedule,
    scheduled_cleaners_for_attendance,
    site_daily_schedule,
)
from apps.site_management.assignment_services import (
    activate_assignment,
    assign_cleaner_area_schedule,
    assign_cleaner_shift,
    assign_cleaner_to_site,
    copy_schedule_from_date,
    deactivate_area_schedule,
    end_assignment,
    remove_cleaner_shift,
    suspend_assignment,
    update_area_schedule,
    update_assignment,
)
from apps.site_management.factories import (
    CleanerFactory,
    CleanerShiftAssignmentFactory,
    CleanerSiteAssignmentFactory,
    OperationalRoleFactory,
    SiteAreaFactory,
    SiteFactory,
    SiteShiftFactory,
    SiteSupervisorAssignmentFactory,
    ZoneSupervisorAssignmentFactory,
)
from apps.site_management.models import (
    CleanerAreaSchedule,
    CleanerAssignmentStatus,
    CleanerAssignmentType,
    CleanerStatus,
    OperationalRole,
    SiteArea,
    SiteShift,
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


def _trainee() -> CleanerFactory:
    return CleanerFactory(status=CleanerStatus.TRAINEE)


# --------------------------------------------------------------------------- #
# Assignment rules
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
def test_assignment_type_must_match_site_work_mode(site, admin_user) -> None:
    site.work_mode = WorkMode.FULL_TIME
    site.save(update_fields=["work_mode"])
    cleaner = _active_cleaner()
    with pytest.raises(ValidationError):
        assign_cleaner_to_site(
            cleaner=cleaner,
            site=site,
            assignment_type=CleanerAssignmentType.SHIFT,
            start_date=date.today(),
            actor=admin_user,
        )
    assignment = assign_cleaner_to_site(
        cleaner=cleaner,
        site=site,
        assignment_type=CleanerAssignmentType.FULL_TIME,
        start_date=date.today(),
        actor=admin_user,
    )
    assert assignment.status == CleanerAssignmentStatus.ACTIVE


@pytest.mark.django_db
def test_shift_site_requires_shift_assignment(site, admin_user) -> None:
    site.work_mode = WorkMode.SHIFT
    site.save(update_fields=["work_mode"])
    SiteShiftFactory(site=site)  # SHIFT site needs an active shift
    cleaner = _active_cleaner()
    with pytest.raises(ValidationError):
        assign_cleaner_to_site(
            cleaner=cleaner,
            site=site,
            assignment_type=CleanerAssignmentType.FULL_TIME,
            start_date=date.today(),
            actor=admin_user,
        )


@pytest.mark.django_db
def test_trainee_gets_draft_and_cannot_activate(site, admin_user) -> None:
    site.work_mode = WorkMode.FULL_TIME_AND_SHIFT
    site.save(update_fields=["work_mode"])
    trainee = _trainee()
    assignment = assign_cleaner_to_site(
        cleaner=trainee,
        site=site,
        assignment_type=CleanerAssignmentType.FULL_TIME,
        start_date=date.today(),
        actor=admin_user,
    )
    assert assignment.status == CleanerAssignmentStatus.DRAFT
    with pytest.raises(ValidationError):
        activate_assignment(assignment=assignment, actor=admin_user)


@pytest.mark.django_db
def test_inactive_cleaner_cannot_be_assigned(site, admin_user) -> None:
    inactive = CleanerFactory(status=CleanerStatus.INACTIVE)
    with pytest.raises(ValidationError):
        assign_cleaner_to_site(
            cleaner=inactive,
            site=site,
            assignment_type=CleanerAssignmentType.FULL_TIME,
            start_date=date.today(),
            actor=admin_user,
        )


@pytest.mark.django_db
def test_end_date_cannot_precede_start(site, admin_user) -> None:
    cleaner = _active_cleaner()
    with pytest.raises(ValidationError):
        assign_cleaner_to_site(
            cleaner=cleaner,
            site=site,
            assignment_type=CleanerAssignmentType.FULL_TIME,
            start_date=date.today(),
            end_date=date.today() - timedelta(days=1),
            actor=admin_user,
        )


@pytest.mark.django_db
def test_duplicate_active_assignment_blocked(site, admin_user) -> None:
    cleaner = _active_cleaner()
    assign_cleaner_to_site(
        cleaner=cleaner,
        site=site,
        assignment_type=CleanerAssignmentType.FULL_TIME,
        start_date=date.today(),
        actor=admin_user,
    )
    with pytest.raises(IntegrityError):
        CleanerSiteAssignmentFactory(cleaner=cleaner, site=site, status=CleanerAssignmentStatus.ACTIVE)


@pytest.mark.django_db
def test_assignment_lifecycle_end_suspend_activate(site, admin_user) -> None:
    cleaner = _active_cleaner()
    assignment = assign_cleaner_to_site(
        cleaner=cleaner,
        site=site,
        assignment_type=CleanerAssignmentType.FULL_TIME,
        start_date=date.today(),
        actor=admin_user,
    )
    assert end_assignment(assignment=assignment, actor=admin_user).status == CleanerAssignmentStatus.ENDED
    assert assignment.end_date is not None

    assignment2 = CleanerSiteAssignmentFactory(cleaner=cleaner, site=site, status=CleanerAssignmentStatus.DRAFT)
    assert suspend_assignment(assignment=assignment2, actor=admin_user).status == CleanerAssignmentStatus.SUSPENDED
    assert activate_assignment(assignment=assignment2, actor=admin_user).status == CleanerAssignmentStatus.ACTIVE
    updated = update_assignment(assignment=assignment2, actor=admin_user, notes="Priority cleaner")
    assert updated.notes == "Priority cleaner"


# --------------------------------------------------------------------------- #
# Shift assignments
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
def test_shift_must_belong_to_assignment_site(site, admin_user) -> None:
    site.work_mode = WorkMode.SHIFT
    site.save(update_fields=["work_mode"])
    shift = SiteShiftFactory(site=site)
    other_site = SiteFactory()
    other_shift = SiteShiftFactory(site=other_site)
    cleaner = _active_cleaner()
    assignment = assign_cleaner_to_site(
        cleaner=cleaner,
        site=site,
        assignment_type=CleanerAssignmentType.SHIFT,
        start_date=date.today(),
        actor=admin_user,
    )
    with pytest.raises(ValidationError):
        assign_cleaner_shift(assignment=assignment, shift=other_shift, effective_from=date.today(), actor=admin_user)
    sa = assign_cleaner_shift(assignment=assignment, shift=shift, effective_from=date.today(), actor=admin_user)
    assert sa.is_active is True


@pytest.mark.django_db
def test_shift_assignment_requires_shift_type(site, admin_user) -> None:
    site.work_mode = WorkMode.FULL_TIME_AND_SHIFT
    site.save(update_fields=["work_mode"])
    shift = SiteShiftFactory(site=site)
    cleaner = _active_cleaner()
    assignment = assign_cleaner_to_site(
        cleaner=cleaner,
        site=site,
        assignment_type=CleanerAssignmentType.FULL_TIME,
        start_date=date.today(),
        actor=admin_user,
    )
    with pytest.raises(ValidationError):
        assign_cleaner_shift(assignment=assignment, shift=shift, effective_from=date.today(), actor=admin_user)


@pytest.mark.django_db
def test_duplicate_active_shift_binding_blocked(site, admin_user) -> None:
    site.work_mode = WorkMode.SHIFT
    site.save(update_fields=["work_mode"])
    shift = SiteShiftFactory(site=site)
    cleaner = _active_cleaner()
    assignment = assign_cleaner_to_site(
        cleaner=cleaner,
        site=site,
        assignment_type=CleanerAssignmentType.SHIFT,
        start_date=date.today(),
        actor=admin_user,
    )
    assign_cleaner_shift(assignment=assignment, shift=shift, effective_from=date.today(), actor=admin_user)
    with pytest.raises(IntegrityError):
        CleanerShiftAssignmentFactory(assignment=assignment, shift=shift)


@pytest.mark.django_db
def test_remove_shift_binding(site, admin_user) -> None:
    site.work_mode = WorkMode.SHIFT
    site.save(update_fields=["work_mode"])
    shift = SiteShiftFactory(site=site)
    cleaner = _active_cleaner()
    assignment = assign_cleaner_to_site(
        cleaner=cleaner,
        site=site,
        assignment_type=CleanerAssignmentType.SHIFT,
        start_date=date.today(),
        actor=admin_user,
    )
    sa = assign_cleaner_shift(assignment=assignment, shift=shift, effective_from=date.today(), actor=admin_user)
    removed = remove_cleaner_shift(shift_assignment=sa, actor=admin_user)
    assert removed.is_active is False


# --------------------------------------------------------------------------- #
# Area schedules
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
def test_area_schedule_lifecycle_and_overnight(site, admin_user) -> None:
    cleaner = _active_cleaner()
    assignment = assign_cleaner_to_site(
        cleaner=cleaner,
        site=site,
        assignment_type=CleanerAssignmentType.FULL_TIME,
        start_date=date.today(),
        actor=admin_user,
    )
    area = SiteAreaFactory(site=site)
    role = OperationalRoleFactory()
    schedule = assign_cleaner_area_schedule(
        assignment=assignment,
        site_area=area,
        operational_role=role,
        day=date.today(),
        start_time=time(22, 0),
        end_time=time(6, 0),
        actor=admin_user,
    )
    assert schedule.crosses_midnight is True

    updated = update_area_schedule(schedule=schedule, actor=admin_user, notes="Overnight shift")
    assert updated.notes == "Overnight shift"

    assert deactivate_area_schedule(schedule=updated, actor=admin_user).is_active is False


@pytest.mark.django_db
def test_area_must_belong_to_assignment_site(site, admin_user) -> None:
    cleaner = _active_cleaner()
    assignment = assign_cleaner_to_site(
        cleaner=cleaner,
        site=site,
        assignment_type=CleanerAssignmentType.FULL_TIME,
        start_date=date.today(),
        actor=admin_user,
    )
    other_area = SiteAreaFactory(site=SiteFactory())
    role = OperationalRoleFactory()
    with pytest.raises(ValidationError):
        assign_cleaner_area_schedule(
            assignment=assignment,
            site_area=other_area,
            operational_role=role,
            day=date.today(),
            start_time=time(8),
            end_time=time(12),
            actor=admin_user,
        )


@pytest.mark.django_db
def test_overlapping_schedule_blocked(site, admin_user) -> None:
    cleaner = _active_cleaner()
    assignment = assign_cleaner_to_site(
        cleaner=cleaner,
        site=site,
        assignment_type=CleanerAssignmentType.FULL_TIME,
        start_date=date.today(),
        actor=admin_user,
    )
    area = SiteAreaFactory(site=site)
    role = OperationalRoleFactory()
    assign_cleaner_area_schedule(
        assignment=assignment,
        site_area=area,
        operational_role=role,
        day=date.today(),
        start_time=time(8),
        end_time=time(12),
        actor=admin_user,
    )
    with pytest.raises(ValidationError):
        assign_cleaner_area_schedule(
            assignment=assignment,
            site_area=area,
            operational_role=role,
            day=date.today(),
            start_time=time(10),
            end_time=time(14),
            actor=admin_user,
        )


@pytest.mark.django_db
def test_non_overlapping_multiple_schedules_allowed(site, admin_user) -> None:
    cleaner = _active_cleaner()
    assignment = assign_cleaner_to_site(
        cleaner=cleaner,
        site=site,
        assignment_type=CleanerAssignmentType.FULL_TIME,
        start_date=date.today(),
        actor=admin_user,
    )
    role = OperationalRoleFactory()
    assign_cleaner_area_schedule(
        assignment=assignment,
        site_area=SiteAreaFactory(site=site),
        operational_role=role,
        day=date.today(),
        start_time=time(8),
        end_time=time(10),
        actor=admin_user,
    )
    assign_cleaner_area_schedule(
        assignment=assignment,
        site_area=SiteAreaFactory(site=site),
        operational_role=role,
        day=date.today(),
        start_time=time(11),
        end_time=time(13),
        actor=admin_user,
    )
    assert CleanerAreaSchedule.objects.filter(assignment=assignment, is_active=True).count() == 2


@pytest.mark.django_db
def test_copy_schedule_from_date(site, admin_user) -> None:
    cleaner = _active_cleaner()
    assignment = assign_cleaner_to_site(
        cleaner=cleaner,
        site=site,
        assignment_type=CleanerAssignmentType.FULL_TIME,
        start_date=date.today(),
        actor=admin_user,
    )
    role = OperationalRoleFactory()
    area = SiteAreaFactory(site=site)
    assign_cleaner_area_schedule(
        assignment=assignment,
        site_area=area,
        operational_role=role,
        day=date(2026, 1, 5),
        start_time=time(8),
        end_time=time(12),
        actor=admin_user,
    )
    created = copy_schedule_from_date(
        assignment=assignment, from_date=date(2026, 1, 5), to_date=date(2026, 1, 6), actor=admin_user
    )
    assert created == 1
    assert CleanerAreaSchedule.objects.filter(assignment=assignment, date=date(2026, 1, 6)).count() == 1


# --------------------------------------------------------------------------- #
# Selectors
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
def test_site_daily_schedule_and_attendance_projection(site, admin_user) -> None:
    cleaner = _active_cleaner()
    assignment = assign_cleaner_to_site(
        cleaner=cleaner,
        site=site,
        assignment_type=CleanerAssignmentType.FULL_TIME,
        start_date=date.today(),
        actor=admin_user,
    )
    role = OperationalRoleFactory(name="Toilet Cleaner", code="toilet")
    area = SiteAreaFactory(site=site, area_name="Lobby")
    assign_cleaner_area_schedule(
        assignment=assignment,
        site_area=area,
        operational_role=role,
        day=date(2026, 3, 10),
        start_time=time(8),
        end_time=time(12),
        actor=admin_user,
    )

    daily = site_daily_schedule(site.pk, date(2026, 3, 10))
    assert len(daily) == 1
    assert daily[0].site_area.area_name == "Lobby"

    rows = scheduled_cleaners_for_attendance(site.pk, date(2026, 3, 10))
    assert rows[0]["cleaner_name"] == cleaner.full_name
    assert rows[0]["role_name"] == "Toilet Cleaner"
    assert rows[0]["area_name"] == "Lobby"
    assert rows[0]["start_time"] == "08:00:00"

    by_cleaner = cleaner_schedule(cleaner.pk, date(2026, 3, 1), date(2026, 3, 31))
    assert len(by_cleaner) == 1


@pytest.mark.django_db
def test_schedule_selectors_single_query(django_assert_num_queries, site, admin_user) -> None:
    cleaner = _active_cleaner()
    assignment = assign_cleaner_to_site(
        cleaner=cleaner,
        site=site,
        assignment_type=CleanerAssignmentType.FULL_TIME,
        start_date=date.today(),
        actor=admin_user,
    )
    role = OperationalRoleFactory()
    area = SiteAreaFactory(site=site)
    assign_cleaner_area_schedule(
        assignment=assignment,
        site_area=area,
        operational_role=role,
        day=date(2026, 4, 1),
        start_time=time(8),
        end_time=time(12),
        actor=admin_user,
    )
    with django_assert_num_queries(1):
        rows = scheduled_cleaners_for_attendance(site.pk, date(2026, 4, 1))
        assert len(rows) == 1


# --------------------------------------------------------------------------- #
# Permissions & API
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
def test_site_supervisor_scoping(admin_user, site, zone_user) -> None:
    cleaner = _active_cleaner()
    assign_cleaner_to_site(
        cleaner=cleaner,
        site=site,
        assignment_type=CleanerAssignmentType.FULL_TIME,
        start_date=date.today(),
        actor=admin_user,
    )
    # Site supervisor sees only their assigned sites' assignments.
    site_supervisor = UserFactory(role=RoleCode.SITE_SUPERVISOR)
    SiteSupervisorAssignmentFactory(site=site, user=site_supervisor)
    response = _authed(site_supervisor).get("/api/site-management/v1/assignments")
    assert response.status_code == 200
    assert response.json()["count"] == 1

    # Unassigned site supervisor sees nothing.
    other = UserFactory(role=RoleCode.SITE_SUPERVISOR)
    response = _authed(other).get("/api/site-management/v1/assignments")
    assert response.json()["count"] == 0


@pytest.mark.django_db
def test_zone_supervisor_sees_zone_sites(admin_user, site, zone_user) -> None:
    cleaner = _active_cleaner()
    assign_cleaner_to_site(
        cleaner=cleaner,
        site=site,
        assignment_type=CleanerAssignmentType.FULL_TIME,
        start_date=date.today(),
        actor=admin_user,
    )
    ZoneSupervisorAssignmentFactory(zone=site.zone, user=zone_user)
    response = _authed(zone_user).get("/api/site-management/v1/assignments")
    assert response.json()["count"] == 1


@pytest.mark.django_db
def test_management_viewer_read_only(admin_user, site) -> None:
    cleaner = _active_cleaner()
    assign_cleaner_to_site(
        cleaner=cleaner,
        site=site,
        assignment_type=CleanerAssignmentType.FULL_TIME,
        start_date=date.today(),
        actor=admin_user,
    )
    viewer = UserFactory(role=RoleCode.MANAGEMENT_VIEWER)
    client = _authed(viewer)
    response = client.get("/api/site-management/v1/assignments")
    assert response.status_code == 200
    created = client.post(
        "/api/site-management/v1/assignments",
        data={
            "cleaner_id": _active_cleaner().pk,
            "site_id": site.pk,
            "assignment_type": "full_time",
            "start_date": "2026-01-01",
        },
        content_type="application/json",
    )
    assert created.status_code in (401, 403)


@pytest.mark.django_db
def test_assignment_api_happy_path(admin_client, admin_user, site) -> None:
    cleaner = _active_cleaner()
    created = admin_client.post(
        "/api/site-management/v1/assignments",
        data={
            "cleaner_id": cleaner.pk,
            "site_id": site.pk,
            "assignment_type": "full_time",
            "start_date": "2026-01-01",
        },
        content_type="application/json",
    )
    assert created.status_code == 200
    assignment_id = created.json()["id"]
    assert created.json()["status"] == "active"

    detail = admin_client.get(f"/api/site-management/v1/assignments/{assignment_id}")
    assert detail.json()["cleaner_name"] == cleaner.full_name

    ended = admin_client.patch(f"/api/site-management/v1/assignments/{assignment_id}/end")
    assert ended.json()["status"] == "ended"

    suspended = admin_client.patch(f"/api/site-management/v1/assignments/{assignment_id}/suspend")
    assert suspended.json()["status"] == "suspended"

    reactivated = admin_client.patch(f"/api/site-management/v1/assignments/{assignment_id}/activate")
    assert reactivated.json()["status"] == "active"


@pytest.mark.django_db
def test_area_schedule_api(site, admin_user, admin_client) -> None:
    cleaner = _active_cleaner()
    created = admin_client.post(
        "/api/site-management/v1/assignments",
        data={"cleaner_id": cleaner.pk, "site_id": site.pk, "assignment_type": "full_time", "start_date": "2026-01-01"},
        content_type="application/json",
    )
    assignment_id = created.json()["id"]
    area = SiteAreaFactory(site=site)
    role = OperationalRoleFactory()
    schedule = admin_client.post(
        f"/api/site-management/v1/assignments/{assignment_id}/area-schedules",
        data={
            "site_area_id": area.pk,
            "operational_role_id": role.pk,
            "date": "2026-02-01",
            "start_time": "08:00:00",
            "end_time": "16:00:00",
        },
        content_type="application/json",
    )
    assert schedule.status_code == 200
    schedule_id = schedule.json()["id"]
    listed = admin_client.get(f"/api/site-management/v1/assignments/{assignment_id}/area-schedules")
    assert len(listed.json()) == 1
    removed = admin_client.delete(f"/api/site-management/v1/assignments/{assignment_id}/area-schedules/{schedule_id}")
    assert removed.status_code == 200


@pytest.mark.django_db
def test_schedules_endpoint(site, admin_user, admin_client) -> None:
    cleaner = _active_cleaner()
    created = admin_client.post(
        "/api/site-management/v1/assignments",
        data={"cleaner_id": cleaner.pk, "site_id": site.pk, "assignment_type": "full_time", "start_date": "2026-01-01"},
        content_type="application/json",
    )
    assignment_id = created.json()["id"]
    area = SiteAreaFactory(site=site)
    role = OperationalRoleFactory()
    admin_client.post(
        f"/api/site-management/v1/assignments/{assignment_id}/area-schedules",
        data={
            "site_area_id": area.pk,
            "operational_role_id": role.pk,
            "date": "2026-05-05",
            "start_time": "08:00:00",
            "end_time": "16:00:00",
        },
        content_type="application/json",
    )
    response = admin_client.get("/api/site-management/v1/schedules", {"site_id": site.pk, "date": "2026-05-05"})
    assert response.status_code == 200
    assert response.json()[0]["area_name"] == area.area_name


# --------------------------------------------------------------------------- #
# Selector filters & policies
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
def test_assignment_list_filters(admin_client, admin_user, site) -> None:
    cleaner_a = _active_cleaner()
    cleaner_b = _active_cleaner()
    other_site = SiteFactory()
    assign_cleaner_to_site(
        cleaner=cleaner_a,
        site=site,
        assignment_type=CleanerAssignmentType.FULL_TIME,
        start_date=date(2026, 1, 1),
        actor=admin_user,
    )
    assign_cleaner_to_site(
        cleaner=cleaner_b,
        site=other_site,
        assignment_type=CleanerAssignmentType.FULL_TIME,
        start_date=date(2026, 1, 1),
        actor=admin_user,
    )

    by_site = admin_client.get("/api/site-management/v1/assignments", {"site_id": site.pk})
    assert by_site.json()["count"] == 1
    by_status = admin_client.get("/api/site-management/v1/assignments", {"status": "active"})
    assert by_status.json()["count"] == 2
    by_type = admin_client.get("/api/site-management/v1/assignments", {"assignment_type": "full_time"})
    assert by_type.json()["count"] == 2
    by_search = admin_client.get("/api/site-management/v1/assignments", {"search": cleaner_a.first_name})
    assert by_search.json()["count"] == 1
    by_cleaner = admin_client.get("/api/site-management/v1/assignments", {"cleaner_id": cleaner_a.pk})
    assert by_cleaner.json()["count"] == 1


@pytest.mark.django_db
def test_site_daily_schedule_shift_filter(site, admin_user) -> None:
    site.work_mode = WorkMode.SHIFT
    site.save(update_fields=["work_mode"])
    shift = SiteShiftFactory(site=site)
    cleaner = _active_cleaner()
    assignment = assign_cleaner_to_site(
        cleaner=cleaner,
        site=site,
        assignment_type=CleanerAssignmentType.SHIFT,
        start_date=date.today(),
        actor=admin_user,
    )
    assign_cleaner_shift(assignment=assignment, shift=shift, effective_from=date.today(), actor=admin_user)
    role = OperationalRoleFactory()
    area = SiteAreaFactory(site=site)
    assign_cleaner_area_schedule(
        assignment=assignment,
        site_area=area,
        operational_role=role,
        day=date(2026, 6, 1),
        start_time=time(8),
        end_time=time(12),
        shift=shift,
        actor=admin_user,
    )
    assert len(site_daily_schedule(site.pk, date(2026, 6, 1))) == 1
    assert len(site_daily_schedule(site.pk, date(2026, 6, 1), shift_id=shift.pk)) == 1
    other_shift = SiteShiftFactory(site=site, shift_name="Other")
    assert len(site_daily_schedule(site.pk, date(2026, 6, 1), shift_id=other_shift.pk)) == 0
    assert cleaner_schedule(cleaner.pk, date(2026, 5, 1), date(2026, 5, 31)) == []


@pytest.mark.django_db
def test_policy_helpers(site, admin_user, zone_user, site_supervisor_user) -> None:
    from apps.site_management.assignment_policies import (
        can_assign_cleaner,
        can_edit_assignment,
        can_view_assignment,
    )

    cleaner = _active_cleaner()
    assignment = assign_cleaner_to_site(
        cleaner=cleaner,
        site=site,
        assignment_type=CleanerAssignmentType.FULL_TIME,
        start_date=date.today(),
        actor=admin_user,
    )
    SiteSupervisorAssignmentFactory(site=site, user=site_supervisor_user)
    assert can_view_assignment(admin_user, assignment) is True
    assert can_edit_assignment(admin_user, assignment) is True
    assert can_assign_cleaner(admin_user, site, cleaner) is True
    # Unassigned site supervisor cannot edit.
    outsider = UserFactory(role=RoleCode.SITE_SUPERVISOR)
    assert can_edit_assignment(outsider, assignment) is False
    assert can_assign_cleaner(outsider, site, cleaner) is False

    hr_user = UserFactory(role=RoleCode.HR)
    assert can_view_assignment(hr_user, assignment) is True
    assert can_edit_assignment(hr_user, assignment) is True
    assert can_assign_cleaner(hr_user, site, cleaner) is True


@pytest.mark.django_db
def test_update_assignment_end_date_and_copy_overlap_skip(site, admin_user) -> None:
    cleaner = _active_cleaner()
    assignment = assign_cleaner_to_site(
        cleaner=cleaner,
        site=site,
        assignment_type=CleanerAssignmentType.FULL_TIME,
        start_date=date(2026, 1, 1),
        actor=admin_user,
    )
    updated = update_assignment(assignment=assignment, actor=admin_user, end_date=date(2026, 12, 31))
    assert updated.end_date == date(2026, 12, 31)

    role = OperationalRoleFactory()
    area = SiteAreaFactory(site=site)
    assign_cleaner_area_schedule(
        assignment=assignment,
        site_area=area,
        operational_role=role,
        day=date(2026, 7, 1),
        start_time=time(8),
        end_time=time(12),
        actor=admin_user,
    )
    # Target date already has an overlapping schedule -> copy skips it.
    assign_cleaner_area_schedule(
        assignment=assignment,
        site_area=area,
        operational_role=role,
        day=date(2026, 7, 2),
        start_time=time(8),
        end_time=time(12),
        actor=admin_user,
    )
    created = copy_schedule_from_date(
        assignment=assignment, from_date=date(2026, 7, 1), to_date=date(2026, 7, 2), actor=admin_user
    )
    assert created == 0


@pytest.mark.django_db
def test_copy_schedule_from_date_with_no_sources(admin_user, site) -> None:
    cleaner = _active_cleaner()
    assignment = assign_cleaner_to_site(
        cleaner=cleaner,
        site=site,
        assignment_type=CleanerAssignmentType.FULL_TIME,
        start_date=date.today(),
        actor=admin_user,
    )
    assert (
        copy_schedule_from_date(
            assignment=assignment, from_date=date(2026, 1, 1), to_date=date(2026, 1, 2), actor=admin_user
        )
        == 0
    )


@pytest.mark.django_db
def test_overnight_schedule_overlap_blocked(site, admin_user) -> None:
    cleaner = _active_cleaner()
    assignment = assign_cleaner_to_site(
        cleaner=cleaner,
        site=site,
        assignment_type=CleanerAssignmentType.FULL_TIME,
        start_date=date.today(),
        actor=admin_user,
    )
    role = OperationalRoleFactory()
    area = SiteAreaFactory(site=site)
    assign_cleaner_area_schedule(
        assignment=assignment,
        site_area=area,
        operational_role=role,
        day=date(2026, 8, 1),
        start_time=time(22, 0),
        end_time=time(2, 0),
        actor=admin_user,
    )
    with pytest.raises(ValidationError):
        assign_cleaner_area_schedule(
            assignment=assignment,
            site_area=SiteAreaFactory(site=site),
            operational_role=role,
            day=date(2026, 8, 1),
            start_time=time(1, 0),
            end_time=time(3, 0),
            actor=admin_user,
        )


@pytest.mark.django_db
def test_update_area_schedule_full_update(site, admin_user) -> None:
    site.work_mode = WorkMode.FULL_TIME_AND_SHIFT
    site.save(update_fields=["work_mode"])
    cleaner = _active_cleaner()
    assignment = assign_cleaner_to_site(
        cleaner=cleaner,
        site=site,
        assignment_type=CleanerAssignmentType.FULL_TIME,
        start_date=date.today(),
        actor=admin_user,
    )
    area = SiteAreaFactory(site=site)
    area2 = cast(SiteArea, SiteAreaFactory(site=site, area_name="Pool"))
    role = OperationalRoleFactory()
    role2 = cast(OperationalRole, OperationalRoleFactory(name="Floor Cleaner", code="floor"))
    shift = cast(SiteShift, SiteShiftFactory(site=site))
    schedule = assign_cleaner_area_schedule(
        assignment=assignment,
        site_area=area,
        operational_role=role,
        day=date(2026, 9, 1),
        start_time=time(8),
        end_time=time(12),
        actor=admin_user,
    )
    updated = update_area_schedule(
        schedule=schedule,
        actor=admin_user,
        site_area=area2,
        operational_role=role2,
        start_time=time(9),
        end_time=time(13),
        shift=shift,
        notes="Updated",
    )
    assert updated.site_area == area2
    assert updated.operational_role == role2
    assert updated.end_time == time(13)
    assert updated.shift == shift
    assert updated.notes == "Updated"
