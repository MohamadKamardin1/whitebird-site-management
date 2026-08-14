"""Tests for the reporting chain engine."""

from datetime import date, timedelta
from decimal import Decimal
from typing import Any

import pytest
from django.core.exceptions import ValidationError
from django.test import Client

from apps.accounts.factories import UserFactory
from apps.accounts.models import RoleCode, User
from apps.accounts.services import issue_api_token
from apps.core.models import DomainEvent
from apps.site_management.factories import (
    CleanerFactory,
    SiteAreaFactory,
    SiteStoreFactory,
    SiteSupervisorAssignmentFactory,
    ZoneSupervisorAssignmentFactory,
)
from apps.site_management.models import (
    AssistantReportStatus,
    AttendanceRecord,
    AttendanceStatus,
    CleanerAssignmentStatus,
    CleanerSiteAssignment,
    CleanerStatus,
    DailySiteReport,
    GeneralReportStatus,
    InspectionOverallStatus,
    Issue,
    IssueStatus,
    SiteReportStatus,
    ZoneReportStatus,
)
from apps.site_management.reporting_selectors import (
    missing_site_reports,
    reporting_status_dashboard,
    site_report_detail,
)
from apps.site_management.reporting_services import (
    generate_assistant_summary,
    generate_general_management_report,
    generate_site_report,
    generate_zone_summary,
    recalculate_report_snapshots,
    return_assistant_summary,
    return_site_report,
    return_zone_summary,
    submit_assistant_summary,
    submit_general_management_report,
    submit_site_report,
    submit_zone_summary,
)


@pytest.fixture(autouse=True)
def rbac_seeded(db: None) -> None:
    from django.core.management import call_command

    call_command("seed_rbac")


def _authed(user: User) -> Client:
    return Client(HTTP_AUTHORIZATION=f"Bearer {issue_api_token(user=user, name='test').key}")


def _seed_site_data(site: Any, admin_user: Any, day: date) -> None:
    cleaner = CleanerFactory(status=CleanerStatus.ACTIVE)
    CleanerSiteAssignment.objects.create(
        cleaner=cleaner,
        site=site,
        assignment_type="full_time",
        start_date=day - timedelta(days=10),
        status=CleanerAssignmentStatus.ACTIVE,
        assigned_by=admin_user,
    )
    AttendanceRecord.objects.create(
        cleaner=cleaner,
        site=site,
        attendance_date=day,
        status=AttendanceStatus.PRESENT,
        review_status="submitted",
        recorded_by=admin_user,
    )
    store = SiteStoreFactory(site=site)
    from apps.site_management.store_services import add_store_item, issue_stock

    item = add_store_item(store=store, item_name="Soap", actor=admin_user, opening_stock=Decimal("10"))
    issue_stock(store_item=item, quantity=Decimal("2"), actor=admin_user, movement_date=day)

    from apps.site_management.inspection_services import create_template, start_inspection

    template = create_template(
        template_name="Audit",
        actor=admin_user,
        site=site,
        items=[{"item_label": "Clean", "item_type": "pass_fail", "sequence": 1}],
    )
    inspection = start_inspection(
        site=site,
        area=SiteAreaFactory(site=site),
        template=template,
        inspected_by=admin_user,
        actor=admin_user,
        inspection_date=day,
    )
    inspection.overall_status = InspectionOverallStatus.PASSED
    inspection.status = "submitted"
    inspection.save(update_fields=["overall_status", "status"])

    from apps.site_management.trainee_services import start_trainee_program

    trainee = CleanerFactory(status=CleanerStatus.APPLICANT)
    start_trainee_program(
        cleaner=trainee,
        site=site,
        expected_end_date=day + timedelta(days=60),
        actor=admin_user,
        start_date=day - timedelta(days=5),
    )

    Issue.objects.create(
        title="Leak",
        site=site,
        source="manual",
        issue_category="maintenance",
        priority="urgent",
        status=IssueStatus.OPEN,
        raised_by=admin_user,
        created_by=admin_user,
    )


