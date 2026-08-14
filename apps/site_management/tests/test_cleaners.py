"""Tests for the cleaner registry and secure document handling."""

from datetime import date, timedelta

import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError
from django.test import Client

from apps.accounts.factories import UserFactory
from apps.accounts.models import RoleCode, User
from apps.accounts.services import issue_api_token
from apps.core.models import AuditLog, DomainEvent
from apps.site_management.cleaner_selectors import (
    can_view_document,
    can_view_full_cleaner_profile,
    mask_value,
)
from apps.site_management.cleaner_services import (
    activate_cleaner_if_eligible,
    change_cleaner_status,
    deactivate_cleaner,
    register_cleaner,
    reject_cleaner_document,
    update_cleaner,
    upload_cleaner_document,
    verify_cleaner_document,
)
from apps.site_management.factories import CleanerDocumentFactory, CleanerFactory
from apps.site_management.models import (
    Cleaner,
    CleanerDocumentStatus,
    CleanerDocumentType,
    CleanerStatus,
)


@pytest.fixture(autouse=True)
def rbac_seeded(db: None) -> None:
    from django.core.management import call_command

    call_command("seed_rbac")


def _authed(user: User) -> Client:
    return Client(HTTP_AUTHORIZATION=f"Bearer {issue_api_token(user=user, name='test').key}")


def _cleaner_payload(**overrides) -> dict:
    payload = {
        "first_name": "Amina",
        "last_name": "Ali",
        "id_type": "nida",
        "id_number": "nida12345",
        "birth_date": "1995-05-10",
        "gender": "female",
    }
    payload.update(overrides)
    return payload


# --------------------------------------------------------------------------- #
# Registration & validation
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
def test_register_cleaner_and_normalize_id(admin_user) -> None:
    cleaner = register_cleaner(**_cleaner_payload(id_number="  nida12345  "), actor=admin_user)
    assert cleaner.status == CleanerStatus.APPLICANT
    assert cleaner.id_number == "NIDA12345"


@pytest.mark.django_db
def test_duplicate_id_prevention(admin_user) -> None:
    register_cleaner(**_cleaner_payload(), actor=admin_user)
    with pytest.raises(IntegrityError):
        register_cleaner(**_cleaner_payload(), actor=admin_user)


@pytest.mark.django_db
def test_birth_date_cannot_be_future(admin_user) -> None:
    future = (date.today() + timedelta(days=1)).isoformat()
    with pytest.raises(ValidationError):
        register_cleaner(**_cleaner_payload(birth_date=future), actor=admin_user)


@pytest.mark.django_db
def test_minimum_age_enforced(admin_user) -> None:
    too_young = (date.today() - timedelta(days=365 * 10)).isoformat()
    with pytest.raises(ValidationError):
        register_cleaner(**_cleaner_payload(birth_date=too_young), actor=admin_user)


@pytest.mark.django_db
def test_invalid_phone_rejected(admin_user) -> None:
    with pytest.raises(ValidationError):
        register_cleaner(**_cleaner_payload(phone_number="not-a-phone"), actor=admin_user)


@pytest.mark.django_db
def test_update_cleaner_and_audit(admin_user) -> None:
    cleaner = register_cleaner(**_cleaner_payload(), actor=admin_user)
    updated = update_cleaner(cleaner=cleaner, actor=admin_user, living_location="Nungwi")
    assert updated.living_location == "Nungwi"
    assert AuditLog.objects.filter(model_name="site_management.cleaner", object_id=str(cleaner.pk)).exists()


# --------------------------------------------------------------------------- #
# Status transitions
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
def test_invalid_transition_rejected(admin_user) -> None:
    cleaner = register_cleaner(**_cleaner_payload(), actor=admin_user)
    with pytest.raises(ValidationError):
        change_cleaner_status(cleaner=cleaner, new_status=CleanerStatus.ACTIVE, actor=admin_user)


