"""Tests for the audit log service."""

import pytest

from apps.core.models import AuditLog
from apps.core.selectors import list_audit_logs
from apps.core.services import record_audit
from apps.site_management.services import SiteDraft, create_site


@pytest.mark.django_db
def test_record_audit_with_entity(admin_user, site):
    entry = record_audit(action=AuditLog.Action.ARCHIVE, actor=admin_user, entity=site)
    assert entry.entity_type == "site_management.site"
    assert entry.entity_id == str(site.pk)
    assert entry.actor == admin_user


@pytest.mark.django_db
def test_record_audit_requires_identity(admin_user):
    with pytest.raises(ValueError):
        record_audit(action=AuditLog.Action.CREATE, actor=admin_user)


@pytest.mark.django_db
def test_service_writes_populate_audit_trail(admin_user):
    site = create_site(draft=SiteDraft(name="Trail Site"), actor=admin_user)
    entry = AuditLog.objects.get(entity_type="site_management.site", entity_id=site.pk)
    assert entry.action == AuditLog.Action.CREATE
    assert entry.summary == f"Created site {site.name}"


@pytest.mark.django_db
def test_audit_log_selectors(admin_user, site):
    record_audit(action=AuditLog.Action.CREATE, actor=admin_user, entity=site)
    rows = list_audit_logs(entity_type="site_management.site")
    assert len(rows) == 1
    assert rows[0]["actor"] == "admin"
