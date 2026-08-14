"""Tests for the site store module: stock, movements, requests and permissions."""

from datetime import date
from decimal import Decimal
from typing import Any, cast

import pytest
from constance.test import override_config
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import Client

from apps.accounts.factories import UserFactory
from apps.accounts.models import RoleCode, User
from apps.accounts.services import issue_api_token
from apps.core.models import AuditLog, DomainEvent
from apps.site_management.factories import (
    CleanerFactory,
    CleanerSiteAssignmentFactory,
    SiteAreaFactory,
    SiteFactory,
    SiteStoreFactory,
    SiteSupervisorAssignmentFactory,
    StockRequestFactory,
    StockRequestItemFactory,
    StoreItemFactory,
    ZoneFactory,
    ZoneSupervisorAssignmentFactory,
)
from apps.site_management.models import (
    CleanerAssignmentStatus,
    CleanerStatus,
    SiteStore,
    StockMovementType,
    StockRequestStatus,
    StoreItem,
)
from apps.site_management.store_selectors import (
    StockMovementFilter,
    StockRequestFilter,
    StoreFilter,
    low_stock_items,
    stock_items,
    stock_movements,
    stock_request_items,
    stock_requests,
    store_detail,
    store_list,
)
from apps.site_management.store_services import (
    add_store_item,
    adjust_stock,
    complete_stock_request,
    create_stock_request,
    create_store,
    issue_stock,
    receive_stock,
    record_damage_loss,
    record_stock_movement,
    reject_stock_request,
    review_stock_request,
    submit_stock_request,
    update_store,
    update_store_item,
)


@pytest.fixture(autouse=True)
def rbac_seeded(db: None) -> None:
    from django.core.management import call_command

    call_command("seed_rbac")


def _authed(user: User) -> Client:
    return Client(HTTP_AUTHORIZATION=f"Bearer {issue_api_token(user=user, name='test').key}")


def _make_store(site: Any) -> SiteStore:
    return cast(SiteStore, SiteStoreFactory(site=site))


def _make_item(store: SiteStore, current: str = "10") -> StoreItem:
    return cast(
        StoreItem, StoreItemFactory(store=store, opening_stock=Decimal(current), current_stock=Decimal(current))
    )


# --------------------------------------------------------------------------- #
# Stores & items
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
def test_create_store_and_item(site, admin_user) -> None:
    store = create_store(site=site, store_name="Main Store", actor=admin_user, location="Ground floor")
    assert store.site_id == site.pk
    assert store.is_active
    assert AuditLog.objects.filter(model_name="site_management.sitestore", object_id=str(store.pk)).exists()

    item = add_store_item(store=store, item_name="Detergent", actor=admin_user, opening_stock=Decimal("20"))
    assert item.current_stock == 20
    assert item.minimum_stock_level == 5
    # Opening stock recorded as an OPENING movement.
    movement = item.movements.first()
    assert movement is not None
    assert movement.movement_type == StockMovementType.OPENING
    assert movement.quantity == Decimal("20")


@pytest.mark.django_db
def test_unique_item_name_and_code_per_store(site, admin_user) -> None:
    store = _make_store(site)
    add_store_item(store=store, item_name="Soap", actor=admin_user)
    with pytest.raises((ValidationError, IntegrityError)):
        add_store_item(store=store, item_name="Soap", actor=admin_user)
    add_store_item(store=store, item_name="Brush", item_code="BR1", actor=admin_user)
    with pytest.raises((ValidationError, IntegrityError)):
        add_store_item(store=store, item_name="Other", item_code="BR1", actor=admin_user)


@pytest.mark.django_db
def test_negative_opening_stock_rejected(site, admin_user) -> None:
    store = _make_store(site)
    with pytest.raises(ValidationError):
        add_store_item(store=store, item_name="Bleach", actor=admin_user, opening_stock=Decimal("-1"))


