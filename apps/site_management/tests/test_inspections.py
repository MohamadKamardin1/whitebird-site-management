"""Tests for the inspection engine: templates, results, scoring, workflow."""

from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError
from django.test import Client

from apps.accounts.factories import UserFactory
from apps.accounts.models import RoleCode, User
from apps.accounts.services import issue_api_token
from apps.core.models import AuditLog, DomainEvent
from apps.site_management.factories import (
    SiteAreaFactory,
    SiteFactory,
    SiteSupervisorAssignmentFactory,
    ZoneSupervisorAssignmentFactory,
)
from apps.site_management.inspection_selectors import (
    InspectionFilter,
    TemplateFilter,
    area_latest_status,
    get_inspection_or_none,
    inspection_list,
    inspection_summary,
    template_list,
)
from apps.site_management.inspection_services import (
    add_inspection_result,
    calculate_inspection_score,
    create_template,
    deactivate_template,
    return_inspection,
    review_inspection,
    save_inspection_draft,
    start_inspection,
    submit_inspection,
    update_inspection_result,
    update_template,
    upload_result_photo,
)
from apps.site_management.models import (
    Inspection,
    InspectionOverallStatus,
    InspectionTemplate,
    InspectionWorkflowStatus,
)


@pytest.fixture(autouse=True)
def rbac_seeded(db: None) -> None:
    from django.core.management import call_command

    call_command("seed_rbac")


def _authed(user: User) -> Client:
    return Client(HTTP_AUTHORIZATION=f"Bearer {issue_api_token(user=user, name='test').key}")


def _template(actor: Any, site=None, with_items: bool = True) -> InspectionTemplate:
    items = None
    if with_items:
        items = [
            {"item_label": "Cleanliness", "item_type": "pass_fail", "required": True, "sequence": 1},
            {"item_label": "Lighting", "item_type": "yes_no", "required": True, "sequence": 2},
            {"item_label": "Rating", "item_type": "score", "required": False, "sequence": 3},
            {"item_label": "Comment", "item_type": "text", "required": False, "sequence": 4},
        ]
    return create_template(template_name="Housekeeping", actor=actor, site=site, items=items)


def _started_inspection(site: Any, actor: Any, area=None, template=None) -> Inspection:
    area = area or SiteAreaFactory(site=site)
    template = template or _template(actor, site=site)
    return start_inspection(site=site, area=area, template=template, inspected_by=actor, actor=actor)


# --------------------------------------------------------------------------- #
# Templates
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
def test_template_crud_and_items(site, admin_user) -> None:
    template = _template(admin_user, site=site)
    assert template.items.count() == 4
    assert template.item_count == 4
    assert AuditLog.objects.filter(model_name="site_management.inspectiontemplate").exists()

    updated = update_template(template=template, actor=admin_user, template_name="Renamed", items=[])
    assert updated.template_name == "Renamed"
    assert template.items.count() == 0

    with pytest.raises(ValidationError):
        create_template(template_name="Bad", actor=admin_user, area=SiteAreaFactory(site=site))

    deactivated = deactivate_template(template=template, actor=admin_user)
    assert deactivated.is_active is False


@pytest.mark.django_db
def test_template_unique_sequence(site, admin_user) -> None:
    template = _template(admin_user, site=site)
    from apps.site_management.models import InspectionTemplateItem

    with pytest.raises(IntegrityError):
        InspectionTemplateItem.objects.create(template=template, item_label="Dup", item_type="text", sequence=1)


@pytest.mark.django_db
def test_global_templates_visible_and_site_scoped(admin_user, zone_user) -> None:
    _template(admin_user)  # global
    site = SiteFactory()
    ZoneSupervisorAssignmentFactory(zone=site.zone, user=zone_user)
    _template(admin_user, site=site)
    assert template_list(admin_user, TemplateFilter()).count() == 2
    assert template_list(zone_user, TemplateFilter()).count() == 2  # global + own site
    outsider = UserFactory(role=RoleCode.ZONE_SUPERVISOR)
    assert template_list(outsider, TemplateFilter()).count() == 1  # global only
    assert template_list(admin_user, TemplateFilter(site_id=site.pk)).count() == 2
    assert template_list(admin_user, TemplateFilter(is_active=True)).count() == 2


