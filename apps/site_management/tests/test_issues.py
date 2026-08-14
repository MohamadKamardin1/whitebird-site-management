"""Tests for issue tracking and job/work order workflow."""

from datetime import date, timedelta
from typing import Any

import pytest
from constance.test import override_config
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client

from apps.accounts.factories import UserFactory
from apps.accounts.models import RoleCode, User
from apps.accounts.services import issue_api_token
from apps.core.models import DomainEvent
from apps.site_management.factories import (
    CleanerFactory,
    SiteAreaFactory,
    SiteSupervisorAssignmentFactory,
    ZoneSupervisorAssignmentFactory,
)
from apps.site_management.inspection_services import create_template, start_inspection
from apps.site_management.issues_selectors import (
    IssueFilter,
    JobFilter,
    issue_list,
    issue_summary,
    job_list,
    job_summary,
    overdue_jobs,
)
from apps.site_management.issues_services import (
    assign_job,
    assign_job_from_issue,
    close_job,
    complete_job,
    create_issue,
    create_job,
    escalate_issue,
    reopen_job,
    review_issue,
    start_job,
    update_issue,
    update_job,
    upload_job_photo,
    verify_job,
)
from apps.site_management.models import (
    CleanerStatus,
    Issue,
    IssueSource,
    IssueStatus,
    JobStatus,
)


@pytest.fixture(autouse=True)
def rbac_seeded(db: None) -> None:
    from django.core.management import call_command

    call_command("seed_rbac")


def _authed(user: User) -> Client:
    return Client(HTTP_AUTHORIZATION=f"Bearer {issue_api_token(user=user, name='test').key}")


def _make_issue(site: Any, actor: Any, **kwargs: Any) -> Issue:
    return create_issue(title="Broken AC", site=site, raised_by=actor, actor=actor, **kwargs)


# --------------------------------------------------------------------------- #
# Issue lifecycle
# --------------------------------------------------------------------------- #


@pytest.mark.django_db(transaction=True)
def test_create_issue_from_manual_and_inspection(site, admin_user) -> None:
    manual = _make_issue(site, admin_user, source=IssueSource.MANUAL, priority="urgent")
    assert manual.status == IssueStatus.OPEN
    assert manual.escalation_level == 0
    assert DomainEvent.objects.filter(event_type="IssueCreated", aggregate_id=str(manual.pk)).exists()

    # From inspection source.
    template = create_template(
        template_name="Audit",
        actor=admin_user,
        site=site,
        items=[{"item_label": "Clean", "item_type": "pass_fail", "sequence": 1}],
    )
    area = SiteAreaFactory(site=site)
    inspection = start_inspection(site=site, area=area, template=template, inspected_by=admin_user, actor=admin_user)
    from_inspection = create_issue(
        title="From inspection",
        site=site,
        raised_by=admin_user,
        actor=admin_user,
        source=IssueSource.INSPECTION,
        inspection=inspection,
        issue_category="cleaning_quality",
    )
    assert from_inspection.inspection_id == inspection.pk
    assert from_inspection.source == IssueSource.INSPECTION


@pytest.mark.django_db
def test_update_and_review_issue(site, admin_user, zone_user) -> None:
    issue = _make_issue(site, admin_user, priority="low")
    updated = update_issue(issue=issue, actor=admin_user, priority="high", title="Broken AC v2")
    assert updated.priority == "high"
    assert updated.title == "Broken AC v2"

    reviewed = review_issue(issue=issue, actor=zone_user, notes="Confirmed")
    assert reviewed.status == IssueStatus.UNDER_REVIEW
    with pytest.raises(ValidationError):
        review_issue(issue=issue, actor=zone_user)


@pytest.mark.django_db(transaction=True)
def test_escalate_issue(site, admin_user, general_user) -> None:
    issue = _make_issue(site, admin_user)
    with pytest.raises(ValidationError):
        escalate_issue(issue=issue, actor=general_user, reason="")
    escalated = escalate_issue(issue=issue, actor=general_user, reason="Unresolved for a week")
    assert escalated.escalation_level == 1
    assert escalated.is_escalated is True
    assert DomainEvent.objects.filter(event_type="IssueEscalated", aggregate_id=str(issue.pk)).exists()


