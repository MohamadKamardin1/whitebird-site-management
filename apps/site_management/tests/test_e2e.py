"""End-to-end flows exercising the full operational backbone.

Each flow drives the real request path (API client → service → DB) and asserts
the end state. Uses the system-admin client so the flows exercise business
logic rather than permission plumbing (permissions are covered separately).
"""

import datetime
from decimal import Decimal

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client

from apps.accounts.models import User
from apps.accounts.services import issue_api_token
from apps.site_management.models import (
    AttendanceRecord,
    AttendanceStatus,
    CleanerStatus,
    Inspection,
    Issue,
    IssueStatus,
    Job,
    JobStatus,
    Site,
    SiteStore,
    TraineeProgramStatus,
)
from apps.site_management.trainee_services import pass_trainee, record_trainee_evaluation, start_trainee_program


@pytest.fixture(autouse=True)
def rbac_seeded(db: None) -> None:
    from django.core.management import call_command

    call_command("seed_rbac")


def _authed(user: User) -> Client:
    return Client(HTTP_AUTHORIZATION=f"Bearer {issue_api_token(user=user, name='e2e').key}")


# --------------------------------------------------------------------------- #
# Flow 1 — full operations cycle
# --------------------------------------------------------------------------- #


@pytest.mark.django_db(transaction=True)
def test_flow1_full_operations_cycle(admin_user) -> None:
    from apps.site_management.attendance_services import bulk_upsert_attendance, generate_daily_attendance_sheet
    from apps.site_management.cleaner_services import register_cleaner, upload_cleaner_document, verify_cleaner_document
    from apps.site_management.inspection_services import (
        add_inspection_result,
        create_template,
        review_inspection,
        start_inspection,
        submit_inspection,
    )
    from apps.site_management.issues_services import (
        assign_job_from_issue,
        close_job,
        complete_job,
        create_issue,
        verify_job,
    )
    from apps.site_management.reporting_services import (
        generate_assistant_summary,
        generate_general_management_report,
        generate_site_report,
        generate_zone_summary,
        review_site_report_by_zone,
        submit_assistant_summary,
        submit_general_management_report,
        submit_site_report,
        submit_zone_summary,
    )
    from apps.site_management.services import create_area, create_shift
    from apps.site_management.store_services import (
        add_store_item,
        create_stock_request,
        submit_stock_request,
    )

    client = _authed(admin_user)
    day = datetime.date.today()

    # --- create zone + site ---
    from apps.site_management.factories import ZoneFactory

    zone = ZoneFactory(name="E2E Zone", code="E2E01")
    zone_id = zone.pk
    site_resp = client.post(
        "/api/site-management/v1/sites",
        data={
            "name": "E2E Site",
            "code": "E2ES01",
            "slug": "e2e-site",
            "zone_id": zone_id,
            "work_mode": "full_time_and_shift",
            "city": "Nungwi",
            "country": "TZ",
        },
        content_type="application/json",
    )
    assert site_resp.status_code == 200
    site_id = site_resp.json()["id"]
    site = Site.objects.get(pk=site_id)

    # --- configure shift + area ---
    create_shift(
        site=site,
        shift_name="AM",
        shift_code="AM",
        start_time=datetime.time(7),
        end_time=datetime.time(15),
        effective_days=["mon"],
        actor=admin_user,
    )
    create_area(site=site, area_name="Lobby", area_code="LB", actor=admin_user)
    area = site.areas.get()

    # --- register cleaner + verify document ---
    cleaner = register_cleaner(
        first_name="E2E",
        last_name="Cleaner",
        id_type="nida",
        id_number="E2E000001",
        gender="female",
        birth_date=datetime.date(1990, 1, 1),
        actor=admin_user,
    )
    from apps.site_management.models import CleanerDocumentType

    document = upload_cleaner_document(
        cleaner=cleaner,
        uploaded_file=SimpleUploadedFile("id.pdf", b"%PDF-1.4 e2e", content_type="application/pdf"),
        document_type=CleanerDocumentType.NIDA,
        actor=admin_user,
    )
    verify_cleaner_document(document=document, actor=admin_user)
    cleaner.refresh_from_db()
    assert cleaner.has_verified_id is True

    # --- assign cleaner + attendance ---
    from apps.site_management.assignment_services import assign_cleaner_to_site
    from apps.site_management.models import CleanerAssignmentType

    assign_cleaner_to_site(
        cleaner=cleaner,
        site=site,
        assignment_type=CleanerAssignmentType.FULL_TIME,
        start_date=day,
        actor=admin_user,
    )
    generate_daily_attendance_sheet(site_id=site.pk, day=day, actor=admin_user)
    bulk_upsert_attendance(
        site_id=site.pk,
        day=day,
        user=admin_user,
        entries=[{"cleaner_id": cleaner.pk, "status": AttendanceStatus.PRESENT}],
    )
    assert AttendanceRecord.objects.filter(site=site, attendance_date=day, status=AttendanceStatus.PRESENT).exists()

    # --- inspection ---
    template = create_template(
        template_name="E2E Audit",
        actor=admin_user,
        site=site,
        items=[{"item_label": "Clean", "item_type": "pass_fail", "sequence": 1}],
    )
    inspection = start_inspection(site=site, area=area, template=template, inspected_by=admin_user, actor=admin_user)
    add_inspection_result(inspection=inspection, template_item=template.items.get(), actor=admin_user, passed=True)
    submit_inspection(inspection=inspection, actor=admin_user)
    review_inspection(inspection=inspection, actor=admin_user)
    assert Inspection.objects.get(pk=inspection.pk).status == "reviewed"

    # --- issue + job lifecycle ---
    issue = create_issue(
        title="E2E leak", site=site, raised_by=admin_user, actor=admin_user, issue_category="maintenance"
    )
    job = assign_job_from_issue(issue=issue, actor=admin_user, assigned_to_user=admin_user)
    from apps.site_management.issues_services import start_job

    start_job(job=job, actor=admin_user)
    complete_job(job=job, actor=admin_user, completion_notes="Fixed")
    verify_job(job=job, actor=admin_user)
    close_job(job=job, actor=admin_user)
    assert Job.objects.get(pk=job.pk).status == JobStatus.CLOSED
    assert Issue.objects.get(pk=issue.pk).status == IssueStatus.CLOSED

    # --- reporting chain ---
    report = generate_site_report(site_id=site.pk, day=day, user=admin_user)
    submit_site_report(report=report, user=admin_user)
    review_site_report_by_zone(report=report, user=admin_user)
    assert site.zone_id is not None
    zone_report = generate_zone_summary(zone_id=site.zone_id, day=day, user=admin_user)
    submit_zone_summary(report=zone_report, user=admin_user)
    assistant = generate_assistant_summary(day=day, user=admin_user, zone_ids=[site.zone_id])
    submit_assistant_summary(report=assistant, user=admin_user)
    general = generate_general_management_report(day=day, user=admin_user)
    submit_general_management_report(report=general, user=admin_user)
    assert general.status == "submitted_to_management"

    # --- store: receive + low-stock request ---
    store = SiteStore.objects.create(site=site, store_name="Main", created_by=admin_user)
    item = add_store_item(
        store=store, item_name="Bleach", actor=admin_user, opening_stock=Decimal("2"), minimum_stock_level=Decimal("5")
    )
    assert item.low_stock is True
    request = create_stock_request(
        site=site,
        store=store,
        actor=admin_user,
        items=[{"store_item_id": item.pk, "requested_quantity": Decimal("20")}],
        request_date=day,
    )
    submit_stock_request(request=request, actor=admin_user)
    assert request.status == "submitted"


