"""Tests for site configuration: shifts, areas, operational roles, working rules."""

from datetime import time
from unittest import mock

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import Client

from apps.accounts.factories import UserFactory
from apps.accounts.models import RoleCode, User
from apps.accounts.services import issue_api_token
from apps.site_management.factories import (
    SiteAreaFactory,
    SiteFactory,
    SiteShiftFactory,
    SiteSupervisorAssignmentFactory,
)
from apps.site_management.models import WorkMode
from apps.site_management.services import (
    create_area,
    create_operational_role,
    create_shift,
    deactivate_area,
    deactivate_operational_role,
    deactivate_shift,
    update_area,
    update_operational_role,
    update_shift,
)
from apps.site_management.validation import (
    validate_area_belongs_to_site,
    validate_shift_belongs_to_site,
    validate_site_configuration_consistency,
    validate_site_work_mode,
)


@pytest.fixture(autouse=True)
def rbac_seeded(db: None) -> None:
    """Ensure group permissions exist so role-based config access works."""
    from django.core.management import call_command

    call_command("seed_rbac")


def _authed(user: User) -> Client:
    return Client(HTTP_AUTHORIZATION=f"Bearer {issue_api_token(user=user, name='test').key}")


# --------------------------------------------------------------------------- #
# Shifts
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
def test_create_shift_and_overnight_logic(site, admin_user) -> None:
    site.work_mode = WorkMode.FULL_TIME_AND_SHIFT
    site.save(update_fields=["work_mode"])
    shift = create_shift(
        site=site,
        shift_name="Night",
        start_time=time(22, 0),
        end_time=time(6, 0),
        effective_days=["mon", "tue"],
        actor=admin_user,
    )
    assert shift.crosses_midnight is True
    day = create_shift(
        site=site,
        shift_name="Day",
        start_time=time(8, 0),
        end_time=time(16, 0),
        effective_days=["mon"],
        actor=admin_user,
    )
    assert day.crosses_midnight is False


@pytest.mark.django_db
def test_shift_effective_days_required_and_valid(site, admin_user) -> None:
    site.work_mode = WorkMode.SHIFT
    site.save(update_fields=["work_mode"])
    with pytest.raises(ValidationError):
        create_shift(
            site=site, shift_name="X", start_time=time(8), end_time=time(12), effective_days=[], actor=admin_user
        )
    with pytest.raises(ValidationError):
        create_shift(
            site=site,
            shift_name="X",
            start_time=time(8),
            end_time=time(12),
            effective_days=["someday"],
            actor=admin_user,
        )


@pytest.mark.django_db
def test_shift_times_required(site, admin_user) -> None:
    site.work_mode = WorkMode.SHIFT
    site.save(update_fields=["work_mode"])
    with pytest.raises(ValidationError):
        create_shift(
            site=site, shift_name="X", start_time=None, end_time=time(12), effective_days=["mon"], actor=admin_user
        )


@pytest.mark.django_db
def test_update_and_deactivate_shift(site, admin_user) -> None:
    site.work_mode = WorkMode.SHIFT
    site.save(update_fields=["work_mode"])
    shift = create_shift(
        site=site, shift_name="A", start_time=time(8), end_time=time(16), effective_days=["mon"], actor=admin_user
    )
    create_shift(
        site=site, shift_name="B", start_time=time(16), end_time=time(23), effective_days=["mon"], actor=admin_user
    )
    updated = update_shift(shift=shift, actor=admin_user, shift_name="Morning", start_time=time(9))
    assert updated.shift_name == "Morning"
    assert updated.start_time == time(9)

    deactivated = deactivate_shift(shift=updated, actor=admin_user)
    assert deactivated.is_active is False


@pytest.mark.django_db
def test_shift_deactivation_refuses_when_in_use(site, admin_user) -> None:
    site.work_mode = WorkMode.SHIFT
    site.save(update_fields=["work_mode"])
    shift = create_shift(
        site=site, shift_name="A", start_time=time(8), end_time=time(16), effective_days=["mon"], actor=admin_user
    )
    with (
        mock.patch.object(type(shift), "has_operational_usage", new_callable=mock.PropertyMock, return_value=True),
        pytest.raises(ValidationError),
    ):
        deactivate_shift(shift=shift, actor=admin_user)


@pytest.mark.django_db
def test_shift_name_and_code_unique_when_active(site, admin_user) -> None:
    site.work_mode = WorkMode.SHIFT
    site.save(update_fields=["work_mode"])
    create_shift(
        site=site,
        shift_name="Morning",
        shift_code="M1",
        start_time=time(8),
        end_time=time(12),
        effective_days=["mon"],
        actor=admin_user,
    )
    with pytest.raises(ValidationError):
        create_shift(
            site=site,
            shift_name="Morning",
            shift_code="M2",
            start_time=time(8),
            end_time=time(12),
            effective_days=["mon"],
            actor=admin_user,
        )
    with pytest.raises(ValidationError):
        create_shift(
            site=site,
            shift_name="Other",
            shift_code="M1",
            start_time=time(13),
            end_time=time(17),
            effective_days=["mon"],
            actor=admin_user,
        )