@pytest.mark.django_db
def test_update_closed_issue_rejected(site, admin_user) -> None:
    issue = _make_issue(site, admin_user)
    issue.status = IssueStatus.CLOSED
    issue.save(update_fields=["status"])
    with pytest.raises(ValidationError):
        update_issue(issue=issue, actor=admin_user, priority="high")


# --------------------------------------------------------------------------- #
# Job lifecycle
# --------------------------------------------------------------------------- #


@pytest.mark.django_db(transaction=True)
def test_job_full_lifecycle(site, admin_user, general_user) -> None:
    cleaner = CleanerFactory(status=CleanerStatus.ACTIVE)
    issue = _make_issue(site, admin_user)
    job = assign_job_from_issue(issue=issue, actor=general_user, assigned_to_cleaner=cleaner)
    assert job.status == JobStatus.ASSIGNED
    assert job.assigned_to_cleaner_id == cleaner.pk
    issue.refresh_from_db()
    assert issue.status == IssueStatus.ASSIGNED
    assert DomainEvent.objects.filter(event_type="JobAssigned").exists()

    started = start_job(job=job, actor=admin_user)
    assert started.status == JobStatus.IN_PROGRESS

    completed = complete_job(job=job, actor=admin_user, completion_notes="Done")
    assert completed.status == JobStatus.COMPLETED
    assert completed.completed_at is not None
    assert DomainEvent.objects.filter(event_type="JobCompleted").exists()

    # Cannot close before verification.
    with pytest.raises(ValidationError):
        close_job(job=job, actor=general_user)

    verified = verify_job(job=job, actor=general_user)
    assert verified.status == JobStatus.VERIFIED
    assert verified.verified_by_id == general_user.pk
    assert DomainEvent.objects.filter(event_type="JobVerified").exists()

    closed = close_job(job=job, actor=general_user)
    assert closed.status == JobStatus.CLOSED
    issue.refresh_from_db()
    assert issue.status == IssueStatus.CLOSED
    assert issue.closed_at is not None


@pytest.mark.django_db
def test_reopen_job_preserves_history(site, admin_user, general_user) -> None:
    cleaner = CleanerFactory(status=CleanerStatus.ACTIVE)
    job = create_job(
        job_title="Repaint",
        site=site,
        assigned_by=general_user,
        actor=general_user,
        assigned_to_cleaner=cleaner,
        due_date=date.today(),
    )
    start_job(job=job, actor=admin_user)
    complete_job(job=job, actor=admin_user, completion_notes="Painted")
    verify_job(job=job, actor=general_user)
    close_job(job=job, actor=general_user)

    with pytest.raises(ValidationError):
        reopen_job(job=job, actor=general_user, reason="")
    reopened = reopen_job(job=job, actor=general_user, reason="Peeling again")
    assert reopened.status == JobStatus.REOPENED
    assert reopened.verified_at is None
    assert "Painted" in reopened.completion_notes
    assert "Peeling again" in reopened.completion_notes

    with pytest.raises(ValidationError):
        start_job(job=job, actor=admin_user)  # reopened must be re-assigned first


@pytest.mark.django_db
def test_job_transition_validation(site, admin_user) -> None:
    job = create_job(job_title="Standalone", site=site, assigned_by=admin_user, actor=admin_user)
    assert job.status == JobStatus.OPEN
    with pytest.raises(ValidationError):
        start_job(job=job, actor=admin_user)  # not assigned
    with pytest.raises(ValidationError):
        complete_job(job=job, actor=admin_user)

    assigned = assign_job(job=job, actor=admin_user, assigned_to_user=admin_user)
    assert assigned.status == JobStatus.ASSIGNED
    with pytest.raises(ValidationError):
        assign_job(job=job, actor=admin_user, assigned_to_user=admin_user)  # already assigned


@pytest.mark.django_db
def test_job_requires_photo_when_configured(site, admin_user) -> None:
    job = create_job(
        job_title="Evidence job",
        site=site,
        assigned_by=admin_user,
        actor=admin_user,
        assigned_to_user=admin_user,
    )
    start_job(job=job, actor=admin_user)
    with override_config(JOB_COMPLETION_PHOTO_REQUIRED=True):
        with pytest.raises(ValidationError):
            complete_job(job=job, actor=admin_user)
        completed = complete_job(
            job=job,
            actor=admin_user,
            completion_photo=SimpleUploadedFile("proof.png", b"\x89PNG\r\n\x1a\n", content_type="image/png"),
        )
    assert completed.status == JobStatus.COMPLETED
    assert bool(completed.file) is True