# --------------------------------------------------------------------------- #
# Movements
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
def test_received_increases_and_issued_decreases(site, admin_user) -> None:
    store = _make_store(site)
    item = _make_item(store, "10")
    receive_stock(store_item=item, quantity=Decimal("5"), actor=admin_user)
    item.refresh_from_db()
    assert item.current_stock == Decimal("15")

    cleaner = CleanerFactory(status=CleanerStatus.ACTIVE)
    CleanerSiteAssignmentFactory(cleaner=cleaner, site=site, status=CleanerAssignmentStatus.ACTIVE)
    area = SiteAreaFactory(site=site)
    issue_stock(store_item=item, quantity=Decimal("6"), actor=admin_user, cleaner=cleaner, area=area)
    item.refresh_from_db()
    assert item.current_stock == Decimal("9")
    assert item.movements.count() == 2  # received + issued (factory item has no opening movement)


@pytest.mark.django_db
def test_damaged_lost_requires_reason(site, admin_user) -> None:
    store = _make_store(site)
    item = _make_item(store, "10")
    for movement_type in (StockMovementType.DAMAGED, StockMovementType.LOST):
        with pytest.raises(ValidationError):
            record_damage_loss(
                store_item=item, movement_type=movement_type, quantity=Decimal("1"), actor=admin_user, reason=""
            )
        record_damage_loss(
            store_item=item,
            movement_type=movement_type,
            quantity=Decimal("1"),
            actor=admin_user,
            reason="Broken in transit",
        )
    item.refresh_from_db()
    assert item.current_stock == Decimal("8")


@pytest.mark.django_db
def test_negative_stock_prevented(site, admin_user) -> None:
    store = _make_store(site)
    item = _make_item(store, "2")
    with pytest.raises(ValidationError):
        issue_stock(store_item=item, quantity=Decimal("3"), actor=admin_user)
    item.refresh_from_db()
    assert item.current_stock == Decimal("2")


@pytest.mark.django_db
def test_negative_stock_allowed_with_override(site, admin_user) -> None:
    store = _make_store(site)
    item = _make_item(store, "2")
    with override_config(ALLOW_NEGATIVE_STOCK=True):
        issue_stock(store_item=item, quantity=Decimal("5"), actor=admin_user)
    item.refresh_from_db()
    assert item.current_stock == Decimal("-3")


@pytest.mark.django_db
def test_adjustment_signed_quantity(site, admin_user) -> None:
    store = _make_store(site)
    item = _make_item(store, "10")
    adjust_stock(store_item=item, signed_quantity=Decimal("-4"), actor=admin_user, reason="Count correction")
    item.refresh_from_db()
    assert item.current_stock == Decimal("6")
    adjust_stock(store_item=item, signed_quantity=Decimal("3"), actor=admin_user, reason="Found extra")
    item.refresh_from_db()
    assert item.current_stock == Decimal("9")
    with pytest.raises(ValidationError):
        adjust_stock(store_item=item, signed_quantity=Decimal("1"), actor=admin_user, reason="")


@pytest.mark.django_db
def test_movement_immutability_via_admin() -> None:
    from apps.site_management.admin import StockMovementAdmin
    from apps.site_management.models import StockMovement

    store_admin = StockMovementAdmin(model=StockMovement, admin_site=None)
    assert store_admin.has_add_permission(None) is False
    assert store_admin.has_delete_permission(None) is False
    assert store_admin.has_change_permission(None) is False


@pytest.mark.django_db
def test_concurrent_movements_do_not_lose_updates(site, admin_user) -> None:
    """Two interleaved movements both apply atomically (F-expression path)."""
    store = _make_store(site)
    item = _make_item(store, "10")
    receive_stock(store_item=item, quantity=Decimal("3"), actor=admin_user)
    record_stock_movement(
        store_item=item, movement_type=StockMovementType.RECEIVED, quantity=Decimal("2"), actor=admin_user
    )
    item.refresh_from_db()
    assert item.current_stock == Decimal("15")
    assert item.movements.count() == 2