@pytest.mark.django_db
def test_duplicate_overlapping_shifts_flagged(site, admin_user) -> None:
    site.work_mode = WorkMode.SHIFT
    site.save(update_fields=["work_mode"])
    create_shift(
        site=site, shift_name="First", start_time=time(8), end_time=time(12), effective_days=["mon"], actor=admin_user
    )
    create_shift(
        site=site, shift_name="Second", start_time=time(8), end_time=time(12), effective_days=["mon"], actor=admin_user
    )
    with pytest.raises(ValidationError):
        validate_site_configuration_consistency(site)


# --------------------------------------------------------------------------- #
# Work mode enforcement
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
def test_full_time_site_cannot_have_active_shifts(site, admin_user) -> None:
    site.work_mode = WorkMode.FULL_TIME
    site.save(update_fields=["work_mode"])
    with pytest.raises(ValidationError):
        create_shift(
            site=site, shift_name="X", start_time=time(8), end_time=time(16), effective_days=["mon"], actor=admin_user
        )


@pytest.mark.django_db
def test_shift_site_requires_active_shift(site) -> None:
    site.work_mode = WorkMode.SHIFT
    site.save(update_fields=["work_mode"])
    with pytest.raises(ValidationError):
        validate_site_work_mode(site)
    site.shifts.create(shift_name="S", start_time=time(8), end_time=time(16), effective_days=["mon"])
    validate_site_work_mode(site)  # no error


@pytest.mark.django_db
def test_shift_belongs_to_site(site, admin_user) -> None:
    other = SiteFactory()
    shift = SiteShiftFactory(site=other)
    with pytest.raises(ValidationError):
        validate_shift_belongs_to_site(site, shift)


# --------------------------------------------------------------------------- #
# Areas
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
def test_area_lifecycle_and_uniqueness(site, admin_user) -> None:
    area = create_area(site=site, area_name="Lobby", actor=admin_user)
    updated = update_area(area=area, actor=admin_user, floor="Ground")
    assert updated.floor == "Ground"
    deactivated = deactivate_area(area=updated, actor=admin_user)
    assert deactivated.is_active is False
    # Duplicate name is rejected last (after deactivation) to keep the
    # transaction clean for assertions.
    with pytest.raises(IntegrityError):
        SiteAreaFactory(site=site, area_name="Lobby")


@pytest.mark.django_db
def test_area_deactivation_refuses_when_in_use(site, admin_user) -> None:
    area = create_area(site=site, area_name="Kitchen", actor=admin_user)
    with (
        mock.patch.object(type(area), "has_operational_usage", new_callable=mock.PropertyMock, return_value=True),
        pytest.raises(ValidationError),
    ):
        deactivate_area(area=area, actor=admin_user)


@pytest.mark.django_db
def test_area_belongs_to_site(site, admin_user) -> None:
    other = SiteFactory()
    area = SiteAreaFactory(site=other)
    with pytest.raises(ValidationError):
        validate_area_belongs_to_site(site, area)


# --------------------------------------------------------------------------- #
# Operational roles
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
def test_operational_role_lifecycle(admin_user) -> None:
    role = create_operational_role(name="Toilet Cleaner", code="toilet-cleaner", actor=admin_user)
    updated = update_operational_role(role=role, actor=admin_user, description="Cleans toilets")
    assert updated.description == "Cleans toilets"
    deactivated = deactivate_operational_role(role=updated, actor=admin_user)
    assert deactivated.is_active is False


@pytest.mark.django_db
def test_operational_role_deactivation_refuses_when_in_use(admin_user) -> None:
    role = create_operational_role(name="Floor Cleaner", code="floor-cleaner", actor=admin_user)
    with (
        mock.patch.object(type(role), "has_operational_usage", new_callable=mock.PropertyMock, return_value=True),
        pytest.raises(ValidationError),
    ):
        deactivate_operational_role(role=role, actor=admin_user)


@pytest.mark.django_db
def test_operational_role_unique_code(admin_user) -> None:
    create_operational_role(name="One", code="role-1", actor=admin_user)
    with pytest.raises(ValidationError):
        create_operational_role(name="Two", code="role-1", actor=admin_user)


# --------------------------------------------------------------------------- #
# Working rules
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
def test_working_rule_defaults_and_get_or_create(site) -> None:
    from apps.site_management.selectors import get_site_working_rule

    rule = get_site_working_rule(site)
    assert rule.attendance_locked is False
    assert rule.require_shift_area_assignment is False
    assert get_site_working_rule(site).pk == rule.pk


