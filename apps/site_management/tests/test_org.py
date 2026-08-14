"""Tests for the organisation hierarchy: zones, sites, supervisor assignments."""

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import Client
from django.utils import timezone

from apps.accounts.factories import UserFactory
from apps.accounts.models import RoleCode, User
from apps.accounts.services import issue_api_token
from apps.site_management.factories import (
    AssistantGeneralSupervisorAssignmentFactory,
    SiteFactory,
    SiteSupervisorAssignmentFactory,
    ZoneFactory,
    ZoneSupervisorAssignmentFactory,
)
from apps.site_management.models import WorkMode, Zone
from apps.site_management.scoping import (
    assigned_zone_ids,
    site_in_user_scope,
    supervised_sites,
    visible_sites,
    visible_zones,
)
from apps.site_management.services import (
    assign_site_supervisor,
    assign_zone_supervisor,
    create_zone,
    deactivate_zone,
    end_site_supervisor_assignment,
    end_zone_supervisor_assignment,
    restore_zone,
    update_zone,
)

# --------------------------------------------------------------------------- #
# Model constraints
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
def test_zone_code_is_unique() -> None:
    ZoneFactory(code="ZN01")
    with pytest.raises(IntegrityError):
        ZoneFactory(code="ZN01")


@pytest.mark.django_db
def test_site_code_is_unique() -> None:
    SiteFactory(code="SITE001")
    with pytest.raises(IntegrityError):
        SiteFactory(code="SITE001")


@pytest.mark.django_db
def test_zone_soft_deactivate_hides_from_default_manager() -> None:
    zone = ZoneFactory()
    zone.is_active = False
    zone.save(update_fields=["is_active"])
    assert Zone.objects.count() == 0
    assert Zone.objects.all_with_deleted().count() == 1


@pytest.mark.django_db
def test_working_days_validation() -> None:
    SiteFactory(working_days=["mon", "fri"])
    with pytest.raises(ValidationError):
        SiteFactory(working_days=["someday"]).full_clean()
    with pytest.raises(ValidationError):
        SiteFactory(working_days="mon").full_clean()


@pytest.mark.django_db
def test_work_mode_is_validated() -> None:
    site = SiteFactory()
    assert site.work_mode in WorkMode.values


# --------------------------------------------------------------------------- #
# Supervisor assignment rules
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
def test_assign_site_supervisor_respects_constance_max() -> None:
    from constance import config

    site = SiteFactory()
    max_supervisors = int(config.MAX_SITE_SUPERVISORS_PER_SITE)
    for _ in range(max_supervisors):
        assign_site_supervisor(site=site, user=UserFactory(), assigned_from=timezone.localdate(), actor=site.created_by)
    with pytest.raises(ValidationError):
        assign_site_supervisor(site=site, user=UserFactory(), assigned_from=timezone.localdate(), actor=site.created_by)


@pytest.mark.django_db
def test_site_supervisor_active_assignment_is_unique_per_user() -> None:
    site = SiteFactory()
    user = UserFactory()
    SiteSupervisorAssignmentFactory(site=site, user=user)
    with pytest.raises(IntegrityError):
        SiteSupervisorAssignmentFactory(site=site, user=user)


@pytest.mark.django_db
def test_ags_requires_zone_when_not_all_zones() -> None:
    user = UserFactory(role=RoleCode.ASSISTANT_GENERAL_SUPERVISOR)
    invalid = AssistantGeneralSupervisorAssignmentFactory.build(user=user, all_zones=False, zone=None)
    with pytest.raises(ValidationError):
        invalid.full_clean()

    ok = AssistantGeneralSupervisorAssignmentFactory(user=user, all_zones=True, zone=None)
    ok.full_clean()  # no error


@pytest.mark.django_db
def test_ags_single_active_per_user() -> None:
    user = UserFactory(role=RoleCode.ASSISTANT_GENERAL_SUPERVISOR)
    AssistantGeneralSupervisorAssignmentFactory(user=user, all_zones=True)
    with pytest.raises(IntegrityError):
        AssistantGeneralSupervisorAssignmentFactory(user=user, all_zones=False, zone=ZoneFactory())


@pytest.mark.django_db
def test_assignment_date_range_validation() -> None:
    from datetime import timedelta

    site = SiteFactory()
    assignment = SiteSupervisorAssignmentFactory(
        site=site,
        user=UserFactory(),
        assigned_from=timezone.localdate(),
        assigned_to=timezone.localdate() - timedelta(days=1),
    )
    with pytest.raises(ValidationError):
        assignment.full_clean()


# --------------------------------------------------------------------------- #
# Scoping selectors
# --------------------------------------------------------------------------- #


def _authed(user: User) -> Client:
    return Client(HTTP_AUTHORIZATION=f"Bearer {issue_api_token(user=user, name='test').key}")


