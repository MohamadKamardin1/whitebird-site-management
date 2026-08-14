"""Dedicated permission/scope hardening tests.

Every major policy is exercised against every role, plus cross-site/cross-zone
denials, service guards, admin queryset scoping and management-viewer
read-only enforcement.
"""

from datetime import date
from typing import Any, cast

import pytest
from django.test import Client, RequestFactory

from apps.accounts.factories import UserFactory
from apps.accounts.models import RoleCode, User
from apps.accounts.services import issue_api_token
from apps.core.errors import ForbiddenActionError
from apps.site_management.factories import (
    AssistantGeneralSupervisorAssignmentFactory,
    CleanerFactory,
    CleanerSiteAssignmentFactory,
    SiteFactory,
    SiteStoreFactory,
    SiteSupervisorAssignmentFactory,
    ZoneFactory,
    ZoneSupervisorAssignmentFactory,
)
from apps.site_management.models import (
    CleanerStatus,
    Issue,
    IssueSource,
)
from apps.site_management.policies import (
    can_assign_job,
    can_edit_cleaner,
    can_edit_issue,
    can_edit_site,
    can_export_data,
    can_manage_store,
    can_review_inspection,
    can_review_site_report,
    can_review_zone_report,
    can_submit_general_report,
    can_submit_site_report,
    can_verify_job,
    can_view_assignment,
    can_view_cleaner,
    can_view_inspection,
    can_view_issue,
    can_view_site,
)
from apps.site_management.scoping import visible_sites


@pytest.fixture(autouse=True)
def rbac_seeded(db: None) -> None:
    from django.core.management import call_command

    call_command("seed_rbac")


@pytest.fixture
def zones(db: Any) -> list[Any]:
    return [ZoneFactory(), ZoneFactory()]


@pytest.fixture
def sites(zones: list[Any]) -> list[Any]:
    return [SiteFactory(zone=zones[0]), SiteFactory(zone=zones[1])]


@pytest.fixture
def actors(sites: list[Any]) -> dict[str, User]:
    zone_a = sites[0].zone
    site_supervisor = cast(User, UserFactory(role=RoleCode.SITE_SUPERVISOR))
    SiteSupervisorAssignmentFactory(site=sites[0], user=site_supervisor)
    zone_supervisor = cast(User, UserFactory(role=RoleCode.ZONE_SUPERVISOR))
    ZoneSupervisorAssignmentFactory(zone=zone_a, user=zone_supervisor)
    ags = cast(User, UserFactory(role=RoleCode.ASSISTANT_GENERAL_SUPERVISOR))
    AssistantGeneralSupervisorAssignmentFactory(user=ags, all_zones=True)
    return {
        "admin": cast(User, UserFactory(role=RoleCode.SYSTEM_ADMIN)),
        "gs": cast(User, UserFactory(role=RoleCode.GENERAL_SUPERVISOR)),
        "ags": ags,
        "zone": zone_supervisor,
        "site": site_supervisor,
        "viewer": cast(User, UserFactory(role=RoleCode.MANAGEMENT_VIEWER)),
    }


def _authed(user: User) -> Client:
    return Client(HTTP_AUTHORIZATION=f"Bearer {issue_api_token(user=user, name='test').key}")


# --------------------------------------------------------------------------- #
# Policies — parametrized over roles
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
@pytest.mark.parametrize(
    "role_key, view_site_a, edit_site_a, view_site_b, edit_site_b",
    [
        ("admin", True, True, True, True),
        ("gs", True, True, True, True),
        ("ags", True, True, True, True),
        ("zone", True, True, False, False),
        ("site", True, True, False, False),
        ("viewer", True, False, True, False),
    ],
)
def test_site_policies_by_role(actors, sites, role_key, view_site_a, edit_site_a, view_site_b, edit_site_b) -> None:
    user = actors[role_key]
    assert can_view_site(user, sites[0]) is view_site_a
    assert can_edit_site(user, sites[0]) is edit_site_a
    assert can_view_site(user, sites[1]) is view_site_b
    assert can_edit_site(user, sites[1]) is edit_site_b


