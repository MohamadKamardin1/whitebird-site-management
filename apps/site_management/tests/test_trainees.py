"""Tests for the trainee lifecycle and cleaner conversion."""

from datetime import date, timedelta

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import Client

from apps.accounts.factories import UserFactory
from apps.accounts.models import RoleCode, User
from apps.accounts.services import issue_api_token
from apps.core.models import AuditLog
from apps.site_management.factories import (
    CleanerDocumentFactory,
    CleanerFactory,
    CleanerSiteAssignmentFactory,
    SiteFactory,
    SiteSupervisorAssignmentFactory,
    TraineeProgramFactory,
    ZoneSupervisorAssignmentFactory,
)
from apps.site_management.models import (
    CleanerDocumentStatus,
    CleanerAssignmentStatus,
    CleanerSiteAssignment,
    CleanerStatus,
    TraineeProgram,
    TraineeProgramStatus,
)
from apps.site_management.trainee_selectors import (
    TraineeFilter,
    trainee_list_queryset,
    trainee_summary,
)
from apps.site_management.trainee_services import (
    drop_trainee,
    extend_trainee_program,
    fail_trainee,
    pass_trainee,
    record_trainee_evaluation,
    start_trainee_program,
    update_trainee_program,
)


@pytest.fixture(autouse=True)
def rbac_seeded(db: None) -> None:
    from django.core.management import call_command

    call_command("seed_rbac")


def _authed(user: User) -> Client:
    return Client(HTTP_AUTHORIZATION=f"Bearer {issue_api_token(user=user, name='test').key}")


def _applicant() -> CleanerFactory:
    return CleanerFactory(status=CleanerStatus.APPLICANT)


# --------------------------------------------------------------------------- #
# Start / active-program rules
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
def test_start_program_sets_cleaner_to_trainee(site, admin_user) -> None:
    cleaner = _applicant()
    program = start_trainee_program(
        cleaner=cleaner,
        site=site,
        expected_end_date=date.today() + timedelta(days=60),
        actor=admin_user,
    )
    assert program.status == TraineeProgramStatus.IN_TRAINING
    cleaner.refresh_from_db()
    assert cleaner.status == CleanerStatus.TRAINEE


@pytest.mark.django_db
def test_only_one_active_program_per_cleaner(site, admin_user) -> None:
    cleaner = _applicant()
    start_trainee_program(
        cleaner=cleaner, site=site, expected_end_date=date.today() + timedelta(days=60), actor=admin_user
    )
    with pytest.raises(IntegrityError):
        TraineeProgramFactory(cleaner=cleaner, site=site)


@pytest.mark.django_db
def test_active_cleaner_cannot_start_program(site, admin_user) -> None:
    active = CleanerFactory(status=CleanerStatus.ACTIVE)
    with pytest.raises(ValidationError):
        start_trainee_program(
            cleaner=active, site=site, expected_end_date=date.today() + timedelta(days=60), actor=admin_user
        )


@pytest.mark.django_db
def test_update_and_extend_program(site, admin_user) -> None:
    cleaner = _applicant()
    program = start_trainee_program(
        cleaner=cleaner, site=site, expected_end_date=date.today() + timedelta(days=60), actor=admin_user
    )
    updated = update_trainee_program(program=program, actor=admin_user, notes="Focused training")
    assert updated.notes == "Focused training"

    new_end = date.today() + timedelta(days=90)
    extended = extend_trainee_program(
        program=program, new_expected_end_date=new_end, reason="Needs more time", actor=admin_user
    )
    assert extended.status == TraineeProgramStatus.EXTENDED
    assert extended.expected_end_date == new_end
    assert "Needs more time" in extended.notes

    with pytest.raises(ValidationError):
        extend_trainee_program(program=program, new_expected_end_date=new_end, reason="", actor=admin_user)


# --------------------------------------------------------------------------- #
# Evaluations
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
def test_evaluation_total_computed_when_absent(site, admin_user) -> None:
    cleaner = _applicant()
    program = start_trainee_program(
        cleaner=cleaner, site=site, expected_end_date=date.today() + timedelta(days=60), actor=admin_user
    )
    evaluation = record_trainee_evaluation(
        program=program,
        evaluation_date=date.today(),
        actor=admin_user,
        attendance_score=70,
        performance_score=80,
        behavior_score=90,
        skill_score=60,
    )
    assert evaluation.total_score == 300
    assert evaluation.is_final is False