@pytest.mark.django_db
def test_scoping_for_every_role() -> None:
    zone_a = ZoneFactory()
    zone_b = ZoneFactory()
    site_a = SiteFactory(zone=zone_a)
    site_b = SiteFactory(zone=zone_b)

    admin = UserFactory(role=RoleCode.SYSTEM_ADMIN)
    general = UserFactory(role=RoleCode.GENERAL_SUPERVISOR)
    viewer = UserFactory(role=RoleCode.MANAGEMENT_VIEWER)
    site_supervisor = UserFactory(role=RoleCode.SITE_SUPERVISOR)
    zone_supervisor = UserFactory(role=RoleCode.ZONE_SUPERVISOR)
    ags_zones = UserFactory(role=RoleCode.ASSISTANT_GENERAL_SUPERVISOR)
    ags_all = UserFactory(role=RoleCode.ASSISTANT_GENERAL_SUPERVISOR)

    SiteSupervisorAssignmentFactory(site=site_a, user=site_supervisor)
    ZoneSupervisorAssignmentFactory(zone=zone_a, user=zone_supervisor)
    AssistantGeneralSupervisorAssignmentFactory(user=ags_zones, all_zones=False, zone=zone_a)
    AssistantGeneralSupervisorAssignmentFactory(user=ags_all, all_zones=True, zone=None)

    def sites(user: User) -> set[int]:
        return set(visible_sites(user).values_list("pk", flat=True))

    def zones(user: User) -> set[int]:
        return set(visible_zones(user).values_list("pk", flat=True))

    def supervised(user: User) -> set[int]:
        return set(supervised_sites(user).values_list("pk", flat=True))

    # Admin & general see everything.
    assert sites(admin) == {site_a.pk, site_b.pk}
    assert sites(general) == {site_a.pk, site_b.pk}
    assert zones(general) == {zone_a.pk, zone_b.pk}
    assert supervised(general) == {site_a.pk, site_b.pk}

    # Viewer sees everything but supervises nothing.
    assert sites(viewer) == {site_a.pk, site_b.pk}
    assert supervised(viewer) == set()

    # Site supervisor sees only assigned sites.
    assert sites(site_supervisor) == {site_a.pk}
    assert supervised(site_supervisor) == {site_a.pk}
    assert site_in_user_scope(site_supervisor, site_b.pk) is False

    # Zone supervisor sees sites in assigned zone.
    assert sites(zone_supervisor) == {site_a.pk}
    assert assigned_zone_ids(zone_supervisor) == {zone_a.pk}

    # Assistant (scoped) sees only assigned zone's sites.
    assert sites(ags_zones) == {site_a.pk}
    assert zones(ags_zones) == {zone_a.pk}

    # Assistant (all zones) sees everything.
    assert sites(ags_all) == {site_a.pk, site_b.pk}
    assert zones(ags_all) == {zone_a.pk, zone_b.pk}


# --------------------------------------------------------------------------- #
# API visibility by role
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
def test_zones_api_paginated(admin_client, admin_user) -> None:
    for _ in range(3):
        create_zone(name=f"Zone {_}", actor=admin_user)
    response = admin_client.get("/api/site-management/v1/zones")
    assert response.status_code == 200
    body = response.json()
    assert body["count"] >= 3
    assert "results" in body
    assert "next" in body and "previous" in body


@pytest.mark.django_db
def test_zones_api_scoped_by_role(site_supervisor_client, site_supervisor_user, zone_client, zone_user, site) -> None:
    # Site supervisor has no zone scope -> sees no zones.
    response = site_supervisor_client.get("/api/site-management/v1/zones")
    assert response.status_code == 200
    assert response.json()["count"] == 0

    # Zone supervisor sees only their zone.
    ZoneSupervisorAssignmentFactory(zone=site.zone, user=zone_user)
    response = zone_client.get("/api/site-management/v1/zones")
    assert response.status_code == 200
    assert [z["name"] for z in response.json()["results"]] == [site.zone.name]


@pytest.mark.django_db
def test_sites_api_scoped_by_role(site_supervisor_client, site_supervisor_user, site) -> None:
    response = site_supervisor_client.get("/api/site-management/v1/sites")
    assert response.status_code == 200
    assert response.json()["count"] == 0

    SiteSupervisorAssignmentFactory(site=site, user=site_supervisor_user)
    response = site_supervisor_client.get("/api/site-management/v1/sites")
    assert response.json()["count"] == 1
    assert response.json()["results"][0]["name"] == site.name
    assert response.json()["results"][0]["zone_name"] == site.zone.name


@pytest.mark.django_db
def test_site_detail_scoped(site_supervisor_client, site_supervisor_user, site) -> None:
    assert site_supervisor_client.get(f"/api/site-management/v1/sites/{site.pk}").status_code == 403
    SiteSupervisorAssignmentFactory(site=site, user=site_supervisor_user)
    response = site_supervisor_client.get(f"/api/site-management/v1/sites/{site.pk}")
    assert response.status_code == 200
    assert response.json()["work_mode"] == WorkMode.FULL_TIME