# --------------------------------------------------------------------------- #
# Results & validation
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
def test_result_type_validation(site, admin_user) -> None:
    inspection = _started_inspection(site, admin_user)
    items = {i.item_label: i for i in inspection.template.items.all()}

    with pytest.raises(ValidationError):
        add_inspection_result(
            inspection=inspection, template_item=items["Cleanliness"], actor=admin_user
        )  # pass_fail needs passed
    with pytest.raises(ValidationError):
        add_inspection_result(
            inspection=inspection, template_item=items["Lighting"], actor=admin_user, value_boolean=None
        )
    with pytest.raises(ValidationError):
        add_inspection_result(
            inspection=inspection, template_item=items["Rating"], actor=admin_user, value_number=Decimal("150")
        )
    with pytest.raises(ValidationError):
        add_inspection_result(inspection=inspection, template_item=items["Comment"], actor=admin_user)

    ok = add_inspection_result(
        inspection=inspection, template_item=items["Rating"], actor=admin_user, value_number=Decimal("80")
    )
    assert ok.passed is True  # score >= 50


@pytest.mark.django_db
def test_result_immutable_after_submit(site, admin_user) -> None:
    inspection = _started_inspection(site, admin_user)
    items = {i.item_label: i for i in inspection.template.items.all()}
    result = add_inspection_result(
        inspection=inspection, template_item=items["Cleanliness"], actor=admin_user, passed=True
    )
    add_inspection_result(inspection=inspection, template_item=items["Lighting"], actor=admin_user, value_boolean=True)
    submit_inspection(inspection=inspection, actor=admin_user)
    with pytest.raises(ValidationError):
        update_inspection_result(result=result, actor=admin_user, passed=False)
    with pytest.raises(ValidationError):
        add_inspection_result(
            inspection=inspection, template_item=items["Rating"], actor=admin_user, value_number=Decimal("50")
        )


# --------------------------------------------------------------------------- #
# Scoring
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
def test_score_calculation(site, admin_user) -> None:
    inspection = _started_inspection(site, admin_user)
    items = {i.item_label: i for i in inspection.template.items.all()}
    add_inspection_result(inspection=inspection, template_item=items["Cleanliness"], actor=admin_user, passed=True)
    add_inspection_result(inspection=inspection, template_item=items["Lighting"], actor=admin_user, value_boolean=True)
    add_inspection_result(
        inspection=inspection, template_item=items["Rating"], actor=admin_user, value_number=Decimal("80")
    )
    score, overall = calculate_inspection_score(inspection)
    assert score == Decimal("80.00")
    assert overall == InspectionOverallStatus.PASSED

    # A failed answer forces FAILED regardless of score.
    add_inspection_result(inspection=inspection, template_item=items["Comment"], actor=admin_user, value_text="dust")
    result = update_inspection_result(
        result=inspection.results.get(template_item=items["Cleanliness"]), actor=admin_user, passed=False
    )
    assert result.passed is False
    score, overall = calculate_inspection_score(inspection)
    assert overall == InspectionOverallStatus.FAILED


@pytest.mark.django_db
def test_score_threshold_needs_attention(site, admin_user) -> None:
    template = create_template(
        template_name="Scored",
        actor=admin_user,
        site=site,
        items=[{"item_label": "Rating", "item_type": "score", "required": True, "sequence": 1}],
    )
    area = SiteAreaFactory(site=site)
    inspection = start_inspection(site=site, area=area, template=template, inspected_by=admin_user, actor=admin_user)
    item = template.items.first()
    add_inspection_result(inspection=inspection, template_item=item, actor=admin_user, value_number=Decimal("60"))
    score, overall = calculate_inspection_score(inspection)
    assert score == Decimal("60.00")
    assert overall == InspectionOverallStatus.NEEDS_ATTENTION


# --------------------------------------------------------------------------- #
# Workflow
# --------------------------------------------------------------------------- #