# --------------------------------------------------------------------------- #
# Flow 2 — trainee lifecycle
# --------------------------------------------------------------------------- #


@pytest.mark.django_db(transaction=True)
def test_flow2_trainee_to_active_cleaner(site, admin_user) -> None:
    from apps.site_management.cleaner_services import register_cleaner, upload_cleaner_document, verify_cleaner_document
    from apps.site_management.trainee_services import fail_trainee

    cleaner = register_cleaner(
        first_name="Trainee",
        last_name="One",
        id_type="nida",
        id_number="TRN000001",
        gender="male",
        birth_date=datetime.date(1995, 1, 1),
        actor=admin_user,
    )
    assert cleaner.status == CleanerStatus.APPLICANT

    program = start_trainee_program(
        cleaner=cleaner,
        site=site,
        expected_end_date=datetime.date.today() + datetime.timedelta(days=60),
        actor=admin_user,
    )
    assert program.status == TraineeProgramStatus.IN_TRAINING
    cleaner.refresh_from_db()
    assert cleaner.status == CleanerStatus.TRAINEE

    record_trainee_evaluation(
        program=program, evaluation_date=datetime.date.today(), actor=admin_user, skill_score=90, is_final=True
    )
    from apps.site_management.models import CleanerDocumentType

    doc = upload_cleaner_document(
        cleaner=cleaner,
        uploaded_file=SimpleUploadedFile("id.pdf", b"%PDF-1.4 trainee", content_type="application/pdf"),
        document_type=CleanerDocumentType.NIDA,
        actor=admin_user,
    )
    verify_cleaner_document(document=doc, actor=admin_user)

    passed = pass_trainee(program=program, actor=admin_user)
    assert passed.status == TraineeProgramStatus.PASSED
    cleaner.refresh_from_db()
    assert cleaner.status == CleanerStatus.ACTIVE

    # Rejected path: another applicant fails and drops to inactive.
    cleaner2 = register_cleaner(
        first_name="Trainee",
        last_name="Two",
        id_type="nida",
        id_number="TRN000002",
        gender="female",
        birth_date=datetime.date(1993, 1, 1),
        actor=admin_user,
    )
    program2 = start_trainee_program(
        cleaner=cleaner2,
        site=site,
        expected_end_date=datetime.date.today() + datetime.timedelta(days=60),
        actor=admin_user,
    )
    fail_trainee(program=program2, actor=admin_user, reason="Attendance")
    cleaner2.refresh_from_db()
    assert cleaner2.status == CleanerStatus.INACTIVE