@pytest.mark.django_db
def test_site_report_generation_aggregates(site, admin_user) -> None:
    day = date.today()
    _seed_site_data(site, admin_user, day)
    report = generate_site_report(site_id=site.pk, day=day, user=admin_user)
    assert report.status == SiteReportStatus.DRAFT
    assert report.attendance_summary["present"] == 1
    assert report.store_summary["issued"] == 1
    assert report.inspection_summary["total"] == 1
    assert report.inspection_summary["passed"] == 1
    assert report.trainee_summary["in_training"] == 1
    assert report.issues_summary["open"] == 1
    assert report.issues_summary["urgent"] == 1

    # Recalculation refreshes a draft.
    recalculated = recalculate_report_snapshots(day=day, user=admin_user)
    assert recalculated == 1


@pytest.mark.django_db
def test_missing_data_handling(site, admin_user) -> None:
    day = date.today()
    report = generate_site_report(site_id=site.pk, day=day, user=admin_user)
    assert report.attendance_summary["total"] == 0
    assert report.attendance_summary["attendance_rate"] == 0.0
    assert report.store_summary["movements"] == 0
    assert report.inspection_summary["total"] == 0


@pytest.mark.django_db(transaction=True)
def test_submit_stores_immutable_snapshot(site, admin_user) -> None:
    day = date.today()
    _seed_site_data(site, admin_user, day)
    report = generate_site_report(site_id=site.pk, day=day, user=admin_user)
    submitted = submit_site_report(report=report, user=admin_user)
    assert submitted.status == SiteReportStatus.SUBMITTED
    assert submitted.submitted_at is not None
    assert submitted.snapshot["attendance"]["present"] == 1
    assert DomainEvent.objects.filter(event_type="SiteReportSubmitted").exists()

    # Regeneration of a submitted report is blocked.
    with pytest.raises(ValidationError):
        generate_site_report(site_id=site.pk, day=day, user=admin_user)

    # Snapshot is unchanged after the underlying data changes.
    before = dict(submitted.snapshot)
    _seed_site_data(site, admin_user, day)
    detail = site_report_detail(site.pk, day)
    assert detail is not None
    assert detail.snapshot == before


@pytest.mark.django_db
def test_return_and_resubmit_flow(site, admin_user, zone_user) -> None:
    day = date.today()
    report = generate_site_report(site_id=site.pk, day=day, user=admin_user)
    submit_site_report(report=report, user=admin_user)
    with pytest.raises(ValidationError):
        return_site_report(report=report, user=zone_user, reason="")
    returned = return_site_report(report=report, user=zone_user, reason="Missing photo evidence")
    assert returned.status == SiteReportStatus.RETURNED
    assert returned.returned_reason == "Missing photo evidence"
    assert returned.snapshot  # history preserved

    # Resubmit after return.
    resubmitted = submit_site_report(report=report, user=admin_user)
    assert resubmitted.status == SiteReportStatus.SUBMITTED


@pytest.mark.django_db
def test_zone_summary_generation(site, admin_user, zone_user) -> None:
    ZoneSupervisorAssignmentFactory(zone=site.zone, user=zone_user)
    day = date.today()
    report = generate_site_report(site_id=site.pk, day=day, user=admin_user)
    submit_site_report(report=report, user=admin_user)

    zone_report = generate_zone_summary(zone_id=site.zone_id, day=day, user=zone_user)
    assert len(zone_report.site_reports) == 1
    assert zone_report.site_reports[0]["site_name"] == site.name
    assert zone_report.status == ZoneReportStatus.DRAFT

    # Review the site report at zone level then regenerate (prefers reviewed reports).
    from apps.site_management.reporting_services import review_site_report_by_zone

    review_site_report_by_zone(report=report, user=zone_user)
    zone_report = generate_zone_summary(zone_id=site.zone_id, day=day, user=zone_user)
    assert len(zone_report.site_reports) == 1

    submitted = submit_zone_summary(report=zone_report, user=zone_user)
    assert submitted.status == ZoneReportStatus.SUBMITTED