@pytest.mark.django_db(transaction=True)
def test_submit_requires_required_items(site, admin_user) -> None:
    inspection = _started_inspection(site, admin_user)
    items = {i.item_label: i for i in inspection.template.items.all()}
    add_inspection_result(inspection=inspection, template_item=items["Cleanliness"], actor=admin_user, passed=False)
    with pytest.raises(ValidationError):
        submit_inspection(inspection=inspection, actor=admin_user)  # Lighting required, missing

    add_inspection_result(inspection=inspection, template_item=items["Lighting"], actor=admin_user, value_boolean=True)
    submitted = submit_inspection(inspection=inspection, actor=admin_user)
    assert submitted.status == InspectionWorkflowStatus.SUBMITTED
    assert submitted.submitted_at is not None
    assert DomainEvent.objects.filter(event_type="InspectionSubmitted", aggregate_id=str(inspection.pk)).exists()

    # Failed result triggered the issue hook.
    assert DomainEvent.objects.filter(event_type="InspectionIssueDetected").exists()


@pytest.mark.django_db
def test_return_and_resubmit(site, admin_user, zone_user) -> None:
    ZoneSupervisorAssignmentFactory(zone=site.zone, user=zone_user)
    inspection = _started_inspection(site, admin_user)
    items = {i.item_label: i for i in inspection.template.items.all()}
    add_inspection_result(inspection=inspection, template_item=items["Cleanliness"], actor=admin_user, passed=True)
    add_inspection_result(inspection=inspection, template_item=items["Lighting"], actor=admin_user, value_boolean=True)
    submit_inspection(inspection=inspection, actor=admin_user)
    with pytest.raises(ValidationError):
        return_inspection(inspection=inspection, actor=zone_user, reason="")
    returned = return_inspection(inspection=inspection, actor=zone_user, reason="Photo missing")
    assert returned.status == InspectionWorkflowStatus.RETURNED

    # Editable again; resubmit works.
    items = {i.item_label: i for i in inspection.template.items.all()}
    add_inspection_result(inspection=inspection, template_item=items["Comment"], actor=admin_user, value_text="ok")
    resubmitted = submit_inspection(inspection=inspection, actor=admin_user)
    assert resubmitted.status == InspectionWorkflowStatus.SUBMITTED


@pytest.mark.django_db
def test_review_workflow(site, admin_user, zone_user) -> None:
    ZoneSupervisorAssignmentFactory(zone=site.zone, user=zone_user)
    inspection = _started_inspection(site, admin_user)
    items = {i.item_label: i for i in inspection.template.items.all()}
    add_inspection_result(inspection=inspection, template_item=items["Cleanliness"], actor=admin_user, passed=True)
    add_inspection_result(inspection=inspection, template_item=items["Lighting"], actor=admin_user, value_boolean=True)
    submit_inspection(inspection=inspection, actor=admin_user)
    draft = _started_inspection(site, admin_user)
    with pytest.raises(ValidationError):
        review_inspection(inspection=draft, actor=zone_user)  # drafts cannot be reviewed
    reviewed = review_inspection(inspection=inspection, actor=zone_user)
    assert reviewed.status == InspectionWorkflowStatus.REVIEWED
    assert reviewed.overall_status == InspectionOverallStatus.PASSED


# --------------------------------------------------------------------------- #
# Photos
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
def test_photo_upload_and_private_access(site, admin_user, admin_client) -> None:
    template = create_template(
        template_name="Photo check",
        actor=admin_user,
        site=site,
        items=[{"item_label": "Condition", "item_type": "photo", "required": True, "sequence": 1}],
    )
    area = SiteAreaFactory(site=site)
    inspection = start_inspection(site=site, area=area, template=template, inspected_by=admin_user, actor=admin_user)
    item = template.items.first()
    result = add_inspection_result(inspection=inspection, template_item=item, actor=admin_user)
    with pytest.raises(ValidationError):
        add_inspection_result(inspection=inspection, template_item=item, actor=admin_user, value_boolean=True)

    photo = admin_client.post(
        f"/api/site-management/v1/inspections/{inspection.pk}/results/{result.pk}/photo",
        {"file": SimpleUploadedFile("room.png", b"\x89PNG\r\n\x1a\nfakepng", content_type="image/png")},
    )
    assert photo.status_code == 200
    assert photo.json()["has_photo"] is True

    url_resp = admin_client.get(f"/api/site-management/v1/inspections/{inspection.pk}/results/{result.pk}/download-url")
    assert url_resp.status_code == 200
    url = url_resp.json()["download_url"]
    assert "files/signed/" in url
    download = admin_client.get(url)
    assert download.status_code == 200

    # Submitted inspection refuses further photo changes.
    submit_inspection(inspection=inspection, actor=admin_user)
    denied = admin_client.post(
        f"/api/site-management/v1/inspections/{inspection.pk}/results/{result.pk}/photo",
        {"file": SimpleUploadedFile("x.png", b"other", content_type="image/png")},
    )
    assert denied.status_code in (400, 422)