@pytest.mark.django_db
def test_final_evaluation_required_for_pass(site, admin_user) -> None:
    cleaner = _applicant()
    program = start_trainee_program(
        cleaner=cleaner, site=site, expected_end_date=date.today() + timedelta(days=60), actor=admin_user
    )
    record_trainee_evaluation(program=program, evaluation_date=date.today(), actor=admin_user, skill_score=50)
    with pytest.raises(ValidationError):
        pass_trainee(program=program, actor=admin_user)

    record_trainee_evaluation(
        program=program, evaluation_date=date.today(), actor=admin_user, skill_score=90, is_final=True
    )
    # Verified ID still missing.
    with pytest.raises(ValidationError):
        pass_trainee(program=program, actor=admin_user)


@pytest.mark.django_db
def test_pass_converts_to_active_cleaner(site, admin_user) -> None:
    cleaner = _applicant()
    program = start_trainee_program(
        cleaner=cleaner, site=site, expected_end_date=date.today() + timedelta(days=60), actor=admin_user
    )
    record_trainee_evaluation(program=program, evaluation_date=date.today(), actor=admin_user, is_final=True)
    CleanerDocumentFactory(cleaner=cleaner, status=CleanerDocumentStatus.VERIFIED)
    passed = pass_trainee(program=program, actor=admin_user)
    assert passed.status == TraineeProgramStatus.PASSED
    assert passed.actual_end_date == date.today()
    cleaner.refresh_from_db()
    assert cleaner.status == CleanerStatus.ACTIVE


@pytest.mark.django_db
def test_fail_and_drop_make_cleaner_inactive(site, admin_user) -> None:
    for service in (fail_trainee, drop_trainee):
        cleaner = _applicant()
        program = start_trainee_program(
            cleaner=cleaner, site=site, expected_end_date=date.today() + timedelta(days=60), actor=admin_user
        )
        with pytest.raises(ValidationError):
            service(program=program, actor=admin_user, reason="")
        completed = service(program=program, actor=admin_user, reason="Not suitable")
        assert completed.actual_end_date == date.today()
        cleaner.refresh_from_db()
        assert cleaner.status == CleanerStatus.INACTIVE


@pytest.mark.django_db
def test_completed_program_cannot_be_extended(site, admin_user) -> None:
    cleaner = _applicant()
    program = start_trainee_program(
        cleaner=cleaner, site=site, expected_end_date=date.today() + timedelta(days=60), actor=admin_user
    )
    drop_trainee(program=program, actor=admin_user, reason="Withdrew")
    with pytest.raises(ValidationError):
        extend_trainee_program(
            program=program, new_expected_end_date=date.today() + timedelta(days=30), reason="x", actor=admin_user
        )


# --------------------------------------------------------------------------- #
# Selectors & summary
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
def test_trainee_summary_counts(site, admin_user, zone_user) -> None:
    for status in (
        TraineeProgramStatus.IN_TRAINING,
        TraineeProgramStatus.PASSED,
        TraineeProgramStatus.FAILED,
        TraineeProgramStatus.DROPPED,
    ):
        c = _applicant()
        program = start_trainee_program(
            cleaner=c, site=site, expected_end_date=date.today() + timedelta(days=60), actor=admin_user
        )
        if status != TraineeProgramStatus.IN_TRAINING:
            record_trainee_evaluation(program=program, evaluation_date=date.today(), actor=admin_user, is_final=True)
            CleanerDocumentFactory(cleaner=c, status=CleanerDocumentStatus.VERIFIED)
            if status == TraineeProgramStatus.PASSED:
                pass_trainee(program=program, actor=admin_user)
            else:
                fail_trainee(
                    program=program, actor=admin_user, reason="x"
                ) if status == TraineeProgramStatus.FAILED else drop_trainee(
                    program=program, actor=admin_user, reason="y"
                )

    summary = trainee_summary(admin_user, TraineeFilter(site_id=site.pk))
    assert summary["total_trainees"] == 4
    assert summary["in_training"] == 1
    assert summary["passed"] == 1
    assert summary["failed"] == 1
    assert summary["dropped"] == 1

    ZoneSupervisorAssignmentFactory(zone=site.zone, user=zone_user)
    scoped = trainee_list_queryset(zone_user, TraineeFilter())
    assert scoped.count() == 4