@pytest.mark.django_db
def test_site_supervisors_endpoint(admin_client, admin_user, site) -> None:
    supervisor = UserFactory(role=RoleCode.SITE_SUPERVISOR)
    assign_site_supervisor(site=site, user=supervisor, assigned_from=timezone.localdate(), actor=admin_user)
    response = admin_client.get(f"/api/site-management/v1/sites/{site.pk}/supervisors")
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["email"] == supervisor.email


@pytest.mark.django_db
def test_site_supervisors_endpoint_scoped(site_supervisor_client, site) -> None:
    assert site_supervisor_client.get(f"/api/site-management/v1/sites/{site.pk}/supervisors").status_code == 403


@pytest.mark.django_db
def test_sites_pagination_envelope(admin_client, admin_user) -> None:
    for i in range(5):
        create_zone(name=f"Zone {i}", actor=admin_user)
    for i in range(5):
        SiteFactory(name=f"Paginated Site {i}")
    response = admin_client.get("/api/site-management/v1/sites?page=1&page_size=2")
    body = response.json()
    assert body["count"] >= 5
    assert len(body["results"]) == 2
    assert body["next"] is not None
    assert body["previous"] is None


# --------------------------------------------------------------------------- #
# Zone + assignment services
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
def test_zone_service_lifecycle(admin_user) -> None:
    zone = create_zone(name="Coastal", actor=admin_user)
    assert zone.code
    zone = update_zone(zone=zone, name="Coastal North", actor=admin_user)
    assert zone.name == "Coastal North"
    deactivated = deactivate_zone(zone=zone, actor=admin_user)
    assert deactivated.is_active is False
    restored = restore_zone(zone=deactivated, actor=admin_user)
    assert restored.is_active is True


@pytest.mark.django_db
def test_end_site_supervisor_assignment(site, site_supervisor_user, admin_user) -> None:
    assignment = assign_site_supervisor(
        site=site, user=site_supervisor_user, assigned_from=timezone.localdate(), actor=admin_user
    )
    ended = end_site_supervisor_assignment(assignment=assignment, actor=admin_user)
    assert ended.is_active is False
    assert site_in_user_scope(site_supervisor_user, site.pk) is False


@pytest.mark.django_db
def test_zone_supervisor_service_lifecycle(zone, zone_user, admin_user) -> None:
    assignment = assign_zone_supervisor(zone=zone, user=zone_user, assigned_from=timezone.localdate(), actor=admin_user)
    ended = end_zone_supervisor_assignment(assignment=assignment, actor=admin_user)
    assert ended.is_active is False


@pytest.mark.django_db
def test_ags_service_lifecycle(admin_user) -> None:
    from apps.accounts.factories import UserFactory as UFactory
    from apps.site_management.services import (
        assign_assistant_general_supervisor,
        end_assistant_general_supervisor_assignment,
    )

    user = UFactory(role=RoleCode.ASSISTANT_GENERAL_SUPERVISOR)
    assignment = assign_assistant_general_supervisor(
        user=user, all_zones=True, assigned_from=timezone.localdate(), actor=admin_user
    )
    ended = end_assistant_general_supervisor_assignment(assignment=assignment, actor=admin_user)
    assert ended.is_active is False


@pytest.mark.django_db
def test_ags_service_requires_zone_when_scoped(admin_user) -> None:
    from apps.accounts.factories import UserFactory as UFactory
    from apps.site_management.services import assign_assistant_general_supervisor

    user = UFactory(role=RoleCode.ASSISTANT_GENERAL_SUPERVISOR)
    with pytest.raises(ValidationError):
        assign_assistant_general_supervisor(
            user=user, all_zones=False, zone=None, assigned_from=timezone.localdate(), actor=admin_user
        )


@pytest.mark.django_db
def test_active_site_supervisor_ids(site, site_supervisor_user) -> None:
    from apps.site_management.scoping import active_site_supervisor_ids

    SiteSupervisorAssignmentFactory(site=site, user=site_supervisor_user)
    assert active_site_supervisor_ids(site.pk) == {site_supervisor_user.pk}
    assert active_site_supervisor_ids(site.pk + 1000) == set()


@pytest.mark.django_db
def test_supervised_sites_empty_for_unknown_role() -> None:
    from apps.accounts.factories import UserFactory as UFactory

    user = UFactory()  # role defaults to management_viewer
    assert supervised_sites(user).count() == 0


@pytest.mark.django_db
def test_scoping_admin_and_general_sees_all(admin_user) -> None:
    general = UserFactory(role=RoleCode.GENERAL_SUPERVISOR)
    zone = ZoneFactory()
    site = SiteFactory(zone=zone)
    assert site_in_user_scope(admin_user, site.pk) is True
    assert set(visible_sites(general).values_list("pk", flat=True)) == {site.pk}
    assert set(visible_zones(admin_user).values_list("pk", flat=True)) == {zone.pk}