# --------------------------------------------------------------------------- #
# Selectors
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
def test_selectors_and_summary(site, admin_user, zone_user) -> None:
    area = SiteAreaFactory(site=site)
    inspection = _started_inspection(site, admin_user, area=area)
    items = {i.item_label: i for i in inspection.template.items.all()}
    add_inspection_result(inspection=inspection, template_item=items["Cleanliness"], actor=admin_user, passed=True)
    add_inspection_result(inspection=inspection, template_item=items["Lighting"], actor=admin_user, value_boolean=True)
    submit_inspection(inspection=inspection, actor=admin_user)

    assert inspection_list(admin_user, InspectionFilter(site_id=site.pk)).count() == 1
    assert inspection_list(admin_user, InspectionFilter(status="submitted")).count() == 1
    assert inspection_list(admin_user, InspectionFilter(date_from=date.today(), date_to=date.today())).count() == 1

    detail = get_inspection_or_none(inspection.pk)
    assert detail is not None and detail.results.count() == 2

    summary = inspection_summary(admin_user)
    assert summary["total_inspections"] == 1
    assert summary["submitted"] == 1
    assert summary["passed"] == 1

    latest = area_latest_status(admin_user, area.pk)
    assert latest is not None
    assert latest["overall_status"] == "passed"

    ZoneSupervisorAssignmentFactory(zone=site.zone, user=zone_user)
    assert inspection_list(zone_user, InspectionFilter()).count() == 1
    outsider = UserFactory(role=RoleCode.ZONE_SUPERVISOR)
    assert inspection_list(outsider, InspectionFilter()).count() == 0


# --------------------------------------------------------------------------- #
# Permissions & API
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
def test_api_inspection_flow(site, admin_user, admin_client, site_supervisor_user) -> None:
    SiteSupervisorAssignmentFactory(site=site, user=site_supervisor_user)
    sup_client = _authed(site_supervisor_user)
    area = SiteAreaFactory(site=site)

    created = sup_client.post(
        "/api/site-management/v1/inspection-templates",
        data={
            "template_name": "Room Audit",
            "site_id": site.pk,
            "frequency": "daily",
            "items": [
                {"item_label": "Clean", "item_type": "pass_fail", "sequence": 1},
                {"item_label": "Note", "item_type": "text", "sequence": 2},
            ],
        },
        content_type="application/json",
    )
    assert created.status_code == 200
    template_id = created.json()["id"]

    listed = admin_client.get("/api/site-management/v1/inspection-templates")
    assert listed.json()["count"] == 1

    started = sup_client.post(
        "/api/site-management/v1/inspections",
        data={"site_id": site.pk, "area_id": area.pk, "template_id": template_id},
        content_type="application/json",
    )
    assert started.status_code == 200
    inspection_id = started.json()["id"]

    template_detail = admin_client.get(f"/api/site-management/v1/inspection-templates/{template_id}")
    raw_item = template_detail.json()["items"][0]
    result = sup_client.post(
        f"/api/site-management/v1/inspections/{inspection_id}/results",
        data={"template_item_id": raw_item["id"], "passed": True},
        content_type="application/json",
    )
    assert result.status_code == 200

    # Missing required item blocks submission.
    blocked = sup_client.post(f"/api/site-management/v1/inspections/{inspection_id}/submit")
    assert blocked.status_code == 422

    # Fill the text item, then submit.
    text_item = template_detail.json()["items"][1]
    sup_client.post(
        f"/api/site-management/v1/inspections/{inspection_id}/results",
        data={"template_item_id": text_item["id"], "value_text": "all good"},
        content_type="application/json",
    )
    submitted = sup_client.post(f"/api/site-management/v1/inspections/{inspection_id}/submit")
    assert submitted.status_code == 200
    assert submitted.json()["status"] == "submitted"

    reviewed = admin_client.post(f"/api/site-management/v1/inspections/{inspection_id}/review")
    assert reviewed.status_code == 200
    assert reviewed.json()["status"] == "reviewed"

    summary = admin_client.get("/api/site-management/v1/inspections/summary")
    assert summary.json()["reviewed"] == 1

    returned = admin_client.post(
        f"/api/site-management/v1/inspections/{inspection_id}/return",
        data={"reason": "Recheck"},
        content_type="application/json",
    )
    assert returned.json()["status"] == "returned"


