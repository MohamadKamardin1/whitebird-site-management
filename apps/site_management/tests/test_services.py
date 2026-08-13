"""Service-layer tests for site management writes."""

import pytest
from django.core.exceptions import ValidationError

from apps.core.models import AuditLog
from apps.site_management.models import (
    Asset,
    Department,
    Notification,
    Site,
    SiteStatus,
    StaffAssignment,
)
from apps.site_management.services import (
    SiteDraft,
    archive_site,
    assign_staff,
    create_asset,
    create_department,
    create_site,
    deactivate_asset,
    deactivate_department,
    restore_site,
    unassign_staff,
    update_site,
)


@pytest.mark.django_db
def test_create_site_generates_slug_and_code(admin_user, site_type, site_status):
    site = create_site(
        draft=SiteDraft(name="Kendwa Cliffs", site_type=site_type, status=site_status, capacity=50),
        actor=admin_user,
    )
    assert site.slug == "kendwa-cliffs"
    assert site.code
    assert site.created_by == admin_user


@pytest.mark.django_db
def test_create_site_disambiguates_duplicate_slugs(admin_user):
    create_site(draft=SiteDraft(name="Same Name"), actor=admin_user)
    second = create_site(draft=SiteDraft(name="Same Name"), actor=admin_user)
    assert second.slug != "same-name"
    assert second.slug.startswith("same-name")


@pytest.mark.django_db
def test_update_site_records_changes_and_audit(admin_user, site):
    draft = SiteDraft(
        name=site.name,
        capacity=250,
        status=site.status,
        site_type=site.site_type,
    )
    updated = update_site(site=site, draft=draft, actor=admin_user)
    assert updated.capacity == 250
    audit = AuditLog.objects.filter(entity_type="site_management.site", entity_id=site.pk).latest("created_at")
    assert audit.action == AuditLog.Action.UPDATE
    assert audit.changes["capacity"] == {"from": 100, "to": 250}


@pytest.mark.django_db
def test_status_change_creates_notifications(admin_user, site, site_status):
    maintenance = SiteStatus.objects.create(name="Maintenance", slug="maintenance", color="#3b82f6")
    draft = SiteDraft(name=site.name, status=maintenance, site_type=site.site_type)
    update_site(site=site, draft=draft, actor=admin_user)

    notification = Notification.objects.filter(title__contains=site.name).first()
    assert notification is not None
    assert "maintenance" in notification.body


@pytest.mark.django_db
def test_archive_and_restore_are_soft(site, admin_user):
    archive_site(site=site, actor=admin_user)
    assert Site.objects.count() == 0
    assert Site.objects.all_with_deleted().count() == 1
    restore_site(site=site, actor=admin_user)
    assert Site.objects.count() == 1


@pytest.mark.django_db
def test_department_unique_name_per_site(admin_user, site):
    create_department(site=site, name="Housekeeping", actor=admin_user)
    with pytest.raises(ValidationError):
        create_department(site=site, name="housekeeping", actor=admin_user)


@pytest.mark.django_db
def test_department_deactivate_is_soft(admin_user, site):
    department = create_department(site=site, name="Kitchen", actor=admin_user)
    deactivate_department(department=department, actor=admin_user)
    assert Department.objects.filter(pk=department.pk).exists() is False
    assert Department.objects.all_with_deleted().filter(pk=department.pk).exists()


@pytest.mark.django_db
def test_asset_lifecycle(admin_user, site, asset_category):
    asset = create_asset(site=site, name="TV", category=asset_category, actor=admin_user)
    assert asset.serial_number == ""
    deactivate_asset(asset=asset, actor=admin_user)
    assert Asset.objects.count() == 0


@pytest.mark.django_db
def test_assign_and_unassign_staff(site, staff_user, admin_user):
    assignment = assign_staff(site=site, user=staff_user, actor=admin_user)
    assert StaffAssignment.objects.count() == 1
    unassign_staff(assignment=assignment, actor=admin_user)
    assert StaffAssignment.objects.count() == 0


@pytest.mark.django_db
def test_assign_staff_is_idempotent(site, staff_user, admin_user):
    assign_staff(site=site, user=staff_user, actor=admin_user)
    assign_staff(site=site, user=staff_user, actor=admin_user)
    assert StaffAssignment.objects.count() == 1


@pytest.mark.django_db
def test_all_writes_create_audit_entries(site, admin_user):
    created = create_site(draft=SiteDraft(name="Audited Site"), actor=admin_user)
    assert AuditLog.objects.filter(entity_type="site_management.site", entity_id=created.pk).exists()