@pytest.mark.django_db
def test_cannot_activate_without_verified_id(admin_user) -> None:
    cleaner = register_cleaner(**_cleaner_payload(), actor=admin_user)
    change_cleaner_status(cleaner=cleaner, new_status=CleanerStatus.TRAINEE, actor=admin_user)
    with pytest.raises(ValidationError):
        change_cleaner_status(cleaner=cleaner, new_status=CleanerStatus.ACTIVE, actor=admin_user)
    with pytest.raises(ValidationError):
        activate_cleaner_if_eligible(cleaner=cleaner, actor=admin_user)


@pytest.mark.django_db
def test_activate_with_verified_id(admin_user) -> None:
    cleaner = register_cleaner(**_cleaner_payload(), actor=admin_user)
    change_cleaner_status(cleaner=cleaner, new_status=CleanerStatus.TRAINEE, actor=admin_user)
    document = upload_cleaner_document(
        cleaner=cleaner,
        uploaded_file=SimpleUploadedFile("id.pdf", b"%PDF-1.4 id", content_type="application/pdf"),
        document_type=CleanerDocumentType.NIDA,
        actor=admin_user,
    )
    verify_cleaner_document(document=document, actor=admin_user)
    activated = activate_cleaner_if_eligible(cleaner=cleaner, actor=admin_user)
    assert activated.status == CleanerStatus.ACTIVE


@pytest.mark.django_db
def test_deactivate_from_any_status(admin_user) -> None:
    cleaner = register_cleaner(**_cleaner_payload(), actor=admin_user)
    deactivated = deactivate_cleaner(cleaner=cleaner, actor=admin_user)
    assert deactivated.status == CleanerStatus.INACTIVE


@pytest.mark.django_db(transaction=True)
def test_domain_events_emitted_on_commit(admin_user) -> None:
    cleaner = register_cleaner(**_cleaner_payload(), actor=admin_user)
    deactivate_cleaner(cleaner=cleaner, actor=admin_user)
    events = list(DomainEvent.objects.filter(aggregate_type="site_management.cleaner", aggregate_id=str(cleaner.pk)))
    types = {e.event_type for e in events}
    assert "CleanerRegistered" in types
    assert "CleanerDeactivated" in types


# --------------------------------------------------------------------------- #
# Documents
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
def test_upload_document_validates_extension(admin_user) -> None:
    cleaner = register_cleaner(**_cleaner_payload(), actor=admin_user)
    with pytest.raises(ValidationError):
        upload_cleaner_document(
            cleaner=cleaner,
            uploaded_file=SimpleUploadedFile("evil.exe", b"x", content_type="application/octet-stream"),
            document_type=CleanerDocumentType.OTHER,
            actor=admin_user,
        )


@pytest.mark.django_db
def test_duplicate_document_hash_rejected(admin_user) -> None:
    cleaner = register_cleaner(**_cleaner_payload(), actor=admin_user)
    content = b"%PDF-1.4 same content"
    upload_cleaner_document(
        cleaner=cleaner,
        uploaded_file=SimpleUploadedFile("a.pdf", content, content_type="application/pdf"),
        document_type=CleanerDocumentType.OTHER,
        actor=admin_user,
    )
    with pytest.raises(ValidationError):
        upload_cleaner_document(
            cleaner=cleaner,
            uploaded_file=SimpleUploadedFile("b.pdf", content, content_type="application/pdf"),
            document_type=CleanerDocumentType.OTHER,
            actor=admin_user,
        )


@pytest.mark.django_db
def test_verify_and_reject_document(admin_user) -> None:
    cleaner = register_cleaner(**_cleaner_payload(), actor=admin_user)
    document = upload_cleaner_document(
        cleaner=cleaner,
        uploaded_file=SimpleUploadedFile("id.pdf", b"%PDF-1.4 id", content_type="application/pdf"),
        document_type=CleanerDocumentType.NIDA,
        actor=admin_user,
    )
    assert document.status == CleanerDocumentStatus.PENDING
    verified = verify_cleaner_document(document=document, actor=admin_user)
    assert verified.status == CleanerDocumentStatus.VERIFIED
    assert verified.verified_by == admin_user
    rejected = reject_cleaner_document(document=verified, actor=admin_user, reason="Blurry")
    assert rejected.status == CleanerDocumentStatus.REJECTED
    assert rejected.rejection_reason == "Blurry"