@pytest.mark.django_db
def test_api_permissions(site, admin_user, viewer_user, site_supervisor_user, zone_user) -> None:
    area = SiteAreaFactory(site=site)
    inspection = _started_inspection(site, admin_user, area=area)

    # Viewer read-only.
    viewer = _authed(viewer_user)
    assert viewer.get("/api/site-management/v1/inspections").status_code == 200
    denied = viewer.post(
        "/api/site-management/v1/inspections",
        data={"site_id": site.pk, "area_id": area.pk, "template_id": inspection.template_id},
        content_type="application/json",
    )
    assert denied.status_code in (401, 403)

    # Unassigned site supervisor cannot create inspections for the site.
    outsider = UserFactory(role=RoleCode.SITE_SUPERVISOR)
    assert _authed(outsider).post(
        "/api/site-management/v1/inspections",
        data={"site_id": site.pk, "area_id": area.pk, "template_id": inspection.template_id},
        content_type="application/json",
    ).status_code in (401, 403)

    # Site supervisor assigned to the site can manage (start), but cannot review.
    SiteSupervisorAssignmentFactory(site=site, user=site_supervisor_user)
    sup = _authed(site_supervisor_user)
    assert (
        sup.post(
            "/api/site-management/v1/inspections",
            data={"site_id": site.pk, "area_id": area.pk, "template_id": inspection.template_id},
            content_type="application/json",
        ).status_code
        == 200
    )
    assert sup.post(
        f"/api/site-management/v1/inspections/{inspection.pk}/review",
        data={},
        content_type="application/json",
    ).status_code in (401, 403)

    # Zone supervisor can review.
    ZoneSupervisorAssignmentFactory(zone=site.zone, user=zone_user)
    assert (
        _authed(zone_user)
        .post(
            f"/api/site-management/v1/inspections/{inspection.pk}/review",
            data={},
            content_type="application/json",
        )
        .status_code
        == 422
    )  # still draft -> review rejected by service

    # Out-of-scope read denied.
    outsider_zone = UserFactory(role=RoleCode.ZONE_SUPERVISOR)
    assert _authed(outsider_zone).get(f"/api/site-management/v1/inspections/{inspection.pk}").status_code in (401, 403)


@pytest.mark.django_db
def test_admin_views_and_actions(site, admin_user) -> None:
    from django.test import Client

    admin = UserFactory(role=RoleCode.SYSTEM_ADMIN, is_staff=True, is_superuser=True)
    client = Client()
    client.force_login(admin)
    assert client.get("/admin/site_management/inspectiontemplate/").status_code == 200
    assert client.get("/admin/site_management/inspection/").status_code == 200

    template = _template(admin_user, site=site)
    area = SiteAreaFactory(site=site)
    inspection = start_inspection(site=site, area=area, template=template, inspected_by=admin_user, actor=admin_user)
    items = {i.item_label: i for i in template.items.all()}
    add_inspection_result(inspection=inspection, template_item=items["Cleanliness"], actor=admin_user, passed=True)
    add_inspection_result(inspection=inspection, template_item=items["Lighting"], actor=admin_user, value_boolean=True)

    assert (
        client.post(
            "/admin/site_management/inspection/",
            data={"action": "submit_inspections", "_selected_action": [inspection.pk]},
        ).status_code
        == 302
    )
    inspection.refresh_from_db()
    assert inspection.status == InspectionWorkflowStatus.SUBMITTED

    from apps.site_management.admin import InspectionAdmin

    inspection_admin = InspectionAdmin(model=Inspection, admin_site=None)
    # Submitted inspections cannot be deleted.
    assert inspection_admin.has_delete_permission(None, inspection) is False

    assert (
        client.post(
            "/admin/site_management/inspection/",
            data={"action": "review_inspections", "_selected_action": [inspection.pk]},
        ).status_code
        == 302
    )
    inspection.refresh_from_db()
    assert inspection.status == InspectionWorkflowStatus.REVIEWED

    assert (
        client.post(
            "/admin/site_management/inspection/",
            data={"action": "return_inspections", "_selected_action": [inspection.pk]},
        ).status_code
        == 302
    )
    inspection.refresh_from_db()
    assert inspection.status == InspectionWorkflowStatus.RETURNED
    # Returned inspections are editable again, so deletion is permitted.
    assert inspection_admin.has_delete_permission(None, inspection) is True