@pytest.mark.django_db
def test_cleaner_and_assignment_policies(actors, sites) -> None:
    cleaner = CleanerFactory(status=CleanerStatus.ACTIVE)
    assignment = CleanerSiteAssignmentFactory(cleaner=cleaner, site=sites[0], status="draft")

    # Every management role can view a cleaner in their scope (site_a).
    assert can_view_cleaner(actors["gs"], cleaner) is True
    assert can_view_cleaner(actors["admin"], cleaner) is True
    assert can_view_cleaner(actors["viewer"], cleaner) is True
    assert can_view_cleaner(actors["zone"], cleaner) is True
    assert can_view_cleaner(actors["site"], cleaner) is True
    # A site supervisor of another site cannot view it.
    outsider = UserFactory(role=RoleCode.SITE_SUPERVISOR)
    SiteSupervisorAssignmentFactory(site=sites[1], user=outsider)
    assert can_view_cleaner(outsider, cleaner) is False
    assert can_edit_cleaner(actors["gs"], cleaner) is True
    assert can_edit_cleaner(actors["admin"], cleaner) is True
    assert can_edit_cleaner(actors["viewer"], cleaner) is False

    # Assignment policies follow site scope.
    from apps.site_management.policies import can_edit_assignment

    assert can_view_assignment(actors["admin"], assignment) is True
    assert can_view_assignment(actors["zone"], assignment) is True
    assert can_view_assignment(actors["site"], assignment) is True
    assert can_edit_assignment(actors["viewer"], assignment) is False
    assert can_edit_assignment(actors["site"], assignment) is True


@pytest.mark.django_db
def test_inspection_and_store_policies(actors, sites) -> None:
    from apps.site_management.inspection_services import create_template, start_inspection

    area = None
    from apps.site_management.factories import SiteAreaFactory

    area = SiteAreaFactory(site=sites[0])
    template = create_template(
        template_name="Audit",
        actor=actors["admin"],
        site=sites[0],
        items=[{"item_label": "C", "item_type": "pass_fail", "sequence": 1}],
    )
    inspection = start_inspection(
        site=sites[0], area=area, template=template, inspected_by=actors["admin"], actor=actors["admin"]
    )
    assert can_view_inspection(actors["admin"], inspection) is True
    assert can_view_inspection(actors["zone"], inspection) is True
    assert can_view_inspection(actors["viewer"], inspection) is True
    assert can_review_inspection(actors["gs"], inspection) is True
    assert can_review_inspection(actors["zone"], inspection) is True
    assert can_review_inspection(actors["site"], inspection) is False  # site supervisor cannot review

    store = SiteStoreFactory(site=sites[0])
    assert can_manage_store(actors["site"], store) is True
    assert can_manage_store(actors["viewer"], store) is False


@pytest.mark.django_db
def test_issue_and_job_policies(actors, sites) -> None:
    issue = Issue.objects.create(
        title="X",
        site=sites[0],
        source=IssueSource.MANUAL,
        issue_category="other",
        priority="high",
        raised_by=actors["admin"],
    )
    from apps.site_management.issues_services import create_job

    job = create_job(job_title="J", site=sites[0], assigned_by=actors["admin"], actor=actors["admin"])

    assert can_view_issue(actors["viewer"], issue) is True
    assert can_view_issue(actors["site"], issue) is True
    assert can_edit_issue(actors["site"], issue) is True
    assert can_edit_issue(actors["viewer"], issue) is False

    assert can_assign_job(actors["gs"], job) is True
    assert can_assign_job(actors["site"], job) is True
    assert can_assign_job(actors["viewer"], job) is False
    assert can_verify_job(actors["gs"], job) is True
    assert can_verify_job(actors["zone"], job) is True
    assert can_verify_job(actors["viewer"], job) is False


@pytest.mark.django_db
def test_report_and_export_policies(actors, sites) -> None:
    from apps.site_management.models import GeneralManagementReport
    from apps.site_management.reporting_services import generate_site_report, generate_zone_summary

    report = generate_site_report(site_id=sites[0].pk, day=date.today(), user=actors["admin"])
    assert can_submit_site_report(actors["site"], report) is True
    assert can_submit_site_report(actors["viewer"], report) is False
    assert can_review_site_report(actors["zone"], report) is True
    assert can_review_site_report(actors["site"], report) is False

    zone_report = generate_zone_summary(zone_id=sites[0].zone_id, day=date.today(), user=actors["zone"])
    assert can_review_zone_report(actors["zone"], zone_report) is True
    assert can_review_zone_report(actors["site"], zone_report) is False

    general = GeneralManagementReport(report_date=date.today(), general_supervisor=actors["gs"])
    assert can_submit_general_report(actors["gs"], general) is True
    assert can_submit_general_report(actors["ags"], general) is False

    assert can_export_data(actors["viewer"], "issues") is True
    assert can_export_data(actors["gs"], "issues") is True