# --------------------------------------------------------------------------- #
# API
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
def test_trainee_api_flow(site, admin_user, admin_client) -> None:
    cleaner = _applicant()
    created = admin_client.post(
        "/api/site-management/v1/trainees",
        data={
            "cleaner_id": cleaner.pk,
            "site_id": site.pk,
            "expected_end_date": (date.today() + timedelta(days=60)).isoformat(),
        },
        content_type="application/json",
    )
    assert created.status_code == 200
    program_id = created.json()["id"]
    assert created.json()["status"] == "in_training"

    eval_resp = admin_client.post(
        f"/api/site-management/v1/trainees/{program_id}/evaluations",
        data={
            "evaluation_date": date.today().isoformat(),
            "attendance_score": 90,
            "performance_score": 90,
            "behavior_score": 90,
            "skill_score": 90,
            "is_final": True,
        },
        content_type="application/json",
    )
    assert eval_resp.status_code == 200
    assert eval_resp.json()["total_score"] == 360

    CleanerDocumentFactory(cleaner=cleaner, status=CleanerDocumentStatus.VERIFIED)
    passed = admin_client.post(
        f"/api/site-management/v1/trainees/{program_id}/pass",
        data={"reason": "Completed training"},
        content_type="application/json",
    )
    assert passed.status_code == 200
    assert passed.json()["status"] == "passed"
    cleaner.refresh_from_db()
    assert cleaner.status == CleanerStatus.ACTIVE

    summary = admin_client.get("/api/site-management/v1/trainees/summary")
    assert summary.status_code == 200
    assert summary.json()["passed"] == 1

    listed = admin_client.get("/api/site-management/v1/trainees", {"status": "passed"})
    assert listed.json()["count"] == 1


@pytest.mark.django_db
def test_trainee_permissions(site, admin_user, viewer_user, zone_user) -> None:
    cleaner = _applicant()
    program = start_trainee_program(
        cleaner=cleaner, site=site, expected_end_date=date.today() + timedelta(days=60), actor=admin_user
    )
    # Viewer read-only: can read, cannot start.
    viewer = UserFactory(role=RoleCode.MANAGEMENT_VIEWER)
    client = _authed(viewer)
    assert client.get("/api/site-management/v1/trainees").status_code == 200
    denied = client.post(
        "/api/site-management/v1/trainees",
        data={"cleaner_id": _applicant().pk, "site_id": site.pk, "expected_end_date": date.today().isoformat()},
        content_type="application/json",
    )
    assert denied.status_code in (401, 403)

    # Zone supervisor (assigned to the site) can manage (evaluate) but not pass.
    ZoneSupervisorAssignmentFactory(zone=site.zone, user=zone_user)
    zone_client = _authed(zone_user)
    evaluated = zone_client.post(
        f"/api/site-management/v1/trainees/{program.pk}/evaluations",
        data={"evaluation_date": date.today().isoformat(), "skill_score": 50},
        content_type="application/json",
    )
    assert evaluated.status_code == 200
    # Final decision requires senior role.
    record_trainee_evaluation(program=program, evaluation_date=date.today(), actor=admin_user, is_final=True)
    CleanerDocumentFactory(cleaner=cleaner, status=CleanerDocumentStatus.VERIFIED)
    denied_pass = zone_client.post(
        f"/api/site-management/v1/trainees/{program.pk}/pass", data={"reason": "x"}, content_type="application/json"
    )
    assert denied_pass.status_code in (401, 403)


@pytest.mark.django_db
def test_trainee_validation_errors(site, admin_user, admin_client) -> None:
    cleaner = _applicant()
    created = admin_client.post(
        "/api/site-management/v1/trainees",
        data={"cleaner_id": cleaner.pk, "site_id": site.pk, "expected_end_date": "2020-01-01"},
        content_type="application/json",
    )
    assert created.status_code in (422, 400)

    program = start_trainee_program(
        cleaner=cleaner, site=site, expected_end_date=date.today() + timedelta(days=60), actor=admin_user
    )
    # Fail without a reason -> 422.
    failed = admin_client.post(
        f"/api/site-management/v1/trainees/{program.pk}/fail", data={"reason": ""}, content_type="application/json"
    )
    assert failed.status_code in (422, 400)


