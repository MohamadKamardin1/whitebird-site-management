from __future__ import annotations

import pytest
from django.test import Client
from django.utils import timezone

from apps.accounts.factories import UserFactory
from apps.accounts.models import RoleCode, User
from apps.accounts.services import issue_api_token
from apps.core.models import AuditLog
from apps.site_management.factories import SiteFactory, ZoneFactory, ZoneSupervisorAssignmentFactory
from apps.site_management.models import SupervisorChecklistSubmission, SupervisorTimetableEntry


def _authed(user: User) -> Client:
    return Client(HTTP_AUTHORIZATION=f"Bearer {issue_api_token(user=user, name='supervisor-roster').key}")


@pytest.mark.django_db
def test_personal_timetable_and_pdf_checklists_are_scoped_and_audited(admin_user: User) -> None:
    zone = ZoneFactory()
    other_zone = ZoneFactory()
    site = SiteFactory(zone=zone)
    other_site = SiteFactory(zone=other_zone)
    supervisor = UserFactory(role=RoleCode.ZONE_SUPERVISOR)
    outsider = UserFactory(role=RoleCode.ZONE_SUPERVISOR)
    ZoneSupervisorAssignmentFactory(zone=zone, user=supervisor)
    ZoneSupervisorAssignmentFactory(zone=other_zone, user=outsider)
    admin_client = _authed(admin_user)
    work_date = timezone.localdate()
    weekday = work_date.strftime("%a").lower()
    created = admin_client.post(
        "/api/site-management/v1/admin/supervisor-timetables",
        data={
            "supervisor_id": supervisor.pk,
            "zone_id": zone.pk,
            "site_id": site.pk,
            "effective_from": work_date.isoformat(),
            "work_days": [weekday],
            "off_days": [],
            "shift_slot": "asubuhi",
        },
        content_type="application/json",
    )
    assert created.status_code == 200, created.content
    entry_id = created.json()["id"]
    assert SupervisorTimetableEntry.objects.filter(pk=entry_id, supervisor=supervisor).exists()
    assert AuditLog.objects.filter(summary__contains="Created personal timetable entry").exists()

    denied = admin_client.post(
        "/api/site-management/v1/admin/supervisor-timetables",
        data={
            "supervisor_id": supervisor.pk,
            "zone_id": other_zone.pk,
            "site_id": other_site.pk,
            "effective_from": work_date.isoformat(),
            "work_days": [weekday],
            "off_days": [],
            "shift_slot": "asubuhi",
        },
        content_type="application/json",
    )
    assert denied.status_code == 422

    own_client = _authed(supervisor)
    timetable = own_client.get(f"/api/site-management/v1/supervisor/timetable?work_date={work_date.isoformat()}")
    assert timetable.status_code == 200
    assert [row["id"] for row in timetable.json()] == [entry_id]
    assert _authed(outsider).get(f"/api/site-management/v1/supervisor/timetable?work_date={work_date.isoformat()}").json() == []

    saved = own_client.post(
        "/api/site-management/v1/supervisor/checklists",
        data={
            "timetable_entry_id": entry_id,
            "work_date": work_date.isoformat(),
            "checklist_kind": "site_zilizotembelewa",
            "table_entries": [{"JINA LA SITE": site.name, "maelezo": "Ziara imefanyika."}],
            "notes": "",
        },
        content_type="application/json",
    )
    assert saved.status_code == 200, saved.content
    submission_id = saved.json()["id"]
    submitted = own_client.post(f"/api/site-management/v1/supervisor/checklists/{submission_id}/submit")
    assert submitted.status_code == 200, submitted.content
    assert submitted.json()["status"] == "submitted"
    record = SupervisorChecklistSubmission.objects.get(pk=submission_id)
    assert record.snapshot["table_label"] == "SITE ZILIZO TEMBELEWA"
    assert record.snapshot["site_name"] == site.name
    assert AuditLog.objects.filter(summary__contains="Submitted SITE ZILIZO TEMBELEWA").exists()

    reviewed = admin_client.post(
        f"/api/site-management/v1/supervisor/checklists/{submission_id}/review",
        data={"action": "reviewed", "reason": ""},
        content_type="application/json",
    )
    assert reviewed.status_code == 200, reviewed.content
    assert reviewed.json()["status"] == "reviewed"

    blocked = _authed(outsider).post(
        "/api/site-management/v1/supervisor/checklists",
        data={
            "timetable_entry_id": entry_id,
            "work_date": work_date.isoformat(),
            "checklist_kind": "site_zilizotembelewa",
            "table_entries": [{"JINA LA SITE": site.name, "maelezo": "bad"}],
        },
        content_type="application/json",
    )
    assert blocked.status_code == 403


@pytest.mark.django_db
def test_assistant_general_supervisor_only_gets_the_pdf_work_done_table(admin_user: User) -> None:
    zone = ZoneFactory()
    site = SiteFactory(zone=zone)
    assistant = UserFactory(role=RoleCode.ASSISTANT_GENERAL_SUPERVISOR)
    from apps.site_management.factories import AssistantGeneralSupervisorAssignmentFactory

    AssistantGeneralSupervisorAssignmentFactory(user=assistant, all_zones=False, zone=zone)
    work_date = timezone.localdate()
    entry = SupervisorTimetableEntry.objects.create(
        supervisor=assistant,
        zone=zone,
        site=site,
        effective_from=work_date,
        work_days=[work_date.strftime("%a").lower()],
        off_days=[],
        shift_slot="mchana",
        created_by=admin_user,
        updated_by=admin_user,
    )
    client = _authed(assistant)
    forbidden = client.post(
        "/api/site-management/v1/supervisor/checklists",
        data={"timetable_entry_id": entry.pk, "work_date": work_date.isoformat(), "checklist_kind": "site_zilizotembelewa", "table_entries": [{"maelezo": "x"}]},
        content_type="application/json",
    )
    assert forbidden.status_code == 403
    accepted = client.post(
        "/api/site-management/v1/supervisor/checklists",
        data={"timetable_entry_id": entry.pk, "work_date": work_date.isoformat(), "checklist_kind": "kazi_zilizofanyika", "table_entries": [{"maelezo": "Kazi imefanyika."}]},
        content_type="application/json",
    )
    assert accepted.status_code == 200, accepted.content