@pytest.mark.django_db
def test_additional_service_branches(site, admin_user, zone_user) -> None:
    ZoneSupervisorAssignmentFactory(zone=site.zone, user=zone_user)
    # start_inspection rejects a site-scoped template from another site.
    other_site = SiteFactory()
    other_template = _template(admin_user, site=other_site)
    area = SiteAreaFactory(site=site)
    with pytest.raises(ValidationError):
        start_inspection(site=site, area=area, template=other_template, inspected_by=admin_user, actor=admin_user)

    # upload_result_photo on a non-photo item is rejected.
    inspection = _started_inspection(site, admin_user, area=area)
    items = {i.item_label: i for i in inspection.template.items.all()}
    result = add_inspection_result(
        inspection=inspection, template_item=items["Cleanliness"], actor=admin_user, passed=True
    )
    from django.core.files.uploadedfile import SimpleUploadedFile

    with pytest.raises(ValidationError):
        upload_result_photo(result=result, uploaded_file=SimpleUploadedFile("x.png", b"x"), actor=admin_user)

    # update_inspection_result field branches.
    rating = add_inspection_result(
        inspection=inspection, template_item=items["Rating"], actor=admin_user, value_number=Decimal("50")
    )
    updated = update_inspection_result(
        result=rating,
        actor=admin_user,
        value_number=Decimal("60"),
        value_boolean=False,
        notes="recheck",
    )
    assert updated.value_number == Decimal("60")
    assert updated.notes == "recheck"

    # save_inspection_draft refreshes score preview and keeps draft.
    saved = save_inspection_draft(inspection=inspection, actor=admin_user, notes="first pass")
    assert saved.notes == "first pass"
    assert saved.status == InspectionWorkflowStatus.DRAFT

    # submit when not DRAFT/RETURNED is rejected.
    other = _started_inspection(site, admin_user, area=area)
    other.status = InspectionWorkflowStatus.SUBMITTED
    other.save(update_fields=["status"])
    with pytest.raises(ValidationError):
        submit_inspection(inspection=other, actor=admin_user)

    # return when not SUBMITTED/REVIEWED is rejected.
    with pytest.raises(ValidationError):
        return_inspection(inspection=inspection, actor=zone_user, reason="x")


@pytest.mark.django_db
def test_selector_remaining_branches(site, admin_user, zone_user) -> None:
    area = SiteAreaFactory(site=site)
    inspection = _started_inspection(site, admin_user, area=area)
    items = {i.item_label: i for i in inspection.template.items.all()}
    add_inspection_result(inspection=inspection, template_item=items["Cleanliness"], actor=admin_user, passed=True)
    add_inspection_result(inspection=inspection, template_item=items["Lighting"], actor=admin_user, value_boolean=True)
    add_inspection_result(
        inspection=inspection, template_item=items["Rating"], actor=admin_user, value_number=Decimal("80")
    )
    submit_inspection(inspection=inspection, actor=admin_user)

    # Template filter branches.
    assert template_list(admin_user, TemplateFilter(site_id=site.pk)).count() == 1
    assert template_list(admin_user, TemplateFilter(is_active=False)).count() == 0
    assert template_list(admin_user, TemplateFilter(frequency="manual")).count() == 1
    assert template_list(admin_user, TemplateFilter(search="Housekeeping")).count() == 1

    # Inspection filter branches.
    assert inspection_list(admin_user, InspectionFilter(overall_status="passed")).count() == 1
    assert inspection_list(admin_user, InspectionFilter(area_id=area.pk)).count() == 1
    assert inspection_list(admin_user, InspectionFilter(template_id=inspection.template_id)).count() == 1
    assert inspection_list(admin_user, InspectionFilter(date_to=date.today())).count() == 1

    # area_latest_status excludes drafts; empty scope returns None.
    assert area_latest_status(admin_user, area.pk) is not None
    assert area_latest_status(admin_user, 999999) is None
    outsider = UserFactory(role=RoleCode.ZONE_SUPERVISOR)
    assert area_latest_status(outsider, area.pk) is None

    # inspection_summary with site filter.
    summary = inspection_summary(admin_user, site_id=site.pk)
    assert summary["total_inspections"] == 1
    assert summary["average_score"] is not None