@pytest.mark.django_db
def test_trainee_admin_actions(admin_user) -> None:
    from django.test import Client

    admin = UserFactory(role=RoleCode.SYSTEM_ADMIN, is_staff=True, is_superuser=True)
    client = Client()
    client.force_login(admin)
    site = SiteFactory()
    cleaner = _applicant()
    program = start_trainee_program(
        cleaner=cleaner, site=site, expected_end_date=date.today() + timedelta(days=60), actor=admin
    )
    assert client.get("/admin/site_management/traineeprogram/").status_code == 200

    # Drop via admin action.
    assert (
        client.post(
            "/admin/site_management/traineeprogram/",
            data={"action": "drop_programs", "_selected_action": [program.pk]},
        ).status_code
        == 302
    )
    program.refresh_from_db()
    assert program.status == TraineeProgramStatus.DROPPED
    cleaner.refresh_from_db()
    assert cleaner.status == CleanerStatus.INACTIVE

    # Completed program is readonly and non-deletable.
    from apps.site_management.admin import TraineeProgramAdmin

    admin_model = TraineeProgramAdmin(model=TraineeProgram, admin_site=None)
    assert "status" in admin_model.get_readonly_fields(None, program)
    assert admin_model.has_delete_permission(None, program) is False


@pytest.mark.django_db
def test_trainee_api_remaining_endpoints(site, admin_user, admin_client, site_supervisor_user) -> None:
    cleaner = _applicant()
    created = admin_client.post(
        "/api/site-management/v1/trainees",
        data={
            "cleaner_id": cleaner.pk,
            "site_id": site.pk,
            "expected_end_date": (date.today() + timedelta(days=60)).isoformat(),
        },
        content_type="application/json",
    ).json()
    pid = created["id"]

    detail = admin_client.get(f"/api/site-management/v1/trainees/{pid}")
    assert detail.status_code == 200
    assert detail.json()["id"] == pid

    updated = admin_client.put(
        f"/api/site-management/v1/trainees/{pid}",
        data={"assigned_site_supervisor_id": site_supervisor_user.pk, "notes": "Intensive track"},
        content_type="application/json",
    )
    assert updated.status_code == 200
    assert updated.json()["notes"] == "Intensive track"

    evaluated = admin_client.post(
        f"/api/site-management/v1/trainees/{pid}/evaluations",
        data={"evaluation_date": date.today().isoformat(), "attendance_score": 88},
        content_type="application/json",
    ).json()
    evals = admin_client.get(f"/api/site-management/v1/trainees/{pid}/evaluations")
    assert evals.status_code == 200
    assert len(evals.json()) == 1
    assert evals.json()[0]["id"] == evaluated["id"]

    extended = admin_client.post(
        f"/api/site-management/v1/trainees/{pid}/extend",
        data={"new_expected_end_date": (date.today() + timedelta(days=90)).isoformat(), "reason": "More time"},
        content_type="application/json",
    )
    assert extended.status_code == 200
    assert extended.json()["status"] == "extended"

    invalid = admin_client.post(
        f"/api/site-management/v1/trainees/{pid}/extend",
        data={"new_expected_end_date": (date.today() + timedelta(days=30)).isoformat(), "reason": ""},
        content_type="application/json",
    )
    assert invalid.status_code in (422, 400)

    dropped = admin_client.post(
        f"/api/site-management/v1/trainees/{pid}/drop",
        data={"reason": "Left the island"},
        content_type="application/json",
    )
    assert dropped.status_code == 200
    assert dropped.json()["status"] == "dropped"

    # Re-start a new program, then fail it.
    cleaner2 = _applicant()
    program = start_trainee_program(
        cleaner=cleaner2, site=site, expected_end_date=date.today() + timedelta(days=60), actor=admin_user
    )
    record_trainee_evaluation(program=program, evaluation_date=date.today(), actor=admin_user, is_final=True)
    failed = admin_client.post(
        f"/api/site-management/v1/trainees/{program.pk}/fail",
        data={"reason": "Failed attendance"},
        content_type="application/json",
    )
    assert failed.status_code == 200
    assert failed.json()["status"] == "failed"
    cleaner2.refresh_from_db()
    assert cleaner2.status == CleanerStatus.INACTIVE

    summary = admin_client.get("/api/site-management/v1/trainees/summary")
    assert summary.json()["total_trainees"] == 2


@pytest.mark.django_db
def test_admin_pass_and_fail_actions() -> None:
    from django.test import Client

    admin = UserFactory(role=RoleCode.SYSTEM_ADMIN, is_staff=True, is_superuser=True)
    client = Client()
    client.force_login(admin)
    site = SiteFactory()
    program = start_trainee_program(
        cleaner=_applicant(), site=site, expected_end_date=date.today() + timedelta(days=60), actor=admin
    )
    record_trainee_evaluation(program=program, evaluation_date=date.today(), actor=admin, is_final=True)
    CleanerDocumentFactory(cleaner=program.cleaner, status=CleanerDocumentStatus.VERIFIED)
    assert (
        client.post(
            "/admin/site_management/traineeprogram/",
            data={"action": "pass_programs", "_selected_action": [program.pk]},
        ).status_code
        == 302
    )
    program.refresh_from_db()
    assert program.status == TraineeProgramStatus.PASSED
    assert program.cleaner.status == CleanerStatus.ACTIVE

    fail_program = start_trainee_program(
        cleaner=_applicant(), site=site, expected_end_date=date.today() + timedelta(days=60), actor=admin
    )
    assert (
        client.post(
            "/admin/site_management/traineeprogram/",
            data={"action": "fail_programs", "_selected_action": [fail_program.pk]},
        ).status_code
        == 302
    )
    fail_program.refresh_from_db()
    assert fail_program.status == TraineeProgramStatus.FAILED
    assert fail_program.cleaner.status == CleanerStatus.INACTIVE