@pytest.mark.django_db
def test_job_photo_upload_service(site, admin_user) -> None:
    job = create_job(job_title="With photo", site=site, assigned_by=admin_user, actor=admin_user)
    updated = upload_job_photo(
        job=job, uploaded_file=SimpleUploadedFile("after.png", b"x", content_type="image/png"), actor=admin_user
    )
    assert bool(updated.file) is True
    assert updated.content_type == "image/png"


# --------------------------------------------------------------------------- #
# Overdue
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
def test_overdue_jobs_and_issue(site, admin_user) -> None:
    overdue = create_job(
        job_title="Overdue",
        site=site,
        assigned_by=admin_user,
        actor=admin_user,
        due_date=date.today() - timedelta(days=1),
        assigned_to_user=admin_user,
    )
    on_time = create_job(
        job_title="On time",
        site=site,
        assigned_by=admin_user,
        actor=admin_user,
        due_date=date.today() + timedelta(days=1),
    )
    done = create_job(
        job_title="Done",
        site=site,
        assigned_by=admin_user,
        actor=admin_user,
        due_date=date.today() - timedelta(days=5),
        assigned_to_user=admin_user,
    )
    start_job(job=done, actor=admin_user)
    complete_job(job=done, actor=admin_user)
    done.refresh_from_db()
    assert done.overdue is False  # completed is not overdue
    assert overdue.overdue is True

    rows = overdue_jobs(admin_user)
    assert {r.pk for r in rows} == {overdue.pk}

    issue = _make_issue(site, admin_user, due_date=date.today() - timedelta(days=1))
    assert issue.overdue is True


# --------------------------------------------------------------------------- #
# Selectors & scoping
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
def test_selectors_and_scoping(site, admin_user, zone_user) -> None:
    issue = _make_issue(site, admin_user, priority="urgent", source=IssueSource.MANUAL)
    create_job(job_title="J1", site=site, assigned_by=admin_user, actor=admin_user, issue=issue)
    assert issue_list(admin_user, IssueFilter()).count() == 1
    assert issue_list(admin_user, IssueFilter(priority="urgent")).count() == 1
    assert issue_list(admin_user, IssueFilter(status="assigned")).count() == 1
    assert issue_list(admin_user, IssueFilter(source="manual")).count() == 1
    assert job_list(admin_user, JobFilter(issue_id=issue.pk)).count() == 1

    summary = issue_summary(admin_user, IssueFilter())
    assert summary["total_issues"] == 1
    assert summary["assigned"] == 1
    assert summary["urgent"] == 1
    assert summary["category_counts"]["other"] == 1

    js = job_summary(admin_user, JobFilter())
    assert js["total_jobs"] == 1
    assert js["open"] == 1

    ZoneSupervisorAssignmentFactory(zone=site.zone, user=zone_user)
    assert issue_list(zone_user, IssueFilter()).count() == 1
    outsider = UserFactory(role=RoleCode.ZONE_SUPERVISOR)
    assert issue_list(outsider, IssueFilter()).count() == 0
    assert job_list(outsider, JobFilter()).count() == 0
    assert overdue_jobs(outsider).count() == 0


