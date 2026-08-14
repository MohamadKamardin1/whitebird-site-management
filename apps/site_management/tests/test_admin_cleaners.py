"""Tests for the cleaner/document admin screens and idempotent service paths."""

import pytest
from django.test import Client

from apps.accounts.factories import UserFactory
from apps.accounts.models import RoleCode
from apps.site_management.cleaner_selectors import can_view_document
from apps.site_management.cleaner_services import (
    change_cleaner_status,
    register_cleaner,
    reject_cleaner_document,
    verify_cleaner_document,
)
from apps.site_management.factories import CleanerDocumentFactory, CleanerFactory
from apps.site_management.models import (
    Cleaner,
    CleanerDocument,
    CleanerDocumentStatus,
    CleanerStatus,
)


@pytest.fixture
def admin_client(db: None) -> Client:
    admin = UserFactory(role=RoleCode.SYSTEM_ADMIN, is_staff=True, is_superuser=True)
    client = Client()
    client.force_login(admin)
    return client


def _register(actor) -> Cleaner:
    return register_cleaner(
        first_name="Zainab",
        last_name="Omar",
        id_type="zanzibar_id",
        id_number="ZB12345",
        birth_date="1993-03-03",
        actor=actor,
    )


@pytest.mark.django_db
def test_cleaner_changelist_renders(admin_client: Client) -> None:
    response = admin_client.get("/admin/site_management/cleaner/")
    assert response.status_code == 200


@pytest.mark.django_db
def test_document_changelist_renders(admin_client: Client, admin_user) -> None:
    cleaner = CleanerFactory()
    CleanerDocumentFactory(cleaner=cleaner)
    response = admin_client.get("/admin/site_management/cleanerdocument/")
    assert response.status_code == 200


@pytest.mark.django_db
def test_cleaner_activate_and_deactivate_actions(admin_client: Client, admin_user) -> None:
    cleaner = _register(admin_user)
    document = CleanerDocumentFactory(cleaner=cleaner, status=CleanerDocumentStatus.VERIFIED)
    verify_cleaner_document(document=document, actor=admin_user)

    response = admin_client.post(
        "/admin/site_management/cleaner/",
        data={"action": "activate_cleaners", "_selected_action": [cleaner.pk]},
    )
    assert response.status_code == 302
    cleaner.refresh_from_db()
    assert cleaner.status == CleanerStatus.ACTIVE

    response = admin_client.post(
        "/admin/site_management/cleaner/",
        data={"action": "deactivate_cleaners", "_selected_action": [cleaner.pk]},
    )
    assert response.status_code == 302
    cleaner.refresh_from_db()
    assert cleaner.status == CleanerStatus.INACTIVE


@pytest.mark.django_db
def test_document_verify_and_reject_actions(admin_client: Client, admin_user) -> None:
    cleaner = _register(admin_user)
    document = CleanerDocumentFactory(cleaner=cleaner)
    assert document.status == CleanerDocumentStatus.PENDING

    response = admin_client.post(
        "/admin/site_management/cleanerdocument/",
        data={"action": "verify_documents", "_selected_action": [document.pk]},
    )
    assert response.status_code == 302
    document.refresh_from_db()
    assert document.status == CleanerDocumentStatus.VERIFIED

    response = admin_client.post(
        "/admin/site_management/cleanerdocument/",
        data={"action": "reject_documents", "_selected_action": [document.pk]},
    )
    assert response.status_code == 302
    document.refresh_from_db()
    assert document.status == CleanerDocumentStatus.REJECTED


@pytest.mark.django_db
def test_document_delete_guard_for_verified(admin_user) -> None:
    from apps.site_management.admin import CleanerDocumentAdmin

    cleaner = _register(admin_user)
    verified = CleanerDocumentFactory(cleaner=cleaner, status=CleanerDocumentStatus.VERIFIED)
    pending = CleanerDocumentFactory(cleaner=cleaner, status=CleanerDocumentStatus.PENDING)
    admin = CleanerDocumentAdmin(model=CleanerDocument, admin_site=None)
    assert admin.has_delete_permission(request=None, obj=verified) is False
    assert admin.has_delete_permission(request=None, obj=pending) is True


@pytest.mark.django_db
def test_document_preview_permission(admin_client: Client, admin_user) -> None:
    cleaner = _register(admin_user)
    document = CleanerDocumentFactory(cleaner=cleaner, content_type="application/pdf")
    response = admin_client.get(f"/admin/site_management/cleanerdocument/{document.pk}/preview/")
    # Staff + sensitive permission => tries to stream (file may be missing -> 404)
    assert response.status_code in (200, 404)


@pytest.mark.django_db
def test_document_preview_forbidden_for_non_staff() -> None:
    viewer = UserFactory(role=RoleCode.MANAGEMENT_VIEWER, is_staff=False)
    cleaner = CleanerFactory()
    document = CleanerDocumentFactory(cleaner=cleaner)
    client = Client()
    client.force_login(viewer)
    response = client.get(f"/admin/site_management/cleanerdocument/{document.pk}/preview/")
    assert response.status_code in (403, 302)


# --------------------------------------------------------------------------- #
# Idempotent service paths & selector branches
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
def test_status_change_to_same_status_is_noop(admin_user) -> None:
    cleaner = _register(admin_user)
    assert change_cleaner_status(cleaner=cleaner, new_status=CleanerStatus.APPLICANT, actor=admin_user) is cleaner


@pytest.mark.django_db
def test_verify_and_reject_are_idempotent(admin_user) -> None:
    cleaner = _register(admin_user)
    document = CleanerDocumentFactory(cleaner=cleaner)
    verified = verify_cleaner_document(document=document, actor=admin_user)
    assert verify_cleaner_document(document=verified, actor=admin_user) is verified
    rejected = reject_cleaner_document(document=document, actor=admin_user, reason="x")
    assert reject_cleaner_document(document=rejected, actor=admin_user, reason="y") is rejected


@pytest.mark.django_db
def test_can_view_document_for_admin(admin_user) -> None:
    cleaner = _register(admin_user)
    document = CleanerDocumentFactory(cleaner=cleaner)
    assert can_view_document(admin_user, document) is True