@pytest.mark.django_db(transaction=True)
def test_assistant_summary_extraction(site, admin_user, zone_user, general_user) -> None:
    ZoneSupervisorAssignmentFactory(zone=site.zone, user=zone_user)
    day = date.today()
    report = generate_site_report(site_id=site.pk, day=day, user=admin_user)
    submit_site_report(report=report, user=admin_user)
    from apps.site_management.reporting_services import review_site_report_by_zone

    review_site_report_by_zone(report=report, user=zone_user)
    zone_report = generate_zone_summary(zone_id=site.zone_id, day=day, user=zone_user)
    submit_zone_summary(report=zone_report, user=zone_user)

    assistant = generate_assistant_summary(day=day, user=general_user, zone_ids=[site.zone_id])
    assert site.zone_id in assistant.zone_ids
    assert assistant.problems_extracted == []  # no urgent/escalated issues in seeded data
    assert assistant.status == AssistantReportStatus.DRAFT

    submitted = submit_assistant_summary(report=assistant, user=general_user)
    assert submitted.status == AssistantReportStatus.SUBMITTED
    assert DomainEvent.objects.filter(event_type="AssistantReportSubmitted").exists()


@pytest.mark.django_db(transaction=True)
def test_general_report_final_submission(site, admin_user, zone_user, general_user) -> None:
    day = date.today()
    ZoneSupervisorAssignmentFactory(zone=site.zone, user=zone_user)
    report = generate_site_report(site_id=site.pk, day=day, user=admin_user)
    submit_site_report(report=report, user=admin_user)
    from apps.site_management.reporting_services import review_site_report_by_zone

    review_site_report_by_zone(report=report, user=zone_user)
    zone_report = generate_zone_summary(zone_id=site.zone_id, day=day, user=zone_user)
    submit_zone_summary(report=zone_report, user=zone_user)
    assistant = generate_assistant_summary(day=day, user=general_user, zone_ids=[site.zone_id])
    submit_assistant_summary(report=assistant, user=general_user)

    general = generate_general_management_report(day=day, user=general_user)
    assert general.status == GeneralReportStatus.DRAFT
    assert general.assigned_jobs == []
    assert general.key_issues == []

    submitted = submit_general_management_report(report=general, user=general_user)
    assert submitted.status == GeneralReportStatus.SUBMITTED_TO_MANAGEMENT
    assert DomainEvent.objects.filter(event_type="GeneralReportSubmitted").exists()


@pytest.mark.django_db
def test_report_status_transitions(site, admin_user, zone_user, general_user) -> None:
    day = date.today()
    report = generate_site_report(site_id=site.pk, day=day, user=admin_user)
    submit_site_report(report=report, user=admin_user)
    from apps.site_management.reporting_services import review_site_report_by_zone

    review_site_report_by_zone(report=report, user=zone_user)
    assert report.status == SiteReportStatus.ZONE_REVIEWED

    # Invalid transition (skipping a level) blocked.
    from apps.site_management.reporting_services import _advance_site_report

    with pytest.raises(ValidationError):
        _advance_site_report(report, admin_user, SiteReportStatus.GENERAL_APPROVED)
    _advance_site_report(report, admin_user, SiteReportStatus.ASSISTANT_REVIEWED)
    assert report.status == SiteReportStatus.ASSISTANT_REVIEWED
    _advance_site_report(report, admin_user, SiteReportStatus.GENERAL_APPROVED)
    _advance_site_report(report, admin_user, SiteReportStatus.MANAGEMENT_SUBMITTED)
    assert report.status == SiteReportStatus.MANAGEMENT_SUBMITTED

    # Return flows.
    zone_report = generate_zone_summary(zone_id=site.zone_id, day=day, user=zone_user)
    submit_zone_summary(report=zone_report, user=zone_user)
    returned = return_zone_summary(report=zone_report, user=general_user, reason="rework")
    assert returned.status == ZoneReportStatus.RETURNED

    assistant = generate_assistant_summary(day=day, user=general_user)
    submit_assistant_summary(report=assistant, user=general_user)
    returned_a = return_assistant_summary(report=assistant, user=general_user, reason="rework")
    assert returned_a.status == AssistantReportStatus.RETURNED


