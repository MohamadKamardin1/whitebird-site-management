"""Tests for the audit logging system."""

import pytest

from apps.core.models import AuditLog
from apps.core.selectors import list_audit_logs
from apps.core.services import model_data, record_audit
from apps.site_management.services import SiteDraft, create_site


@pytest.mark.django_db
def test_record_audit_with_entity(admin_user, site) -> None:
    entry = record_audit(action=AuditLog.Action.ARCHIVE, actor=admin_user, entity=site)
    assert entry.model_name == "site_management.site"
    assert entry.object_id == str(site.pk)
    assert entry.user == admin_user
    assert entry.object_repr == str(site)
    assert entry.action == AuditLog.Action.ARCHIVE


@pytest.mark.django_db
def test_record_audit_with_explicit_identity(admin_user) -> None:
    entry = record_audit(
        action="custom_action",
        user=admin_user,
        model_name="core.auditlog",
        object_id="42",
        object_repr="Legacy row",
        before_data={"a": 1},
        after_data={"a": 2},
    )
    assert entry.model_name == "core.auditlog"
    assert entry.before_data == {"a": 1}
    assert entry.after_data == {"a": 2}


@pytest.mark.django_db
def test_record_audit_requires_identity(admin_user) -> None:
    with pytest.raises(ValueError):
        record_audit(action=AuditLog.Action.CREATE, actor=admin_user)


@pytest.mark.django_db
def test_model_data_is_json_safe(admin_user, site) -> None:
    snapshot = model_data(site)
    assert snapshot["name"] == site.name
    assert snapshot["capacity"] == site.capacity
    assert isinstance(snapshot["created_at"], str)
    import json

    json.dumps(snapshot)  # must be serialisable


@pytest.mark.django_db
def test_service_writes_populate_audit_trail(admin_user) -> None:
    site = create_site(draft=SiteDraft(name="Trail Site"), actor=admin_user)
    entry = AuditLog.objects.get(model_name="site_management.site", object_id=str(site.pk))
    assert entry.action == AuditLog.Action.CREATE
    assert entry.summary == f"Created site {site.name}"
    assert entry.after_data["name"] == "Trail Site"


@pytest.mark.django_db
def test_audit_log_selectors(admin_user, site) -> None:
    record_audit(action=AuditLog.Action.CREATE, actor=admin_user, entity=site)
    rows = list_audit_logs(model_name="site_management.site")
    assert len(rows) == 1
    assert rows[0]["user"] == "admin@whitebird.test"
    assert rows[0]["model_name"] == "site_management.site"


@pytest.mark.django_db
def test_audit_log_records_request_context(admin_user, site) -> None:
    entry = record_audit(
        action=AuditLog.Action.ARCHIVE,
        user=admin_user,
        entity=site,
        ip_address="10.0.0.1",
        request_id="req-123",
    )
    assert entry.ip_address == "10.0.0.1"
    assert entry.request_id == "req-123"


@pytest.mark.django_db
def test_legacy_changes_alias_maps_to_after_data(admin_user, site) -> None:
    entry = record_audit(
        action=AuditLog.Action.UPDATE,
        actor=admin_user,
        entity=site,
        changes={"capacity": {"from": 10, "to": 20}},
    )
    assert entry.after_data == {"capacity": {"from": 10, "to": 20}}