# --------------------------------------------------------------------------- #
# Privacy: masking & permissions
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
def test_mask_value() -> None:
    assert mask_value("NIDA12345") == "*****2345"
    assert mask_value("") == ""
    assert mask_value("abc") == "***"


@pytest.mark.django_db
def test_sensitive_permission_gating(admin_user, general_user, zone_user) -> None:
    cleaner = register_cleaner(**_cleaner_payload(), actor=admin_user)
    assert can_view_full_cleaner_profile(admin_user, cleaner) is True
    assert can_view_full_cleaner_profile(general_user, cleaner) is True  # general holds sensitive perm
    assert can_view_full_cleaner_profile(zone_user, cleaner) is False


@pytest.mark.django_db
def test_document_view_requires_sensitive_permission(admin_user, zone_user) -> None:
    cleaner = register_cleaner(**_cleaner_payload(), actor=admin_user)
    document = CleanerDocumentFactory(cleaner=cleaner)
    assert can_view_document(zone_user, document) is False


# --------------------------------------------------------------------------- #
# API
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
def test_cleaners_api_list_masks_pii(admin_client, admin_user, zone_client, zone_user) -> None:
    register_cleaner(**_cleaner_payload(), actor=admin_user)
    response = zone_client.get("/api/site-management/v1/cleaners")
    assert response.status_code == 200
    result = response.json()["results"][0]
    assert result["id_number"] == mask_value("NIDA12345")
    assert result["id_number"] != "NIDA12345"

    admin_response = admin_client.get("/api/site-management/v1/cleaners")
    assert admin_response.json()["results"][0]["id_number"] == "NIDA12345"


@pytest.mark.django_db
def test_cleaners_api_write_permissions(admin_client, general_client, viewer_user) -> None:
    viewer = UserFactory(role=RoleCode.MANAGEMENT_VIEWER)
    denied = _authed(viewer).post(
        "/api/site-management/v1/cleaners", data=_cleaner_payload(), content_type="application/json"
    )
    assert denied.status_code in (401, 403)
    assert (
        general_client.post(
            "/api/site-management/v1/cleaners", data=_cleaner_payload(), content_type="application/json"
        ).status_code
        == 200
    )


@pytest.mark.django_db
def test_cleaner_status_api(admin_client, admin_user) -> None:
    created = admin_client.post(
        "/api/site-management/v1/cleaners", data=_cleaner_payload(), content_type="application/json"
    )
    cleaner_id = created.json()["id"]
    status = admin_client.patch(
        f"/api/site-management/v1/cleaners/{cleaner_id}/status",
        data={"status": "inactive"},
        content_type="application/json",
    )
    assert status.status_code == 200
    assert status.json()["status"] == "inactive"


@pytest.mark.django_db
def test_document_upload_and_download_url_api(admin_client, admin_user) -> None:
    created = admin_client.post(
        "/api/site-management/v1/cleaners", data=_cleaner_payload(), content_type="application/json"
    )
    cleaner_id = created.json()["id"]
    uploaded = admin_client.post(
        f"/api/site-management/v1/cleaners/{cleaner_id}/documents",
        data={
            "document_type": "nida",
            "file": SimpleUploadedFile("id.pdf", b"%PDF-1.4 id", content_type="application/pdf"),
        },
    )
    assert uploaded.status_code == 200
    document_id = uploaded.json()["id"]

    verified = admin_client.post(f"/api/site-management/v1/cleaners/{cleaner_id}/documents/{document_id}/verify")
    assert verified.status_code == 200
    assert verified.json()["status"] == "verified"

    url_resp = admin_client.get(f"/api/site-management/v1/cleaners/{cleaner_id}/documents/{document_id}/download-url")
    assert url_resp.status_code == 200
    download_url = url_resp.json()["download_url"]
    assert download_url.startswith("/api/site-management/v1/files/signed/")
    assert download_url.endswith("/")