# --------------------------------------------------------------------------- #
# Selectors
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
def test_missing_and_status_dashboard(site, admin_user, zone_user) -> None:
    day = date.today()
    missing = missing_site_reports(admin_user, day)
    assert {m["site_id"] for m in missing} == {site.pk}

    generate_site_report(site_id=site.pk, day=day, user=admin_user)
    submit_site_report(report=site_report_detail(site.pk, day), user=admin_user)
    assert missing_site_reports(admin_user, day) == []

    dashboard = reporting_status_dashboard(admin_user, day)
    assert dashboard["site_reports"][0]["status"] == SiteReportStatus.SUBMITTED
    assert dashboard["missing_site_reports"] == []

    # Zone-scoped user sees their zone only.
    ZoneSupervisorAssignmentFactory(zone=site.zone, user=zone_user)
    assert {m["site_id"] for m in missing_site_reports(zone_user, day)} == set()


# --------------------------------------------------------------------------- #
# Permissions & API
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
def test_api_site_report_flow(site, admin_user, admin_client, zone_user, site_supervisor_user) -> None:
    SiteSupervisorAssignmentFactory(site=site, user=site_supervisor_user)
    sup = _authed(site_supervisor_user)
    day = date.today().isoformat()

    generated = sup.post(f"/api/site-management/v1/reports/site/{site.pk}/{day}/generate")
    assert generated.status_code == 200
    assert generated.json()["status"] == "draft"

    detail = admin_client.get(f"/api/site-management/v1/reports/site/{site.pk}/{day}")
    assert detail.status_code == 200

    submitted = sup.post(f"/api/site-management/v1/reports/site/{site.pk}/{day}/submit")
    assert submitted.status_code == 200
    assert submitted.json()["status"] == "submitted"

    # Unassigned site supervisor cannot generate a report for the site.
    outsider = UserFactory(role=RoleCode.SITE_SUPERVISOR)
    assert _authed(outsider).post(f"/api/site-management/v1/reports/site/{site.pk}/{day}/generate").status_code in (
        401,
        403,
    )

    # Zone supervisor returns the report.
    ZoneSupervisorAssignmentFactory(zone=site.zone, user=zone_user)
    returned = _authed(zone_user).post(
        f"/api/site-management/v1/reports/site/{site.pk}/{day}/return",
        data={"reason": "needs work"},
        content_type="application/json",
    )
    assert returned.status_code == 200
    assert returned.json()["status"] == "returned"

    listed = admin_client.get("/api/site-management/v1/reports/site")
    assert listed.status_code == 200

    status = admin_client.get("/api/site-management/v1/reports/status")
    assert status.status_code == 200
    missing = admin_client.get("/api/site-management/v1/reports/missing")
    assert missing.status_code == 200


@pytest.mark.django_db
def test_api_higher_report_flow(site, admin_user, admin_client, general_user, zone_user) -> None:
    ZoneSupervisorAssignmentFactory(zone=site.zone, user=zone_user)
    day = date.today()
    zone_report = generate_zone_summary(zone_id=site.zone_id, day=day, user=zone_user)
    zone_id = zone_report.pk

    submitted = _authed(zone_user).post(f"/api/site-management/v1/reports/zone/{zone_id}/submit")
    assert submitted.status_code == 200
    assert submitted.json()["status"] == "submitted"

    assistant = _authed(general_user).post(
        "/api/site-management/v1/reports/assistant/generate",
        data={"report_date": day.isoformat(), "zone_ids": [site.zone_id]},
        content_type="application/json",
    )
    assert assistant.status_code == 200
    assistant_id = assistant.json()["id"]
    assert (
        _authed(general_user).post(f"/api/site-management/v1/reports/assistant/{assistant_id}/submit").json()["status"]
        == "submitted"
    )

    general = _authed(general_user).post(
        "/api/site-management/v1/reports/general/generate",
        data={"report_date": day.isoformat()},
        content_type="application/json",
    )
    assert general.status_code == 200
    general_id = general.json()["id"]
    submitted_general = _authed(general_user).post(f"/api/site-management/v1/reports/general/{general_id}/submit")
    assert submitted_general.json()["status"] == "submitted_to_management"

    # Viewer read-only on reports.
    viewer = UserFactory(role=RoleCode.MANAGEMENT_VIEWER)
    v = _authed(viewer)
    assert v.get("/api/site-management/v1/reports/site").status_code == 200
    assert v.get("/api/site-management/v1/reports/status").status_code == 200