@pytest.mark.django_db
def test_api_template_and_result_updates(site, admin_user, admin_client) -> None:
    template = _template(admin_user, site=site)
    updated = admin_client.put(
        f"/api/site-management/v1/inspection-templates/{template.pk}",
        data={"template_name": "Renamed", "frequency": "weekly"},
        content_type="application/json",
    )
    assert updated.status_code == 200
    assert updated.json()["template_name"] == "Renamed"

    # Replace items via PUT.
    replaced = admin_client.put(
        f"/api/site-management/v1/inspection-templates/{template.pk}",
        data={
            "template_name": "Renamed",
            "items": [{"item_label": "Single", "item_type": "text", "sequence": 1}],
        },
        content_type="application/json",
    )
    assert replaced.json()["item_count"] == 1

    # PATCH status deactivate then activate.
    deactivated = admin_client.patch(
        f"/api/site-management/v1/inspection-templates/{template.pk}/status",
        data={"is_active": False},
        content_type="application/json",
    )
    if deactivated.status_code != 200:
        print("DEACT", deactivated.status_code, deactivated.content)
    assert deactivated.status_code == 200
    assert deactivated.json()["is_active"] is False
    activated = admin_client.patch(
        f"/api/site-management/v1/inspection-templates/{template.pk}/status",
        data={"is_active": True},
        content_type="application/json",
    )
    if activated.status_code != 200:
        print("ACT", activated.status_code, activated.content)
    assert activated.status_code == 200
    assert activated.json()["is_active"] is True

    # PUT result update branch.
    template = _template(admin_user, site=site)
    area = SiteAreaFactory(site=site)
    inspection = start_inspection(site=site, area=area, template=template, inspected_by=admin_user, actor=admin_user)
    items = {i.item_label: i for i in template.items.all()}
    result = add_inspection_result(
        inspection=inspection, template_item=items["Comment"], actor=admin_user, value_text="draft"
    )
    updated_result = admin_client.put(
        f"/api/site-management/v1/inspections/{inspection.pk}/results/{result.pk}",
        data={"value_text": "final", "notes": "done"},
        content_type="application/json",
    )
    assert updated_result.status_code == 200
    assert updated_result.json()["value_text"] == "final"


@pytest.mark.django_db
def test_result_create_is_idempotent_and_repeated_save_uses_real_server_id(admin_client, admin_user, site):
    template = _template(admin_user, site=site)
    area = SiteAreaFactory(site=site)
    inspection = start_inspection(site=site, area=area, template=template, inspected_by=admin_user, actor=admin_user)
    item = template.items.first()
    assert item is not None

    first = admin_client.post(
        f"/api/site-management/v1/inspections/{inspection.pk}/results",
        data={"template_item_id": item.pk, "value_boolean": True, "passed": True, "notes": "first save"},
        content_type="application/json",
    )
    assert first.status_code == 200, first.content
    server_result_id = first.json()["id"]

    repeated = admin_client.post(
        f"/api/site-management/v1/inspections/{inspection.pk}/results",
        data={"template_item_id": item.pk, "value_boolean": False, "passed": False, "notes": "corrected save"},
        content_type="application/json",
    )
    assert repeated.status_code == 200, repeated.content
    assert repeated.json()["id"] == server_result_id
    assert repeated.json()["passed"] is False

    updated = admin_client.put(
        f"/api/site-management/v1/inspections/{inspection.pk}/results/{server_result_id}",
        data={"value_boolean": True, "passed": True, "notes": "final save"},
        content_type="application/json",
    )
    assert updated.status_code == 200, updated.content
    assert updated.json()["id"] == server_result_id
    assert updated.json()["notes"] == "final save"
