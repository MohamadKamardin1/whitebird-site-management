"""Tests for the transactional domain-event outbox.

``transaction.on_commit`` callbacks only fire when a real commit happens, so
these tests opt out of pytest-django's per-test transaction wrapping
(``django_db(transaction=True)``) and assert on specific event types to stay
isolated.
"""

import pytest
from django.db import transaction

from apps.core.models import DomainEvent
from apps.core.selectors import list_pending_domain_events
from apps.core.services import publish_domain_event

EVENT = "site.created"


@pytest.mark.django_db(transaction=True)
def test_event_is_created_after_commit(admin_user) -> None:
    with transaction.atomic():
        publish_domain_event(
            event_type=EVENT,
            aggregate_type="site_management.site",
            aggregate_id=42,
            payload={"name": "Test"},
            created_by=admin_user,
        )
        assert DomainEvent.objects.filter(event_type=EVENT).count() == 0  # not yet committed

    event = DomainEvent.objects.get(event_type=EVENT, aggregate_id="42")
    assert event.event_type == EVENT
    assert event.payload == {"name": "Test"}
    assert event.schema_version == 1
    assert event.status == DomainEvent.Status.PENDING
    assert event.created_by == admin_user


@pytest.mark.django_db(transaction=True)
def test_event_is_rolled_back_with_transaction() -> None:
    with pytest.raises(RuntimeError), transaction.atomic():
        publish_domain_event(event_type="site.rolled_back", aggregate_type="site", aggregate_id=999)
        raise RuntimeError("boom")

    assert not DomainEvent.objects.filter(event_type="site.rolled_back").exists()


@pytest.mark.django_db(transaction=True)
def test_pending_events_listed_in_order() -> None:
    with transaction.atomic():
        publish_domain_event(event_type="order.one", aggregate_type="x", aggregate_id=1)
        publish_domain_event(event_type="order.two", aggregate_type="x", aggregate_id=2)
    pending = [e.event_type for e in list_pending_domain_events()]
    assert pending.index("order.one") < pending.index("order.two")


@pytest.mark.django_db(transaction=True)
def test_event_uuid_is_unique() -> None:
    with transaction.atomic():
        publish_domain_event(event_type="uuid.one", aggregate_type="x", aggregate_id=1)
        publish_domain_event(event_type="uuid.two", aggregate_type="x", aggregate_id=2)
    ids = [e.event_id for e in DomainEvent.objects.filter(event_type__startswith="uuid.")]
    assert len(ids) == 2
    assert len(set(ids)) == 2