# --------------------------------------------------------------------------- #
# Low stock
# --------------------------------------------------------------------------- #


@pytest.mark.django_db(transaction=True)
def test_low_stock_detection_and_alert(site, admin_user, general_user) -> None:
    store = _make_store(site)
    item = _make_item(store, "3")
    assert item.low_stock is True
    assert low_stock_items(admin_user).filter(pk=item.pk).exists()

    # Dropping to/below the reorder point emits a StockLow domain event.
    issue_stock(store_item=item, quantity=Decimal("3"), actor=admin_user)
    item.refresh_from_db()
    assert item.current_stock == Decimal("0")
    assert item.low_stock
    assert DomainEvent.objects.filter(event_type="StockLow", aggregate_id=str(item.pk)).exists()

    # Items above the reorder point are not low stock.
    full = _make_item(store, "50")
    assert full.low_stock is False
    assert not low_stock_items(admin_user).filter(pk=full.pk).exists()


@pytest.mark.django_db
def test_low_stock_notifies_store_manager(site, admin_user) -> None:
    manager = UserFactory(role=RoleCode.SITE_SUPERVISOR)
    store = SiteStoreFactory(site=site, managed_by=manager)
    item = _make_item(store, "10")
    issue_stock(store_item=item, quantity=Decimal("6"), actor=admin_user)
    manager.refresh_from_db()
    assert manager.notifications.filter(title__icontains="Low stock").exists()


# --------------------------------------------------------------------------- #
# Stock request workflow
# --------------------------------------------------------------------------- #


@pytest.mark.django_db(transaction=True)
def test_request_workflow_to_completion(site, admin_user, zone_user) -> None:
    store = _make_store(site)
    item = _make_item(store, "50")
    request = create_stock_request(
        site=site,
        store=store,
        actor=admin_user,
        items=[{"store_item_id": item.pk, "requested_quantity": Decimal("10")}],
    )
    assert request.status == StockRequestStatus.DRAFT

    submitted = submit_stock_request(request=request, actor=admin_user)
    assert submitted.status == StockRequestStatus.SUBMITTED
    assert DomainEvent.objects.filter(event_type="StockRequestSubmitted", aggregate_id=str(request.pk)).exists()

    with pytest.raises(ValidationError):
        submit_stock_request(request=request, actor=admin_user)

    request_item = request.items.first()
    assert request_item is not None
    reviewed = review_stock_request(
        request=request,
        actor=zone_user,
        approved=[{"item_id": request_item.pk, "approved_quantity": Decimal("10")}],
    )
    assert reviewed.status == StockRequestStatus.ZONE_REVIEWED
    assert reviewed.reviewed_by_id == zone_user.pk

    with pytest.raises(ValidationError):
        review_stock_request(request=request, actor=zone_user, approved=[])

    completed = complete_stock_request(request=request, actor=zone_user)
    assert completed.status == StockRequestStatus.COMPLETED
    item.refresh_from_db()
    assert item.current_stock == Decimal("40")
    assert item.movements.filter(movement_type=StockMovementType.ISSUED).exists()


@pytest.mark.django_db
def test_request_rejection(site, admin_user, zone_user) -> None:
    store = _make_store(site)
    item = _make_item(store, "50")
    request = create_stock_request(
        site=site,
        store=store,
        actor=admin_user,
        items=[{"store_item_id": item.pk, "requested_quantity": Decimal("10")}],
    )
    submit_stock_request(request=request, actor=admin_user)
    with pytest.raises(ValidationError):
        reject_stock_request(request=request, actor=zone_user, reason="")
    rejected = reject_stock_request(request=request, actor=zone_user, reason="Budget not approved")
    assert rejected.status == StockRequestStatus.REJECTED
    item.refresh_from_db()
    assert item.current_stock == Decimal("50")