@pytest.mark.django_db
def test_signed_download_streams_and_audits(admin_user, general_user) -> None:
    cleaner = register_cleaner(**_cleaner_payload(), actor=admin_user)
    document = upload_cleaner_document(
        cleaner=cleaner,
        uploaded_file=SimpleUploadedFile("id.pdf", b"%PDF-1.4 SECRET", content_type="application/pdf"),
        document_type=CleanerDocumentType.NIDA,
        actor=admin_user,
    )
    from apps.core.files import create_file_token, decode_file_token

    token = create_file_token(
        user_id=general_user.pk, app_label="site_management", model_name="cleanerdocument", object_id=document.pk
    )
    assert decode_file_token(token) is not None
    response = _authed(general_user).get(f"/api/site-management/v1/files/signed/{token}/")
    assert response.status_code == 200
    assert b"%PDF-1.4 SECRET" in b"".join(response.streaming_content)
    assert AuditLog.objects.filter(action=AuditLog.Action.FILE_DOWNLOAD).exists()


@pytest.mark.django_db
def test_signed_download_rejects_other_user(admin_user, general_user, zone_user) -> None:
    cleaner = register_cleaner(**_cleaner_payload(), actor=admin_user)
    document = CleanerDocumentFactory(cleaner=cleaner)
    from apps.core.files import create_file_token

    token = create_file_token(
        user_id=general_user.pk, app_label="site_management", model_name="cleanerdocument", object_id=document.pk
    )
    response = _authed(zone_user).get(f"/api/site-management/v1/files/signed/{token}/")
    assert response.status_code == 403


@pytest.mark.django_db
def test_download_url_requires_sensitive_permission(zone_user, admin_user) -> None:
    cleaner = register_cleaner(**_cleaner_payload(), actor=admin_user)
    document = CleanerDocumentFactory(cleaner=cleaner)
    response = _authed(zone_user).get(
        f"/api/site-management/v1/cleaners/{cleaner.pk}/documents/{document.pk}/download-url"
    )
    assert response.status_code == 403


@pytest.mark.django_db
def test_expired_token_denied(admin_user, monkeypatch) -> None:
    cleaner = register_cleaner(**_cleaner_payload(), actor=admin_user)
    document = CleanerDocumentFactory(cleaner=cleaner)
    from apps.core import files

    token = files.create_file_token(
        user_id=admin_user.pk, app_label="site_management", model_name="cleanerdocument", object_id=document.pk
    )
    monkeypatch.setattr(files, "file_token_ttl_seconds", lambda: -10)
    assert files.decode_file_token(token) is None


@pytest.mark.django_db
def test_document_review_permissions(zone_client, zone_user, admin_user) -> None:
    cleaner = register_cleaner(**_cleaner_payload(), actor=admin_user)
    document = CleanerDocumentFactory(cleaner=cleaner)
    response = zone_client.post(f"/api/site-management/v1/cleaners/{cleaner.pk}/documents/{document.pk}/verify")
    assert response.status_code == 403


@pytest.mark.django_db
def test_cleaner_admin_delete_guard() -> None:
    from apps.site_management.admin import CleanerAdmin

    cleaner = CleanerFactory()
    CleanerDocumentFactory(cleaner=cleaner)
    admin = CleanerAdmin(model=Cleaner, admin_site=None)
    assert admin.has_delete_permission(request=None, obj=cleaner) is False
    fresh = CleanerFactory()
    assert admin.has_delete_permission(request=None, obj=fresh) is True
