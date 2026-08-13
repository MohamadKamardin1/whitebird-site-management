"""Tests for the private file storage, validators, and signed-token downloads."""

from typing import cast

import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection, models
from django.test import Client

from apps.accounts.factories import UserFactory
from apps.accounts.models import RoleCode, User
from apps.accounts.services import issue_api_token
from apps.core.files import (
    PrivateMediaStorage,
    allowed_file_extensions,
    create_file_token,
    decode_file_token,
    max_upload_bytes,
    validate_file_extension,
    validate_file_size,
)


class TestAttachment(models.Model):
    """Concrete stand-in for a private-file record (e.g. cleaner documents)."""

    file = models.FileField(storage=PrivateMediaStorage(), upload_to="test/", max_length=500)
    original_filename = models.CharField(max_length=255, blank=True, default="")
    content_type = models.CharField(max_length=127, blank=True, default="")
    size_bytes = models.PositiveBigIntegerField(default=0)

    class Meta:
        app_label = "core"
        db_table = "core_test_attachment"


def _create_table() -> None:
    if "core_test_attachment" not in connection.introspection.table_names():
        with connection.schema_editor() as schema_editor:
            schema_editor.create_model(TestAttachment)


def _authed(user: User) -> Client:
    return Client(HTTP_AUTHORIZATION=f"Bearer {issue_api_token(user=user, name='test').key}")


def _save_attachment(user: User, name: str = "scan.pdf", content: bytes = b"%PDF-1.4 test") -> TestAttachment:
    uploaded = SimpleUploadedFile(name, content, content_type="application/pdf")
    attachment = cast(
        TestAttachment,
        TestAttachment.objects.create(
            file=uploaded,
            original_filename=name,
            content_type="application/pdf",
            size_bytes=len(content),
        ),
    )
    return attachment


# --------------------------------------------------------------------------- #
# Storage & validators
# --------------------------------------------------------------------------- #


def test_private_storage_has_no_public_url() -> None:
    storage = PrivateMediaStorage()
    assert storage.location == str(__import__("django.conf", fromlist=["settings"]).settings.PRIVATE_MEDIA_ROOT)
    with pytest.raises(ValueError):
        storage.url("scan.pdf")


@pytest.mark.django_db
def test_extension_validator_whitelist() -> None:
    assert "pdf" in allowed_file_extensions()
    validate_file_extension(SimpleUploadedFile("doc.pdf", b"x"))
    validate_file_extension(SimpleUploadedFile("photo.JPG", b"x"))  # case-insensitive
    with pytest.raises(ValidationError):
        validate_file_extension(SimpleUploadedFile("evil.exe", b"x"))
    with pytest.raises(ValidationError):
        validate_file_extension(SimpleUploadedFile("noextension", b"x"))


@pytest.mark.django_db
def test_size_validator_uses_constance_limit() -> None:
    validate_file_size(SimpleUploadedFile("small.pdf", b"x"))
    oversized = SimpleUploadedFile("big.pdf", b"x" * (max_upload_bytes() + 1))
    with pytest.raises(ValidationError):
        validate_file_size(oversized)


# --------------------------------------------------------------------------- #
# Signed tokens
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
def test_file_token_round_trip(admin_user) -> None:
    token = create_file_token(user_id=admin_user.pk, app_label="core", model_name="testattachment", object_id=7)
    payload = decode_file_token(token)
    assert payload is not None
    assert payload["uid"] == admin_user.pk
    assert payload["model"] == "core.testattachment"
    assert payload["oid"] == "7"


@pytest.mark.django_db
def test_file_token_rejects_garbage() -> None:
    assert decode_file_token("not-a-token") is None
    assert decode_file_token("") is None


@pytest.mark.django_db
def test_file_token_expiry(admin_user, monkeypatch) -> None:
    from apps.core import files

    token = create_file_token(user_id=admin_user.pk, app_label="core", model_name="testattachment", object_id=1)
    assert decode_file_token(token) is not None

    monkeypatch.setattr(files, "file_token_ttl_seconds", lambda: -10)
    assert decode_file_token(token) is None


# --------------------------------------------------------------------------- #
# Signed download endpoint
# --------------------------------------------------------------------------- #


@pytest.mark.django_db(transaction=True)
def test_signed_download_streams_file(admin_user) -> None:
    _create_table()
    attachment = _save_attachment(admin_user)
    token = create_file_token(
        user_id=admin_user.pk, app_label="core", model_name="testattachment", object_id=attachment.pk
    )
    response = _authed(admin_user).get(f"/api/site-management/v1/files/signed/{token}/")
    assert response.status_code == 200
    assert b"%PDF-1.4 test" in b"".join(response.streaming_content)
    assert "attachment" in response["Content-Disposition"]
    assert "scan.pdf" in response["Content-Disposition"]


@pytest.mark.django_db(transaction=True)
def test_signed_download_audits() -> None:
    from apps.core.models import AuditLog

    _create_table()
    user = UserFactory(role=RoleCode.SYSTEM_ADMIN)
    attachment = _save_attachment(user)
    token = create_file_token(user_id=user.pk, app_label="core", model_name="testattachment", object_id=attachment.pk)
    _authed(user).get(f"/api/site-management/v1/files/signed/{token}/")
    assert (
        AuditLog.objects.filter(
            action=AuditLog.Action.FILE_DOWNLOAD, model_name="core.testattachment", object_id=str(attachment.pk)
        ).count()
        == 1
    )


@pytest.mark.django_db
def test_signed_download_rejects_invalid_token(admin_user) -> None:
    response = _authed(admin_user).get("/api/site-management/v1/files/signed/garbage/")
    assert response.status_code == 404


@pytest.mark.django_db(transaction=True)
def test_signed_download_rejects_other_user(admin_user, viewer_user) -> None:
    _create_table()
    attachment = _save_attachment(admin_user)
    token = create_file_token(
        user_id=admin_user.pk, app_label="core", model_name="testattachment", object_id=attachment.pk
    )
    response = _authed(viewer_user).get(f"/api/site-management/v1/files/signed/{token}/")
    assert response.status_code == 403


@pytest.mark.django_db(transaction=True)
def test_signed_download_missing_object(admin_user) -> None:
    _create_table()
    token = create_file_token(user_id=admin_user.pk, app_label="core", model_name="testattachment", object_id=999999)
    response = _authed(admin_user).get(f"/api/site-management/v1/files/signed/{token}/")
    assert response.status_code == 404


@pytest.mark.django_db(transaction=True)
def test_signed_download_unknown_model(admin_user) -> None:
    _create_table()
    token = create_file_token(user_id=admin_user.pk, app_label="core", model_name="nonexistentmodel", object_id=1)
    response = _authed(admin_user).get(f"/api/site-management/v1/files/signed/{token}/")
    assert response.status_code == 404