@pytest.mark.django_db
def test_hr_bulk_transfer_keeps_trainee_assignment_and_training_scope_in_sync() -> None:
    source = SiteFactory()
    destination = SiteFactory()
    hr = UserFactory(role=RoleCode.HR)
    source_supervisor = UserFactory(role=RoleCode.SITE_SUPERVISOR)
    destination_supervisor = UserFactory(role=RoleCode.SITE_SUPERVISOR)
    SiteSupervisorAssignmentFactory(site=source, user=source_supervisor)
    SiteSupervisorAssignmentFactory(site=destination, user=destination_supervisor)

    trainee = CleanerFactory(status=CleanerStatus.TRAINEE)
    trainee_assignment = CleanerSiteAssignmentFactory(
        cleaner=trainee,
        site=source,
        status=CleanerAssignmentStatus.DRAFT,
        start_date=date.today() - timedelta(days=5),
    )
    trainee_program = TraineeProgramFactory(
        cleaner=trainee,
        site=source,
        status=TraineeProgramStatus.IN_TRAINING,
    )
    active_cleaner = CleanerFactory(status=CleanerStatus.ACTIVE)
    CleanerSiteAssignmentFactory(cleaner=active_cleaner, site=source, status=CleanerAssignmentStatus.ACTIVE)

    transferred = _authed(hr).post(
        "/api/site-management/v1/hr/cleaners/transfer",
        data={
            "cleaner_ids": [trainee.pk, active_cleaner.pk],
            "destination_site_id": destination.pk,
            "effective_date": date.today().isoformat(),
            "reason": "Move both people to the new operating site.",
        },
        content_type="application/json",
    )
    assert transferred.status_code == 200, transferred.content
    assert {item["cleaner_id"] for item in transferred.json()} == {trainee.pk, active_cleaner.pk}

    trainee_assignment.refresh_from_db()
    assert trainee_assignment.status == CleanerAssignmentStatus.ENDED
    assert trainee_assignment.end_date == date.today()
    trainee_program.refresh_from_db()
    assert trainee_program.site_id == destination.pk
    assert trainee_program.assigned_site_supervisor_id is None
    assert "Move both people" in trainee_program.notes
    assert CleanerSiteAssignment.objects.filter(
        cleaner=trainee,
        site=destination,
        status=CleanerAssignmentStatus.DRAFT,
    ).exists()
    assert CleanerSiteAssignment.objects.filter(
        cleaner=active_cleaner,
        site=destination,
        status=CleanerAssignmentStatus.ACTIVE,
    ).exists()

    source_rows = _authed(source_supervisor).get(
        "/api/site-management/v1/trainees", {"status": TraineeProgramStatus.IN_TRAINING}
    )
    destination_rows = _authed(destination_supervisor).get(
        "/api/site-management/v1/trainees", {"status": TraineeProgramStatus.IN_TRAINING}
    )
    assert all(item["id"] != trainee_program.pk for item in source_rows.json()["results"])
    assert any(item["id"] == trainee_program.pk for item in destination_rows.json()["results"])

    registry = _authed(hr).get("/api/site-management/v1/cleaners", {"page_size": 100})
    trainee_row = next(item for item in registry.json()["results"] if item["id"] == trainee.pk)
    assert trainee_row["current_site_name"] == destination.name
    assert trainee_row["training_site_name"] == destination.name
    assert AuditLog.objects.filter(summary__contains="Transferred 2 cleaner(s)").exists()

    denied = _authed(source_supervisor).post(
        "/api/site-management/v1/hr/cleaners/transfer",
        data={
            "cleaner_ids": [trainee.pk],
            "destination_site_id": source.pk,
            "effective_date": date.today().isoformat(),
            "reason": "Not permitted.",
        },
        content_type="application/json",
    )
    assert denied.status_code in (401, 403)