# --------------------------------------------------------------------------- #
# Flow 3 — store low stock + request workflow
# --------------------------------------------------------------------------- #


@pytest.mark.django_db(transaction=True)
def test_flow3_store_low_stock_and_request(site, admin_user) -> None:
    from apps.site_management.store_services import (
        add_store_item,
        complete_stock_request,
        create_stock_request,
        issue_stock,
        review_stock_request,
        submit_stock_request,
    )

    store = SiteStore.objects.create(site=site, store_name="Pantry", created_by=admin_user)
    item = add_store_item(
        store=store, item_name="Soap", actor=admin_user, opening_stock=Decimal("4"), minimum_stock_level=Decimal("5")
    )
    assert item.low_stock is True

    issue_stock(store_item=item, quantity=Decimal("2"), actor=admin_user)
    item.refresh_from_db()
    assert item.current_stock == Decimal("2")

    request = create_stock_request(
        site=site,
        store=store,
        actor=admin_user,
        items=[{"store_item_id": item.pk, "requested_quantity": Decimal("10")}],
        request_date=datetime.date.today(),
    )
    submit_stock_request(request=request, actor=admin_user)
    request_item = request.items.first()
    assert request_item is not None
    review_stock_request(
        request=request,
        actor=admin_user,
        approved=[{"item_id": request_item.pk, "approved_quantity": Decimal("2")}],
    )
    complete_stock_request(request=request, actor=admin_user)
    item.refresh_from_db()
    assert item.current_stock == Decimal("0")  # 2 issued earlier + 2 issued on completion
    assert request.status == "completed"


@pytest.mark.django_db(transaction=True)
def test_seed_demo_command() -> None:
    from django.core.management import call_command

    from apps.site_management.models import AttendanceRecord, Cleaner, Site, TraineeProgram

    call_command("seed_demo", sites=1, cleaners=2)
    assert Site.objects.count() == 1
    assert Cleaner.objects.count() >= 2
    assert AttendanceRecord.objects.count() >= 1
    assert TraineeProgram.objects.count() >= 1
    assert User.objects.filter(email="admin@whitebird.local").exists()
    # Idempotent on a second run.
    call_command("seed_demo", sites=1, cleaners=2)
    assert Site.objects.count() == 1