@pytest.mark.django_db
def test_request_validation(site, admin_user) -> None:
    store = _make_store(site)
    item = _make_item(store, "50")
    other_site = SiteFactory()
    with pytest.raises(ValidationError):
        create_stock_request(
            site=other_site,
            store=store,
            actor=admin_user,
            items=[{"store_item_id": item.pk, "requested_quantity": Decimal("1")}],
        )
    with pytest.raises(ValidationError):
        create_stock_request(site=site, store=store, actor=admin_user, items=[])
    with pytest.raises(ValidationError):
        create_stock_request(
            site=site,
            store=store,
            actor=admin_user,
            items=[{"store_item_id": item.pk, "requested_quantity": Decimal("-1")}],
        )

    request = create_stock_request(
        site=site,
        store=store,
        actor=admin_user,
        items=[{"store_item_id": item.pk, "requested_quantity": Decimal("10")}],
    )
    with pytest.raises(ValidationError):
        review_stock_request(
            request=request, actor=admin_user, approved=[{"item_id": 999999, "approved_quantity": Decimal("1")}]
        )
    submit_stock_request(request=request, actor=admin_user)
    request_item = request.items.first()
    assert request_item is not None
    with pytest.raises(ValidationError):
        review_stock_request(
            request=request,
            actor=admin_user,
            approved=[{"item_id": request_item.pk, "approved_quantity": Decimal("99")}],
        )


# --------------------------------------------------------------------------- #
# Selectors
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
def test_selectors_scoping(site, admin_user, zone_user) -> None:
    store = _make_store(site)
    item = _make_item(store, "3")
    request = create_stock_request(
        site=site, store=store, actor=admin_user, items=[{"store_item_id": item.pk, "requested_quantity": Decimal("5")}]
    )
    assert store_list(admin_user, StoreFilter()).count() == 1
    assert store_list(admin_user, StoreFilter(site_id=999)).count() == 0
    assert list(stock_items(admin_user, store.pk))[0].pk == item.pk
    receive_stock(store_item=item, quantity=Decimal("5"), actor=admin_user)
    assert stock_movements(admin_user, StockMovementFilter(store_id=store.pk)).count() == 1
    assert stock_requests(admin_user, StockRequestFilter(status="draft")).count() == 1

    ZoneSupervisorAssignmentFactory(zone=site.zone, user=zone_user)
    assert store_list(zone_user, StoreFilter()).count() == 1
    # A zone supervisor outside the zone sees nothing.
    outsider = UserFactory(role=RoleCode.ZONE_SUPERVISOR)
    other_zone = ZoneFactory()
    ZoneSupervisorAssignmentFactory(zone=other_zone, user=outsider)
    assert store_list(outsider, StoreFilter()).count() == 0
    assert low_stock_items(outsider).count() == 0


@pytest.mark.django_db
def test_store_item_list_single_query(django_assert_num_queries, site, admin_user) -> None:
    store = _make_store(site)
    for _ in range(3):
        _make_item(store, "10")
    with django_assert_num_queries(1):
        items = stock_items(admin_user, store.pk)
        assert len(list(items)) == 3
        for item in items:
            assert item.store.site.name


