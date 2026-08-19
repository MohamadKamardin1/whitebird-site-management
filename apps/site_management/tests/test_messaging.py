"""Regression coverage for role-scoped retained messaging."""

from __future__ import annotations

from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
import pytest

from apps.accounts.factories import UserFactory
from apps.accounts.models import RoleCode
from apps.core.errors import ForbiddenActionError
from apps.core.files import create_file_token, decode_file_token
from apps.site_management.factories import (
    SiteFactory,
    SiteSupervisorAssignmentFactory,
    ZoneFactory,
    ZoneSupervisorAssignmentFactory,
)
from apps.site_management.messaging_services import (
    can_start_conversation,
    create_group_conversation,
    get_or_create_direct_conversation,
    mark_read,
    send_message,
    upload_attachment,
)
from apps.site_management.models import ConversationMembership, MessageAttachmentType


@pytest.mark.django_db
def test_direct_conversation_is_deduplicated_and_retains_membership() -> None:
    admin = UserFactory(role=RoleCode.SYSTEM_ADMIN)
    site_supervisor = UserFactory(role=RoleCode.SITE_SUPERVISOR)

    first = get_or_create_direct_conversation(user_a=admin, user_b=site_supervisor, actor=admin)
    repeated = get_or_create_direct_conversation(user_a=admin, user_b=site_supervisor, actor=admin)

    assert first.pk == repeated.pk
    assert first.direct_key == ":".join(str(value) for value in sorted((admin.pk, site_supervisor.pk)))
    assert list(first.memberships.values_list("user_id", flat=True)) == [admin.pk, site_supervisor.pk]


@pytest.mark.django_db
def test_zone_supervisor_can_only_start_threads_with_site_supervisors_in_own_zone() -> None:
    controlled_zone = ZoneFactory()
    other_zone = ZoneFactory()
    controlled_site = SiteFactory(zone=controlled_zone)
    other_site = SiteFactory(zone=other_zone)
    zone_supervisor = UserFactory(role=RoleCode.ZONE_SUPERVISOR)
    assigned_site_supervisor = UserFactory(role=RoleCode.SITE_SUPERVISOR)
    outsider_site_supervisor = UserFactory(role=RoleCode.SITE_SUPERVISOR)
    ZoneSupervisorAssignmentFactory(zone=controlled_zone, user=zone_supervisor)
    SiteSupervisorAssignmentFactory(site=controlled_site, user=assigned_site_supervisor)
    SiteSupervisorAssignmentFactory(site=other_site, user=outsider_site_supervisor)

    assert can_start_conversation(actor=zone_supervisor, recipient=assigned_site_supervisor) is True
    assert can_start_conversation(actor=zone_supervisor, recipient=outsider_site_supervisor) is False
    get_or_create_direct_conversation(user_a=zone_supervisor, user_b=assigned_site_supervisor, actor=zone_supervisor)
    with pytest.raises(ForbiddenActionError):
        get_or_create_direct_conversation(user_a=zone_supervisor, user_b=outsider_site_supervisor, actor=zone_supervisor)


@pytest.mark.django_db
def test_message_send_and_read_state_are_retained() -> None:
    admin = UserFactory(role=RoleCode.SYSTEM_ADMIN)
    recipient = UserFactory(role=RoleCode.STORE_MANAGER)
    conversation = get_or_create_direct_conversation(user_a=admin, user_b=recipient, actor=admin)

    message = send_message(conversation=conversation, sender=admin, body="Stock form is ready for review.")
    membership = mark_read(conversation=conversation, user=recipient)

    assert message.conversation_id == conversation.pk
    assert conversation.messages.count() == 1
    assert membership.last_read_at is not None
    assert membership.last_read_at >= message.created_at


@pytest.mark.django_db
def test_private_attachment_has_a_user_bound_signed_download_token() -> None:
    admin = UserFactory(role=RoleCode.SYSTEM_ADMIN)
    recipient = UserFactory(role=RoleCode.HR)
    conversation = get_or_create_direct_conversation(user_a=admin, user_b=recipient, actor=admin)
    message = send_message(conversation=conversation, sender=admin, body="Please review the attached form.")
    upload = SimpleUploadedFile("monthly-form.pdf", b"%PDF-1.4 private test file", content_type="application/pdf")

    attachment = upload_attachment(
        message=message,
        upload=upload,
        attachment_type=MessageAttachmentType.PDF,
        actor=admin,
    )
    token = create_file_token(
        user_id=recipient.pk,
        app_label="site_management",
        model_name="conversationmessageattachment",
        object_id=attachment.pk,
    )
    payload = decode_file_token(token)

    assert attachment.file.name
    assert attachment.uploaded_by_id == admin.pk
    assert payload is not None
    assert payload["uid"] == recipient.pk
    assert payload["oid"] == str(attachment.pk)


@pytest.mark.django_db
def test_group_creation_records_a_membership_history_row_for_each_initial_member() -> None:
    admin = UserFactory(role=RoleCode.SYSTEM_ADMIN)
    hr = UserFactory(role=RoleCode.HR)
    store_manager = UserFactory(role=RoleCode.STORE_MANAGER)

    conversation = create_group_conversation(
        title="Monthly operations handover",
        member_ids=[hr.pk, store_manager.pk],
        actor=admin,
    )
    memberships = ConversationMembership.objects.filter(conversation=conversation).order_by("user_id")

    assert conversation.conversation_type == "group"
    assert memberships.count() == 3
    assert set(memberships.values_list("user_id", flat=True)) == {admin.pk, hr.pk, store_manager.pk}
    assert all(membership.is_active and membership.left_at is None and membership.joined_at <= timezone.now() for membership in memberships)
