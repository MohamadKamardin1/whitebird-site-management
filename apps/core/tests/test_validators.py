"""Tests for the core validators re-export module."""

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile


@pytest.mark.django_db
def test_validators_module_exports_file_helpers() -> None:
    from apps.core.validators import (
        allowed_file_extensions,
        max_upload_bytes,
        validate_file_extension,
        validate_file_size,
    )

    assert "pdf" in allowed_file_extensions()
    assert max_upload_bytes() > 0
    validate_file_extension(SimpleUploadedFile("doc.pdf", b"x"))
    validate_file_size(SimpleUploadedFile("doc.pdf", b"x"))