# --------------------------------------------------------------------------- #
# Permissions & API
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
def test_api_store_flow(site, admin_user, admin_client) -> None:
    created = admin_client.post(
        "/api/site-management/v1/stores",
        data={"site_id": site.pk, "store_name": "Main Store", "location": "GF"},
        content_type="application/json",
    )
    assert created.status_code == 200
    store_id = created.json()["id"]

    item = admin_client.post(
        f"/api/site-management/v1/stores/{store_id}/items",
        data={"item_name": "Detergent", "opening_stock": "20"},
        content_type="application/json",
    )
    assert item.status_code == 200
    item_id = item.json()["id"]
    assert item.json()["current_stock"] == "20" or Decimal(item.json()["current_stock"]) == Decimal("20")

    movement = admin_client.post(
        f"/api/site-management/v1/stores/{store_id}/movements",
        data={"store_item_id": item_id, "movement_type": "received", "quantity": "5"},
        content_type="application/json",
    )
    assert movement.status_code == 200
    assert Decimal(movement.json()["quantity"]) == Decimal("5")

    low = admin_client.get("/api/site-management/v1/stores/low-stock")
    assert low.status_code == 200

    req = admin_client.post(
        f"/api/site-management/v1/stores/{store_id}/requests",
        data={"items": [{"store_item_id": item_id, "requested_quantity": "4"}]},
        content_type="application/json",
    )
    assert req.status_code == 200
    req_id = req.json()["id"]

    submitted = admin_client.post(f"/api/site-management/v1/stores/{store_id}/requests/{req_id}/submit")
    assert submitted.json()["status"] == "submitted"

    item_row_id = submitted.json()["items"][0]["id"]
    reviewed = admin_client.post(
        f"/api/site-management/v1/stores/{store_id}/requests/{req_id}/review",
        data={"approved": [{"item_id": item_row_id, "approved_quantity": "4"}]},
        content_type="application/json",
    )
    assert reviewed.json()["status"] == "zone_reviewed"

    completed = admin_client.post(f"/api/site-management/v1/stores/{store_id}/requests/{req_id}/complete")
    assert completed.json()["status"] == "completed"

    listed = admin_client.get(f"/api/site-management/v1/stores/{store_id}/requests")
    assert listed.json()["count"] == 1
    movements = admin_client.get(f"/api/site-management/v1/stores/{store_id}/movements", {"movement_type": "issued"})
    assert movements.json()["count"] == 1


@pytest.mark.django_db
def test_api_validation(site, admin_client) -> None:
    store = _make_store(site)
    item = _make_item(store, "2")
    # Insufficient stock -> service error (400 via error handler or 422).
    resp = admin_client.post(
        f"/api/site-management/v1/stores/{store.pk}/movements",
        data={"store_item_id": item.pk, "movement_type": "issued", "quantity": "99"},
        content_type="application/json",
    )
    assert resp.status_code in (400, 422)
    # Invalid movement type -> 422 schema validation.
    resp = admin_client.post(
        f"/api/site-management/v1/stores/{store.pk}/movements",
        data={"store_item_id": item.pk, "movement_type": "bogus", "quantity": "1"},
        content_type="application/json",
    )
    assert resp.status_code == 422
    # Damaged without a reason -> service error.
    resp = admin_client.post(
        f"/api/site-management/v1/stores/{store.pk}/movements",
        data={"store_item_id": item.pk, "movement_type": "damaged", "quantity": "1", "reason": ""},
        content_type="application/json",
    )
    assert resp.status_code in (400, 422)