# --------------------------------------------------------------------------- #
# Cross-scope denial via scoping
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
def test_visible_sites_scoping(actors, sites) -> None:
    site_a, site_b = sites
    assert set(visible_sites(actors["admin"])) == {site_a, site_b}
    assert set(visible_sites(actors["gs"])) == {site_a, site_b}
    assert set(visible_sites(actors["ags"])) == {site_a, site_b}
    assert set(visible_sites(actors["zone"])) == {site_a}
    assert set(visible_sites(actors["site"])) == {site_a}


# --------------------------------------------------------------------------- #
# Service guards
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
def test_report_service_guards(actors, sites) -> None:
    from apps.site_management.reporting_services import generate_site_report, submit_site_report

    report = generate_site_report(site_id=sites[0].pk, day=date.today(), user=actors["admin"])
    with pytest.raises(ForbiddenActionError):
        submit_site_report(report=report, user=actors["viewer"])
    # A site supervisor from another site cannot submit.
    other = UserFactory(role=RoleCode.SITE_SUPERVISOR)
    SiteSupervisorAssignmentFactory(site=sites[1], user=other)
    with pytest.raises(ForbiddenActionError):
        submit_site_report(report=report, user=other)
    # The site's own supervisor can submit.
    submit_site_report(report=report, user=actors["site"])


@pytest.mark.django_db
def test_job_service_guards(actors, sites) -> None:
    from apps.site_management.issues_services import assign_job, create_job, verify_job

    job = create_job(job_title="J", site=sites[0], assigned_by=actors["admin"], actor=actors["admin"])
    with pytest.raises(ForbiddenActionError):
        assign_job(job=job, actor=actors["viewer"], assigned_to_user=actors["admin"])
    # Zone supervisor from another zone cannot assign.
    other_zone = UserFactory(role=RoleCode.ZONE_SUPERVISOR)
    ZoneSupervisorAssignmentFactory(zone=sites[1].zone, user=other_zone)
    with pytest.raises(ForbiddenActionError):
        assign_job(job=job, actor=other_zone, assigned_to_user=actors["admin"])

    assign_job(job=job, actor=actors["gs"], assigned_to_user=actors["admin"])
    with pytest.raises(ForbiddenActionError):
        verify_job(job=job, actor=actors["viewer"])


# --------------------------------------------------------------------------- #
# Admin scoping
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
def test_admin_queryset_scoping(actors, sites) -> None:
    from apps.site_management.admin import SiteAdmin, SiteStoreAdmin

    rf = RequestFactory()
    request = rf.get("/")
    request.user = actors["zone"]

    from apps.site_management.models import Site, SiteStore

    admin = SiteAdmin(Site, admin_site=None)
    assert {s.pk for s in admin.get_queryset(request)} == {sites[0].pk}

    store_admin = SiteStoreAdmin(SiteStore, admin_site=None)
    store = SiteStoreFactory(site=sites[0])
    assert store.pk in {s.pk for s in store_admin.get_queryset(request)}


@pytest.mark.django_db
def test_admin_viewer_read_only(actors, sites) -> None:
    from apps.site_management.admin import SiteStoreAdmin

    rf = RequestFactory()
    request = rf.get("/")
    request.user = actors["viewer"]
    from apps.site_management.models import SiteStore

    store_admin = SiteStoreAdmin(SiteStore, admin_site=None)
    assert store_admin.has_add_permission(request) is False
    assert store_admin.has_change_permission(request) is False
    assert store_admin.has_delete_permission(request) is False


# --------------------------------------------------------------------------- #
# API cross-scope denial
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
def test_api_cross_scope_denial(actors, sites) -> None:
    site_a, site_b = sites
    # Zone supervisor cannot read another zone's site.
    resp = _authed(actors["zone"]).get(f"/api/site-management/v1/sites/{site_b.pk}")
    assert resp.status_code in (401, 403)
    # Can read own zone.
    assert _authed(actors["zone"]).get(f"/api/site-management/v1/sites/{site_a.pk}").status_code == 200
    # Management viewer is read-only on write endpoints.
    denied = _authed(actors["viewer"]).post(
        "/api/site-management/v1/stores",
        data={"site_id": site_a.pk, "store_name": "X"},
        content_type="application/json",
    )
    assert denied.status_code in (401, 403)