# --------------------------------------------------------------------------- #
# API permissions
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
def test_shift_api_permissions(site, admin_user, admin_client, viewer_client, site_supervisor_user) -> None:
    site.work_mode = WorkMode.SHIFT
    site.save(update_fields=["work_mode"])

    payload = {"shift_name": "Morning", "start_time": "08:00:00", "end_time": "16:00:00", "effective_days": ["mon"]}

    # Viewer cannot write.
    viewer = UserFactory(role=RoleCode.MANAGEMENT_VIEWER)
    denied = _authed(viewer).post(
        f"/api/site-management/v1/sites/{site.pk}/shifts", data=payload, content_type="application/json"
    )
    assert denied.status_code in (401, 403)

    # System admin can write and read.
    created = admin_client.post(
        f"/api/site-management/v1/sites/{site.pk}/shifts", data=payload, content_type="application/json"
    )
    assert created.status_code == 200
    listed = admin_client.get(f"/api/site-management/v1/sites/{site.pk}/shifts")
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    assert listed.json()[0]["crosses_midnight"] is False

    # Site supervisor can review assigned-site configuration but cannot mutate it.
    SiteSupervisorAssignmentFactory(site=site, user=site_supervisor_user)
    supervisor_client = _authed(site_supervisor_user)
    evening = dict(payload, shift_name="Evening")
    assert supervisor_client.post(
        f"/api/site-management/v1/sites/{site.pk}/shifts", data=evening, content_type="application/json"
    ).status_code == 403


@pytest.mark.django_db
def test_shift_status_endpoint(site, admin_client, admin_user) -> None:
    site.work_mode = WorkMode.FULL_TIME_AND_SHIFT
    site.save(update_fields=["work_mode"])
    shift = create_shift(
        site=site, shift_name="S", start_time=time(8), end_time=time(16), effective_days=["mon"], actor=admin_user
    )
    response = admin_client.patch(
        f"/api/site-management/v1/sites/{site.pk}/shifts/{shift.pk}/status",
        data={"is_active": False},
        content_type="application/json",
    )
    assert response.status_code == 200
    assert response.json()["is_active"] is False


@pytest.mark.django_db
def test_areas_api(admin_client, admin_user, site) -> None:
    created = admin_client.post(
        f"/api/site-management/v1/sites/{site.pk}/areas", data={"area_name": "Lobby"}, content_type="application/json"
    )
    assert created.status_code == 200
    area_id = created.json()["id"]
    updated = admin_client.put(
        f"/api/site-management/v1/sites/{site.pk}/areas/{area_id}",
        data={"floor": "Ground"},
        content_type="application/json",
    )
    assert updated.status_code == 200
    assert updated.json()["floor"] == "Ground"
    status = admin_client.patch(
        f"/api/site-management/v1/sites/{site.pk}/areas/{area_id}/status",
        data={"is_active": False},
        content_type="application/json",
    )
    assert status.json()["is_active"] is False


@pytest.mark.django_db
def test_operational_roles_api(admin_client, viewer_user) -> None:
    created = admin_client.post(
        "/api/site-management/v1/operational-roles",
        data={"name": "Compound Sweeper", "code": "compound-sweeper"},
        content_type="application/json",
    )
    assert created.status_code == 200
    role_id = created.json()["id"]

    listed = admin_client.get("/api/site-management/v1/operational-roles")
    assert any(r["code"] == "compound-sweeper" for r in listed.json())

    updated = admin_client.put(
        f"/api/site-management/v1/operational-roles/{role_id}",
        data={"description": "Sweeps the compound"},
        content_type="application/json",
    )
    assert updated.json()["description"] == "Sweeps the compound"

    status = admin_client.patch(
        f"/api/site-management/v1/operational-roles/{role_id}/status",
        data={"is_active": False},
        content_type="application/json",
    )
    assert status.json()["is_active"] is False

    # Viewer cannot write roles.
    denied = _authed(viewer_user).post(
        "/api/site-management/v1/operational-roles",
        data={"name": "X", "code": "x-role"},
        content_type="application/json",
    )
    assert denied.status_code in (401, 403)


@pytest.mark.django_db
def test_site_config_404s(admin_client, site) -> None:
    status = admin_client.patch(
        f"/api/site-management/v1/sites/{site.pk}/shifts/999999/status",
        data={"is_active": True},
        content_type="application/json",
    )
    assert status.status_code == 404
    area = admin_client.patch(
        f"/api/site-management/v1/sites/{site.pk}/areas/999999/status",
        data={"is_active": True},
        content_type="application/json",
    )
    assert area.status_code == 404
    role = admin_client.patch(
        "/api/site-management/v1/operational-roles/999999/status",
        data={"is_active": True},
        content_type="application/json",
    )
    assert role.status_code == 404