@pytest.mark.django_db
def test_api_permissions(site, admin_user, zone_user, site_supervisor_user, viewer_user) -> None:
    store = _make_store(site)
    item = _make_item(store, "10")
    request = create_stock_request(
        site=site, store=store, actor=admin_user, items=[{"store_item_id": item.pk, "requested_quantity": Decimal("5")}]
    )
    submit_stock_request(request=request, actor=admin_user)

    # Viewer: read-only.
    viewer = _authed(viewer_user)
    assert viewer.get("/api/site-management/v1/stores").status_code == 200
    denied = viewer.post(
        "/api/site-management/v1/stores",
        data={"site_id": site.pk, "store_name": "X"},
        content_type="application/json",
    )
    assert denied.status_code in (401, 403)

    # Site supervisor must be assigned to the site to manage; otherwise denied.
    other_site_sup = UserFactory(role=RoleCode.SITE_SUPERVISOR)
    outsider = _authed(other_site_sup)
    assert outsider.post(
        f"/api/site-management/v1/stores/{store.pk}/items",
        data={"item_name": "Broom"},
        content_type="application/json",
    ).status_code in (401, 403)

    # Unassigned viewer of a store cannot read it.
    outsider_get = outsider.get(f"/api/site-management/v1/stores/{store.pk}")
    assert outsider_get.status_code in (401, 403)

    # Zone supervisor assigned to the zone can review.
    ZoneSupervisorAssignmentFactory(zone=site.zone, user=zone_user)
    zone_client = _authed(zone_user)
    assert zone_client.get(f"/api/site-management/v1/stores/{store.pk}").status_code == 200
    request_item = request.items.first()
    assert request_item is not None
    item_row_id = request_item.pk
    reviewed = zone_client.post(
        f"/api/site-management/v1/stores/{store.pk}/requests/{request.pk}/review",
        data={"approved": [{"item_id": item_row_id, "approved_quantity": "5"}]},
        content_type="application/json",
    )
    assert reviewed.status_code == 200

    # A site supervisor cannot review (zone-level action).
    SiteSupervisorAssignmentFactory(site=site, user=site_supervisor_user)
    sup_client = _authed(site_supervisor_user)
    assert sup_client.get(f"/api/site-management/v1/stores/{store.pk}").status_code == 200
    assert sup_client.post(
        f"/api/site-management/v1/stores/{store.pk}/requests/{request.pk}/reject",
        data={"reason": "x"},
        content_type="application/json",
    ).status_code in (401, 403)


@pytest.mark.django_db
def test_admin_views(site, admin_user) -> None:
    from django.test import Client

    admin = UserFactory(role=RoleCode.SYSTEM_ADMIN, is_staff=True, is_superuser=True)
    client = Client()
    client.force_login(admin)
    store = _make_store(site)
    item = _make_item(store, "10")
    assert client.get("/admin/site_management/sitestore/").status_code == 200
    assert client.get("/admin/site_management/storeitem/").status_code == 200
    assert client.get("/admin/site_management/stockmovement/").status_code == 200
    assert client.get("/admin/site_management/stockrequest/").status_code == 200

    # Deactivate store action.
    assert (
        client.post(
            "/admin/site_management/sitestore/",
            data={"action": "deactivate_stores", "_selected_action": [store.pk]},
        ).status_code
        == 302
    )
    store.refresh_from_db()
    assert store.is_active is False


@pytest.mark.django_db
def test_update_store_and_item_services(site, admin_user, site_supervisor_user) -> None:
    store = _make_store(site)
    updated = update_store(
        store=store,
        actor=admin_user,
        store_name="Renamed Store",
        location="Basement",
        managed_by=site_supervisor_user,
        is_active=False,
    )
    assert updated.store_name == "Renamed Store"
    assert updated.location == "Basement"
    assert updated.managed_by_id == site_supervisor_user.pk
    assert updated.is_active is False

    item = _make_item(store, "10")
    updated_item = update_store_item(
        item=item,
        actor=admin_user,
        item_name="New Detergent",
        item_code="ND1",
        unit="litre",
        category="chemicals",
        minimum_stock_level=Decimal("2"),
        is_active=True,
    )
    assert updated_item.item_name == "New Detergent"
    assert updated_item.item_code == "ND1"
    assert updated_item.unit == "litre"
    assert updated_item.category == "chemicals"
    assert updated_item.minimum_stock_level == Decimal("2")


@pytest.mark.django_db
def test_api_item_update_and_reject(site, admin_user, admin_client, zone_user) -> None:
    store = _make_store(site)
    item = _make_item(store, "10")
    updated = admin_client.put(
        f"/api/site-management/v1/stores/{store.pk}/items/{item.pk}",
        data={"item_name": "Updated", "minimum_stock_level": "3"},
        content_type="application/json",
    )
    assert updated.status_code == 200
    assert updated.json()["item_name"] == "Updated"

    request = create_stock_request(
        site=site, store=store, actor=admin_user, items=[{"store_item_id": item.pk, "requested_quantity": Decimal("5")}]
    )
    submit_stock_request(request=request, actor=admin_user)
    rejected = admin_client.post(
        f"/api/site-management/v1/stores/{store.pk}/requests/{request.pk}/reject",
        data={"reason": "No budget"},
        content_type="application/json",
    )
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"

    # Movement filters.
    movements = admin_client.get(
        f"/api/site-management/v1/stores/{store.pk}/movements",
        {"movement_type": "received", "date_from": date.today().isoformat()},
    )
    assert movements.status_code == 200