# --------------------------------------------------------------------------- #
# Permissions & API
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
def test_api_issue_job_flow(site, admin_user, admin_client, general_user, site_supervisor_user) -> None:
    SiteSupervisorAssignmentFactory(site=site, user=site_supervisor_user)
    general_client = _authed(general_user)
    sup_client = _authed(site_supervisor_user)

    created = admin_client.post(
        "/api/site-management/v1/issues",
        data={"title": "Leaky roof", "site_id": site.pk, "priority": "high", "issue_category": "maintenance"},
        content_type="application/json",
    )
    assert created.status_code == 200
    issue_id = created.json()["id"]

    reviewed = admin_client.post(
        f"/api/site-management/v1/issues/{issue_id}/review",
        data={"notes": "Confirmed leak"},
        content_type="application/json",
    )
    assert reviewed.json()["status"] == "under_review"

    escalated = general_client.post(
        f"/api/site-management/v1/issues/{issue_id}/escalate",
        data={"reason": "Roof damage spreading"},
        content_type="application/json",
    )
    assert escalated.status_code == 200
    assert escalated.json()["is_escalated"] is True

    assigned = general_client.post(
        f"/api/site-management/v1/issues/{issue_id}/jobs",
        data={"assigned_to_user_id": site_supervisor_user.pk},
        content_type="application/json",
    )
    assert assigned.status_code == 200
    assert assigned.json()["status"] == "assigned"
    job_id = assigned.json()["id"]

    started = sup_client.post(f"/api/site-management/v1/jobs/{job_id}/start")
    assert started.status_code == 200
    assert started.json()["status"] == "in_progress"

    completed = sup_client.post(
        f"/api/site-management/v1/jobs/{job_id}/complete",
        data={"completion_notes": "Patched"},
        content_type="application/json",
    )
    assert completed.status_code == 200
    assert completed.json()["status"] == "completed"

    verified = general_client.post(f"/api/site-management/v1/jobs/{job_id}/verify")
    assert verified.json()["status"] == "verified"

    closed = admin_client.post(f"/api/site-management/v1/jobs/{job_id}/close")
    assert closed.json()["status"] == "closed"

    issue_detail = admin_client.get(f"/api/site-management/v1/issues/{issue_id}")
    assert issue_detail.json()["status"] == "closed"

    overdue = admin_client.get("/api/site-management/v1/jobs/overdue")
    assert overdue.status_code == 200
    summary = admin_client.get("/api/site-management/v1/jobs/summary")
    assert summary.json()["closed"] == 1
    issue_summary_resp = admin_client.get("/api/site-management/v1/issues/summary")
    assert issue_summary_resp.json()["closed"] == 1


@pytest.mark.django_db
def test_api_permissions(site, admin_user, viewer_user, site_supervisor_user, general_user, zone_user) -> None:
    issue = _make_issue(site, admin_user)

    # Viewer read-only.
    viewer = _authed(viewer_user)
    assert viewer.get("/api/site-management/v1/issues").status_code == 200
    denied = viewer.post(
        "/api/site-management/v1/issues",
        data={"title": "X", "site_id": site.pk},
        content_type="application/json",
    )
    assert denied.status_code in (401, 403)

    # Site supervisor (not assigned) cannot manage issues on the site.
    outsider = UserFactory(role=RoleCode.SITE_SUPERVISOR)
    assert _authed(outsider).post(
        "/api/site-management/v1/issues",
        data={"title": "X", "site_id": site.pk},
        content_type="application/json",
    ).status_code in (401, 403)

    # Escalation restricted to senior management.
    assert _authed(zone_user).post(
        f"/api/site-management/v1/issues/{issue.pk}/escalate",
        data={"reason": "x"},
        content_type="application/json",
    ).status_code in (401, 403)

    # Site supervisor assigned to the site can raise issues but not escalate/review.
    SiteSupervisorAssignmentFactory(site=site, user=site_supervisor_user)
    sup = _authed(site_supervisor_user)
    assert (
        sup.post(
            "/api/site-management/v1/issues",
            data={"title": "From sup", "site_id": site.pk},
            content_type="application/json",
        ).status_code
        == 200
    )
    assert sup.post(
        f"/api/site-management/v1/issues/{issue.pk}/escalate",
        data={"reason": "x"},
        content_type="application/json",
    ).status_code in (401, 403)

    # Zone supervisor can review issues in scope.
    ZoneSupervisorAssignmentFactory(zone=site.zone, user=zone_user)
    assert (
        _authed(zone_user)
        .post(
            f"/api/site-management/v1/issues/{issue.pk}/review",
            data={"notes": "ok"},
            content_type="application/json",
        )
        .status_code
        == 200
    )

    # Assign permission: site supervisor has assign_job (RBAC) + site scope.
    job = create_job(job_title="Assign me", site=site, assigned_by=admin_user, actor=admin_user)
    assigned = sup.post(
        f"/api/site-management/v1/jobs/{job.pk}/assign",
        data={"assigned_to_user_id": site_supervisor_user.pk},
        content_type="application/json",
    )
    assert assigned.status_code == 200