@pytest.mark.django_db
def test_api_validation_and_permissions(site, admin_user, admin_client) -> None:
    day = date.today()
    # Generate on a non-existent site -> 404.
    assert (
        admin_client.post(
            "/api/site-management/v1/reports/site/99999/{day}/generate".replace("{day}", day.isoformat())
        ).status_code
        == 404
    )

    # Zone supervisor cannot author the general report.
    zone_user = UserFactory(role=RoleCode.ZONE_SUPERVISOR)
    assert _authed(zone_user).post(
        "/api/site-management/v1/reports/general/generate",
        data={"report_date": day.isoformat()},
        content_type="application/json",
    ).status_code in (401, 403)


@pytest.mark.django_db
def test_admin_views(site, admin_user) -> None:
    from django.test import Client

    admin = UserFactory(role=RoleCode.SYSTEM_ADMIN, is_staff=True, is_superuser=True)
    client = Client()
    client.force_login(admin)
    day = date.today()
    generate_site_report(site_id=site.pk, day=day, user=admin_user)
    assert client.get("/admin/site_management/dailysitereport/").status_code == 200
    assert client.get("/admin/site_management/zonesummaryreport/").status_code == 200
    assert client.get("/admin/site_management/assistantgeneralsummaryreport/").status_code == 200
    assert client.get("/admin/site_management/generalmanagementreport/").status_code == 200

    report = site_report_detail(site.pk, day)
    assert report is not None
    # Submit via admin action.
    assert (
        client.post(
            "/admin/site_management/dailysitereport/",
            data={"action": "submit_reports", "_selected_action": [report.pk]},
        ).status_code
        == 302
    )
    report.refresh_from_db()
    assert report.status == SiteReportStatus.SUBMITTED

    # Submitted reports cannot be deleted.
    from apps.site_management.admin import DailySiteReportAdmin

    r_admin = DailySiteReportAdmin(model=DailySiteReport, admin_site=None)
    assert r_admin.has_delete_permission(None, report) is False


@pytest.mark.django_db
def test_report_validation_branches(site, admin_user, zone_user, general_user) -> None:
    day = date.today()
    draft = generate_site_report(site_id=site.pk, day=day, user=admin_user)
    # Cannot return a draft.
    with pytest.raises(ValidationError):
        return_site_report(report=draft, user=zone_user, reason="x")

    submitted = submit_site_report(report=draft, user=admin_user)
    from apps.site_management.reporting_services import review_site_report_by_zone

    review_site_report_by_zone(report=submitted, user=zone_user)
    # Cannot submit again once reviewed.
    with pytest.raises(ValidationError):
        submit_site_report(report=submitted, user=admin_user)

    # Zone summary: regenerate non-draft blocked; submit twice blocked.
    zone_report = generate_zone_summary(zone_id=site.zone_id, day=day, user=zone_user)
    submit_zone_summary(report=zone_report, user=zone_user)
    with pytest.raises(ValidationError):
        generate_zone_summary(zone_id=site.zone_id, day=day, user=zone_user)
    with pytest.raises(ValidationError):
        submit_zone_summary(report=zone_report, user=zone_user)

    # Assistant: regenerate submitted blocked; submit twice blocked; return draft blocked.
    assistant = generate_assistant_summary(day=day, user=general_user)
    submit_assistant_summary(report=assistant, user=general_user)
    with pytest.raises(ValidationError):
        generate_assistant_summary(day=day, user=general_user)
    with pytest.raises(ValidationError):
        submit_assistant_summary(report=assistant, user=general_user)
    # A draft assistant summary cannot be returned.
    draft_assistant = generate_assistant_summary(day=day + timedelta(days=1), user=general_user)
    with pytest.raises(ValidationError):
        return_assistant_summary(report=draft_assistant, user=general_user, reason="x")

    # General: regenerate submitted blocked; submit twice blocked.
    general = generate_general_management_report(day=day, user=general_user)
    submit_general_management_report(report=general, user=general_user)
    with pytest.raises(ValidationError):
        generate_general_management_report(day=day, user=general_user)
    with pytest.raises(ValidationError):
        submit_general_management_report(report=general, user=general_user)