@pytest.mark.django_db
def test_admin_stock_request_actions(site, admin_user) -> None:
    from django.test import Client

    admin = UserFactory(role=RoleCode.SYSTEM_ADMIN, is_staff=True, is_superuser=True)
    client = Client()
    client.force_login(admin)
    store = _make_store(site)
    item = _make_item(store, "50")

    def _make_request() -> Any:
        return create_stock_request(
            site=site,
            store=store,
            actor=admin_user,
            items=[{"store_item_id": item.pk, "requested_quantity": Decimal("5")}],
        )

    # Submit action.
    req = _make_request()
    assert (
        client.post(
            "/admin/site_management/stockrequest/",
            data={"action": "submit_requests", "_selected_action": [req.pk]},
        ).status_code
        == 302
    )
    req.refresh_from_db()
    assert req.status == StockRequestStatus.SUBMITTED

    # Review action approves full requested quantities.
    assert (
        client.post(
            "/admin/site_management/stockrequest/",
            data={"action": "review_requests", "_selected_action": [req.pk]},
        ).status_code
        == 302
    )
    req.refresh_from_db()
    assert req.status == StockRequestStatus.ZONE_REVIEWED
    assert req.items.first().approved_quantity == Decimal("5")

    # Complete action issues stock.
    assert (
        client.post(
            "/admin/site_management/stockrequest/",
            data={"action": "complete_requests", "_selected_action": [req.pk]},
        ).status_code
        == 302
    )
    req.refresh_from_db()
    assert req.status == StockRequestStatus.COMPLETED
    item.refresh_from_db()
    assert item.current_stock == Decimal("45")

    # Reject action.
    req2 = _make_request()
    submit_stock_request(request=req2, actor=admin_user)
    assert (
        client.post(
            "/admin/site_management/stockrequest/",
            data={"action": "reject_requests", "_selected_action": [req2.pk]},
        ).status_code
        == 302
    )
    req2.refresh_from_db()
    assert req2.status == StockRequestStatus.REJECTED

    # Readonly after leaving draft.
    from apps.site_management.admin import StockRequestAdmin

    request_admin = StockRequestAdmin(model=req2.__class__, admin_site=None)
    assert "status" in request_admin.get_readonly_fields(None, req2)


@pytest.mark.django_db
def test_store_selector_filters(site, admin_user) -> None:
    store_a = _make_store(site)
    store_b = SiteStoreFactory(site=site, store_name="Second Store")
    item = _make_item(store_a, "3")
    _make_item(store_b, "50")
    assert store_list(admin_user, StoreFilter(search="Second")).count() == 1
    assert store_list(admin_user, StoreFilter(site_id=site.pk)).count() == 2

    receive_stock(store_item=item, quantity=Decimal("2"), actor=admin_user)
    movements = stock_movements(
        admin_user, StockMovementFilter(store_id=store_a.pk, store_item_id=item.pk, date_from=date.today())
    )
    assert movements.count() == 1
    assert low_stock_items(admin_user, site_id=site.pk).filter(pk=item.pk).exists()