@pytest.mark.django_db
def test_api_validation(site, admin_user, admin_client) -> None:
    # Missing title -> 422.
    bad = admin_client.post(
        "/api/site-management/v1/issues",
        data={"site_id": site.pk},
        content_type="application/json",
    )
    assert bad.status_code == 422

    job = create_job(job_title="V", site=site, assigned_by=admin_user, actor=admin_user)
    # Cannot start an unassigned job -> service error.
    resp = admin_client.post(f"/api/site-management/v1/jobs/{job.pk}/start")
    assert resp.status_code == 422


@pytest.mark.django_db
def test_admin_views_and_actions(site, admin_user) -> None:
    from django.test import Client

    admin = UserFactory(role=RoleCode.SYSTEM_ADMIN, is_staff=True, is_superuser=True)
    client = Client()
    client.force_login(admin)
    issue = _make_issue(site, admin_user)
    cleaner = CleanerFactory(status=CleanerStatus.ACTIVE)
    job = create_job(
        job_title="J",
        site=site,
        assigned_by=admin_user,
        actor=admin_user,
        assigned_to_cleaner=cleaner,
        issue=issue,
    )
    start_job(job=job, actor=admin_user)
    complete_job(job=job, actor=admin_user)

    assert client.get("/admin/site_management/issue/").status_code == 200
    assert client.get("/admin/site_management/job/").status_code == 200

    # Verify action.
    assert (
        client.post(
            "/admin/site_management/issue/",
            data={"action": "verify_issues", "_selected_action": [issue.pk]},
        ).status_code
        == 302
    )
    job.refresh_from_db()
    assert job.status == JobStatus.VERIFIED

    # Escalate action.
    assert (
        client.post(
            "/admin/site_management/issue/",
            data={"action": "escalate_issues", "_selected_action": [issue.pk]},
        ).status_code
        == 302
    )
    issue.refresh_from_db()
    assert issue.escalation_level == 1

    # Reopen jobs action.
    close_job(job=job, actor=admin_user)
    assert (
        client.post(
            "/admin/site_management/issue/",
            data={"action": "reopen_jobs", "_selected_action": [issue.pk]},
        ).status_code
        == 302
    )
    job.refresh_from_db()
    assert job.status == JobStatus.REOPENED


@pytest.mark.django_db
def test_additional_branches(site, admin_user, zone_user) -> None:
    area = SiteAreaFactory(site=site)
    cleaner = CleanerFactory(status=CleanerStatus.ACTIVE)
    issue = _make_issue(site, admin_user, area=area, cleaner=cleaner, due_date=date.today())
    assert issue.area_id == area.pk
    assert issue.cleaner_id == cleaner.pk

    # update_issue with area/cleaner/due_date branches.
    updated = update_issue(
        issue=issue, actor=admin_user, area=area, cleaner=cleaner, due_date=date.today() + timedelta(days=1)
    )
    assert updated.due_date == date.today() + timedelta(days=1)

    # review_issue with notes.
    reviewed = review_issue(issue=issue, actor=zone_user, notes="Assessed")
    assert "Assessed" in reviewed.description

    # Selector filter branches.
    escalated = escalate_issue(issue=issue, actor=admin_user, reason="escalate to test filter")
    assert escalated.is_escalated
    assert (
        issue_list(
            admin_user, IssueFilter(site_id=site.pk, category="other", escalated=True, assigned_to_id=admin_user.pk)
        ).count()
        == 0
    )
    assert issue_list(admin_user, IssueFilter(category="other")).count() == 1
    assert issue_list(admin_user, IssueFilter(escalated=False)).count() == 0

    # Job selector filter branches.
    job = create_job(
        job_title="Filtered",
        site=site,
        assigned_by=admin_user,
        actor=admin_user,
        assigned_to_user=admin_user,
        priority="high",
        issue=issue,
    )
    assert (
        job_list(
            admin_user,
            JobFilter(site_id=site.pk, status="assigned", priority="high", assigned_to_user_id=admin_user.pk),
        ).count()
        == 1
    )
    assert job_list(admin_user, JobFilter(issue_id=issue.pk)).count() == 1

    # start_job triggers issue assigned sync.
    started = start_job(job=job, actor=admin_user)
    assert started.status == JobStatus.IN_PROGRESS
    issue.refresh_from_db()
    assert issue.status == IssueStatus.ASSIGNED