@pytest.mark.django_db
def test_general_report_includes_assigned_jobs(site, admin_user, general_user) -> None:
    from apps.site_management.issues_services import create_job

    cleaner = CleanerFactory(status=CleanerStatus.ACTIVE)
    create_job(
        job_title="Clean pool",
        site=site,
        assigned_by=general_user,
        actor=general_user,
        assigned_to_cleaner=cleaner,
        due_date=date.today() + timedelta(days=2),
    )
    general = generate_general_management_report(day=date.today(), user=general_user)
    assert len(general.assigned_jobs) == 1
    assert general.assigned_jobs[0]["assignee"] == cleaner.full_name


@pytest.mark.django_db
def test_admin_report_actions(site, admin_user, general_user, zone_user) -> None:
    from django.test import Client

    admin = UserFactory(role=RoleCode.SYSTEM_ADMIN, is_staff=True, is_superuser=True)
    client = Client()
    client.force_login(admin)
    day = date.today()

    # Daily site report return action.
    report = generate_site_report(site_id=site.pk, day=day, user=admin_user)
    submit_site_report(report=report, user=admin_user)
    assert (
        client.post(
            "/admin/site_management/dailysitereport/",
            data={"action": "return_reports", "_selected_action": [report.pk]},
        ).status_code
        == 302
    )
    report.refresh_from_db()
    assert report.status == SiteReportStatus.RETURNED

    # Zone summary submit + return actions.
    zone_report = generate_zone_summary(zone_id=site.zone_id, day=day, user=zone_user)
    assert (
        client.post(
            "/admin/site_management/zonesummaryreport/",
            data={"action": "submit_zone_reports", "_selected_action": [zone_report.pk]},
        ).status_code
        == 302
    )
    zone_report.refresh_from_db()
    assert zone_report.status == ZoneReportStatus.SUBMITTED
    assert (
        client.post(
            "/admin/site_management/zonesummaryreport/",
            data={"action": "return_zone_reports", "_selected_action": [zone_report.pk]},
        ).status_code
        == 302
    )
    zone_report.refresh_from_db()
    assert zone_report.status == ZoneReportStatus.RETURNED

    # Assistant summary submit + return actions.
    assistant = generate_assistant_summary(day=day, user=general_user)
    assert (
        client.post(
            "/admin/site_management/assistantgeneralsummaryreport/",
            data={"action": "submit_assistant_reports", "_selected_action": [assistant.pk]},
        ).status_code
        == 302
    )
    assistant.refresh_from_db()
    assert assistant.status == AssistantReportStatus.SUBMITTED
    assert (
        client.post(
            "/admin/site_management/assistantgeneralsummaryreport/",
            data={"action": "return_assistant_reports", "_selected_action": [assistant.pk]},
        ).status_code
        == 302
    )
    assistant.refresh_from_db()
    assert assistant.status == AssistantReportStatus.RETURNED

    # General report submit action.
    general = generate_general_management_report(day=day, user=general_user)
    assert (
        client.post(
            "/admin/site_management/generalmanagementreport/",
            data={"action": "submit_general_reports", "_selected_action": [general.pk]},
        ).status_code
        == 302
    )
    general.refresh_from_db()
    assert general.status == GeneralReportStatus.SUBMITTED_TO_MANAGEMENT