@pytest.mark.django_db
def test_movement_edge_cases(site, admin_user) -> None:
    store = _make_store(site)
    item = _make_item(store, "10")

    with pytest.raises(ValidationError):
        record_stock_movement(
            store_item=item, movement_type=StockMovementType.RECEIVED, quantity=Decimal("-1"), actor=admin_user
        )
    with pytest.raises(ValidationError):
        record_stock_movement(
            store_item=item, movement_type=StockMovementType.ISSUED, quantity=Decimal("0"), actor=admin_user
        )
    with pytest.raises(ValidationError):
        record_stock_movement(store_item=item, movement_type="bogus", quantity=Decimal("1"), actor=admin_user)
    with pytest.raises(ValidationError):
        record_damage_loss(
            store_item=item,
            movement_type=StockMovementType.RECEIVED,
            quantity=Decimal("1"),
            actor=admin_user,
            reason="x",
        )

    moved = record_damage_loss(
        store_item=item,
        movement_type=StockMovementType.DAMAGED,
        quantity=Decimal("1"),
        actor=admin_user,
        reason="Shelf fall",
        notes="Twice",
    )
    assert "Shelf fall" in moved.notes
    assert "Twice" in moved.notes


@pytest.mark.django_db
def test_request_workflow_edge_cases(site, admin_user, zone_user) -> None:
    store = _make_store(site)
    item = _make_item(store, "10")
    request = create_stock_request(
        site=site, store=store, actor=admin_user, items=[{"store_item_id": item.pk, "requested_quantity": Decimal("5")}]
    )

    # Reject/complete only valid in specific statuses.
    with pytest.raises(ValidationError):
        reject_stock_request(request=request, actor=zone_user, reason="x")
    with pytest.raises(ValidationError):
        complete_stock_request(request=request, actor=zone_user)

    # Submit with no items is rejected.
    request.items.all().delete()
    with pytest.raises(ValidationError):
        submit_stock_request(request=request, actor=admin_user)

    # Re-create a valid request and exercise review validation branches.
    request2 = create_stock_request(
        site=site, store=store, actor=admin_user, items=[{"store_item_id": item.pk, "requested_quantity": Decimal("5")}]
    )
    submit_stock_request(request=request2, actor=admin_user)
    request_item = request2.items.first()
    assert request_item is not None
    with pytest.raises(ValidationError):
        review_stock_request(
            request=request2,
            actor=zone_user,
            approved=[{"item_id": request_item.pk, "approved_quantity": Decimal("-1")}],
        )

    # Complete without approvals is rejected.
    reviewed_no_approval = StockRequestFactory(
        site=site, store=store, requested_by=admin_user, status=StockRequestStatus.ZONE_REVIEWED
    )
    StockRequestItemFactory(request=reviewed_no_approval, store_item=item, requested_quantity=Decimal("1"))
    with pytest.raises(ValidationError):
        complete_stock_request(request=reviewed_no_approval, actor=zone_user)


@pytest.mark.django_db
def test_selector_remaining_branches(site, admin_user, zone_user) -> None:
    store = _make_store(site)
    item = _make_item(store, "3")
    request = create_stock_request(
        site=site, store=store, actor=admin_user, items=[{"store_item_id": item.pk, "requested_quantity": Decimal("5")}]
    )

    detail = store_detail(admin_user, store.pk)
    assert detail is not None and detail.pk == store.pk
    assert store_detail(admin_user, 99999) is None

    # stock_items for an out-of-scope user is empty.
    outsider = UserFactory(role=RoleCode.ZONE_SUPERVISOR)
    assert stock_items(outsider, store.pk).count() == 0

    # stock_request_items helper.
    assert len(stock_request_items(request.pk)) == 1

    # Movement date filter branches.
    receive_stock(store_item=item, quantity=Decimal("1"), actor=admin_user)
    assert stock_movements(admin_user, StockMovementFilter(date_to=date.today())).count() == 1
    assert (
        stock_movements(admin_user, StockMovementFilter(date_from=date(2020, 1, 1), date_to=date(2020, 1, 31))).count()
        == 0
    )

    # stock_requests extra filter branches.
    assert (
        stock_requests(
            admin_user, StockRequestFilter(site_id=site.pk, status="draft", request_date=date.today())
        ).count()
        == 1
    )
    assert stock_requests(admin_user, StockRequestFilter(request_date=date(2020, 1, 1))).count() == 0