@pytest.mark.django_db
def test_update_job_and_closed_photo_guard(site, admin_user, general_user) -> None:
    job = create_job(
        job_title="Old",
        site=site,
        assigned_by=admin_user,
        actor=admin_user,
        assigned_to_user=admin_user,
        due_date=date.today(),
    )
    updated = update_job(
        job=job,
        actor=admin_user,
        job_title="New",
        description="desc",
        due_date=date.today() + timedelta(days=2),
        priority="urgent",
    )
    assert updated.job_title == "New"
    assert updated.description == "desc"
    assert updated.priority == "urgent"

    start_job(job=job, actor=admin_user)
    complete_job(job=job, actor=admin_user)
    verify_job(job=job, actor=general_user)
    close_job(job=job, actor=general_user)
    job.refresh_from_db()
    with pytest.raises(ValidationError):
        update_job(job=job, actor=admin_user, job_title="X")
    with pytest.raises(ValidationError):
        upload_job_photo(
            job=job,
            uploaded_file=SimpleUploadedFile("x.png", b"x", content_type="image/png"),
            actor=admin_user,
        )


@pytest.mark.django_db
def test_api_remaining_endpoints(site, admin_user, admin_client, general_user) -> None:
    from apps.site_management.inspection_services import create_template, start_inspection

    template = create_template(
        template_name="T",
        actor=admin_user,
        site=site,
        items=[{"item_label": "C", "item_type": "pass_fail", "sequence": 1}],
    )
    area = SiteAreaFactory(site=site)
    inspection = start_inspection(site=site, area=area, template=template, inspected_by=admin_user, actor=admin_user)

    # Create an issue from an inspection source.
    created = admin_client.post(
        "/api/site-management/v1/issues",
        data={
            "title": "Inspection flag",
            "site_id": site.pk,
            "source": "inspection",
            "inspection_id": inspection.pk,
            "issue_category": "cleaning_quality",
        },
        content_type="application/json",
    )
    assert created.status_code == 200
    assert created.json()["inspection_id"] == inspection.pk
    issue_id = created.json()["id"]

    # PUT issue update.
    updated = admin_client.put(
        f"/api/site-management/v1/issues/{issue_id}",
        data={"title": "Renamed", "priority": "high"},
        content_type="application/json",
    )
    assert updated.status_code == 200
    assert updated.json()["title"] == "Renamed"

    # Create a standalone job and update it.
    job_resp = admin_client.post(
        "/api/site-management/v1/jobs",
        data={"job_title": "Standalone", "site_id": site.pk},
        content_type="application/json",
    )
    assert job_resp.status_code == 200
    job_id = job_resp.json()["id"]
    job_update = admin_client.put(
        f"/api/site-management/v1/jobs/{job_id}",
        data={"job_title": "Standalone v2", "priority": "urgent"},
        content_type="application/json",
    )
    assert job_update.json()["job_title"] == "Standalone v2"

    # Photo upload + signed URL.
    photo = admin_client.post(
        f"/api/site-management/v1/jobs/{job_id}/photo",
        {"file": SimpleUploadedFile("proof.png", b"\x89PNG\r\n\x1a\n", content_type="image/png")},
    )
    assert photo.status_code == 200
    assert photo.json()["has_completion_photo"] is True
    url_resp = admin_client.get(f"/api/site-management/v1/jobs/{job_id}/photo/download-url")
    assert url_resp.status_code == 200
    assert "files/signed/" in url_resp.json()["download_url"]

    # Full lifecycle to close, then reopen.
    admin_client.post(
        f"/api/site-management/v1/jobs/{job_id}/assign",
        data={"assigned_to_user_id": admin_user.pk},
        content_type="application/json",
    )
    admin_client.post(f"/api/site-management/v1/jobs/{job_id}/start")
    admin_client.post(
        f"/api/site-management/v1/jobs/{job_id}/complete",
        data={"completion_notes": "x"},
        content_type="application/json",
    )
    admin_client.post(f"/api/site-management/v1/jobs/{job_id}/verify")
    closed = admin_client.post(f"/api/site-management/v1/jobs/{job_id}/close")
    assert closed.json()["status"] == "closed"
    reopened = admin_client.post(
        f"/api/site-management/v1/jobs/{job_id}/reopen", data={"reason": "recheck"}, content_type="application/json"
    )
    assert reopened.json()["status"] == "reopened"

    # Job list filters.
    filtered = admin_client.get("/api/site-management/v1/jobs", {"site_id": site.pk, "status": "reopened"})
    assert filtered.json()["count"] == 1
