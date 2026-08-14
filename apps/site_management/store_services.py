"""Site store services.

Store/item maintenance, concurrency-safe stock movements and the stock
request workflow. All writes are transactional and audited; movements use
``select_for_update`` plus ``F`` expressions so concurrent updates never lose
a change; low-stock thresholds emit a ``StockLow`` domain event and an
in-platform notification; submissions emit a ``StockRequestSubmitted`` event
for the future Office Management module.
"""

from __future__ import annotations

import datetime
from decimal import Decimal
from typing import Any

from constance import config
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from apps.accounts.models import User
from apps.core.models import AuditLog
from apps.core.services import model_data, publish_domain_event, record_audit

from .models import (
    INCREASING_MOVEMENT_TYPES,
    Cleaner,
    SiteArea,
    SiteStore,
    StockMovement,
    StockMovementType,
    StockRequest,
    StockRequestItem,
    StockRequestStatus,
    StoreItem,
)
from .services import create_notification

EVENT_STOCK_REQUEST_SUBMITTED = "StockRequestSubmitted"
EVENT_STOCK_LOW = "StockLow"


def _emit(event_type: str, aggregate_type: str, aggregate_id: int, actor: User, payload: dict[str, Any]) -> None:
    publish_domain_event(
        event_type=event_type,
        aggregate_type=aggregate_type,
        aggregate_id=aggregate_id,
        payload=payload,
        created_by=actor,
    )


def _audit(
    action: AuditLog.Action,
    entity: Any,
    actor: User,
    summary: str,
    *,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
) -> None:
    record_audit(
        action=action,
        actor=actor,
        entity=entity,
        summary=summary,
        before_data=before,
        after_data=after if after is not None else model_data(entity),
    )


# --------------------------------------------------------------------------- #
# Stores & items
# --------------------------------------------------------------------------- #


def create_store(
    *,
    site: Any,
    store_name: str,
    actor: User,
    location: str = "",
    managed_by: User | None = None,
) -> SiteStore:
    """Create a store for a site (one or more stores per site allowed)."""
    with transaction.atomic():
        store = SiteStore(
            site=site,
            store_name=store_name,
            location=location,
            managed_by=managed_by,
            created_by=actor,
            updated_by=actor,
        )
        store.full_clean()
        store.save()
        _audit(AuditLog.Action.CREATE, store, actor, f"Created store {store.store_name} at {site.name}")
    return store


def update_store(
    *,
    store: SiteStore,
    actor: User,
    store_name: str | None = None,
    location: str | None = None,
    managed_by: User | None = None,
    is_active: bool | None = None,
) -> SiteStore:
    """Update store metadata or soft-deactivate it."""
    with transaction.atomic():
        before = model_data(store)
        if store_name is not None:
            store.store_name = store_name
        if location is not None:
            store.location = location
        if managed_by is not None:
            store.managed_by = managed_by
        if is_active is not None:
            store.is_active = is_active
        store.updated_by = actor
        store.full_clean()
        store.save()
        _audit(AuditLog.Action.UPDATE, store, actor, f"Updated store {store.store_name}", before=before)
    return store


def add_store_item(
    *,
    store: SiteStore,
    item_name: str,
    actor: User,
    item_code: str = "",
    unit: str = "piece",
    category: str = "",
    opening_stock: Decimal = Decimal("0"),
    minimum_stock_level: Decimal | None = None,
) -> StoreItem:
    """Add an item to a store; opening stock seeds an OPENING movement."""
    with transaction.atomic():
        if opening_stock < 0:
            raise ValidationError("Opening stock cannot be negative.", code="opening_stock_invalid")
        min_level = minimum_stock_level if minimum_stock_level is not None else Decimal(str(config.LOW_STOCK_DEFAULT))
        item = StoreItem(
            store=store,
            item_name=item_name,
            item_code=item_code,
            unit=unit,
            category=category,
            opening_stock=opening_stock,
            current_stock=opening_stock,
            minimum_stock_level=min_level,
            created_by=actor,
            updated_by=actor,
        )
        item.full_clean()
        item.save()
        if opening_stock > 0:
            StockMovement(
                store_item=item,
                movement_type=StockMovementType.OPENING,
                quantity=opening_stock,
                movement_date=datetime.date.today(),
                recorded_by=actor,
                notes="Opening stock",
                created_by=actor,
                updated_by=actor,
            ).save()
        _audit(AuditLog.Action.CREATE, item, actor, f"Added item {item.item_name} to {store.store_name}")
    return item


def update_store_item(
    *,
    item: StoreItem,
    actor: User,
    item_name: str | None = None,
    item_code: str | None = None,
    unit: str | None = None,
    category: str | None = None,
    minimum_stock_level: Decimal | None = None,
    is_active: bool | None = None,
) -> StoreItem:
    """Update item metadata/reorder point. ``current_stock`` is never set here —
    it changes only through recorded movements."""
    with transaction.atomic():
        before = model_data(item)
        if item_name is not None:
            item.item_name = item_name
        if item_code is not None:
            item.item_code = item_code
        if unit is not None:
            item.unit = unit
        if category is not None:
            item.category = category
        if minimum_stock_level is not None:
            item.minimum_stock_level = minimum_stock_level
        if is_active is not None:
            item.is_active = is_active
        item.updated_by = actor
        item.full_clean()
        item.save()
        _audit(AuditLog.Action.UPDATE, item, actor, f"Updated item {item.item_name}", before=before)
    return item


# --------------------------------------------------------------------------- #
# Stock movements (concurrency-safe)
# --------------------------------------------------------------------------- #


def _movement_delta(movement_type: str, quantity: Decimal) -> Decimal:
    """Return the signed change to apply to ``current_stock`` for a movement.

    Increasing types (OPENING/RECEIVED/RETURNED) and decreasing types
    (ISSUED/DAMAGED/LOST) take a positive magnitude; ADJUSTMENT takes a signed
    quantity (positive = increase, negative = decrease).
    """
    if movement_type in {t.value for t in INCREASING_MOVEMENT_TYPES}:
        if quantity <= 0:
            raise ValidationError("Movement quantity must be positive.", code="positive_quantity_required")
        return quantity
    if movement_type in {
        t.value for t in (StockMovementType.ISSUED, StockMovementType.DAMAGED, StockMovementType.LOST)
    }:
        if quantity <= 0:
            raise ValidationError("Movement quantity must be positive.", code="positive_quantity_required")
        return -quantity
    if movement_type == StockMovementType.ADJUSTMENT:
        return quantity
    raise ValidationError("Unknown movement type.", code="invalid_movement_type")


def record_stock_movement(
    *,
    store_item: StoreItem,
    movement_type: str,
    quantity: Decimal,
    actor: User,
    movement_date: datetime.date | None = None,
    cleaner: Cleaner | None = None,
    area: SiteArea | None = None,
    notes: str = "",
) -> StockMovement:
    """Record a stock movement and atomically update ``current_stock``.

    The store item row is locked (``select_for_update``) and updated with an
    ``F`` expression so concurrent movements cannot race. Negative stock is
    rejected unless the ``ALLOW_NEGATIVE_STOCK`` override is enabled.
    """
    if quantity == 0:
        raise ValidationError("Quantity cannot be zero.", code="zero_quantity")
    with transaction.atomic():
        locked = StoreItem.objects.select_for_update().get(pk=store_item.pk)
        delta = _movement_delta(movement_type, quantity)
        new_stock = locked.current_stock + delta
        if new_stock < 0 and not config.ALLOW_NEGATIVE_STOCK:
            raise ValidationError(
                "Insufficient stock: this movement would make stock negative.",
                code="insufficient_stock",
            )
        movement = StockMovement(
            store_item=locked,
            movement_type=movement_type,
            quantity=quantity if movement_type == StockMovementType.ADJUSTMENT else abs(delta),
            movement_date=movement_date or datetime.date.today(),
            cleaner=cleaner,
            area=area,
            notes=notes,
            recorded_by=actor,
            created_by=actor,
            updated_by=actor,
        )
        movement.full_clean()
        movement.save()
        StoreItem.objects.filter(pk=locked.pk).update(current_stock=F("current_stock") + delta)
        locked.refresh_from_db()
        _audit(
            AuditLog.Action.CREATE,
            movement,
            actor,
            f"{movement_type} {abs(delta)} x {locked.item_name} ({locked.store.store_name})",
        )
        _maybe_low_stock_alert(locked, actor)
    return movement


def _maybe_low_stock_alert(item: StoreItem, actor: User) -> None:
    """Emit a low-stock event + notification when an item drops to its reorder point."""
    if item.low_stock:
        _emit(
            EVENT_STOCK_LOW,
            "site_management.storeitem",
            item.pk,
            actor,
            {
                "store_item_id": item.pk,
                "store_id": item.store_id,
                "site_id": item.store.site_id,
                "current_stock": str(item.current_stock),
                "minimum_stock_level": str(item.minimum_stock_level),
            },
        )
        store = item.store
        managed_by = store.managed_by
        if config.ENABLE_NOTIFICATIONS and managed_by is not None:
            create_notification(
                recipient=managed_by,
                title=f"Low stock: {item.item_name}",
                body=f"{item.item_name} is at {item.current_stock} {item.unit} (min {item.minimum_stock_level}).",
                entity_type="storeitem",
                entity_id=str(item.pk),
            )


def receive_stock(
    *,
    store_item: StoreItem,
    quantity: Decimal,
    actor: User,
    movement_date: datetime.date | None = None,
    notes: str = "",
) -> StockMovement:
    return record_stock_movement(
        store_item=store_item,
        movement_type=StockMovementType.RECEIVED,
        quantity=quantity,
        actor=actor,
        movement_date=movement_date,
        notes=notes,
    )


def issue_stock(
    *,
    store_item: StoreItem,
    quantity: Decimal,
    actor: User,
    movement_date: datetime.date | None = None,
    cleaner: Cleaner | None = None,
    area: SiteArea | None = None,
    notes: str = "",
) -> StockMovement:
    return record_stock_movement(
        store_item=store_item,
        movement_type=StockMovementType.ISSUED,
        quantity=quantity,
        actor=actor,
        movement_date=movement_date,
        cleaner=cleaner,
        area=area,
        notes=notes,
    )


def record_damage_loss(
    *,
    store_item: StoreItem,
    movement_type: str,
    quantity: Decimal,
    actor: User,
    reason: str,
    movement_date: datetime.date | None = None,
    notes: str = "",
) -> StockMovement:
    """Record DAMAGED/LOST stock; a reason is required."""
    if movement_type not in {StockMovementType.DAMAGED, StockMovementType.LOST}:
        raise ValidationError("record_damage_loss only accepts DAMAGED or LOST.", code="invalid_movement_type")
    if not reason.strip():
        raise ValidationError("A reason is required for damage/loss.", code="reason_required")
    combined = reason.strip()
    if notes.strip():
        combined = f"{notes.strip()}\n{combined}"
    return record_stock_movement(
        store_item=store_item,
        movement_type=movement_type,
        quantity=quantity,
        actor=actor,
        movement_date=movement_date,
        notes=combined,
    )


def adjust_stock(
    *,
    store_item: StoreItem,
    signed_quantity: Decimal,
    actor: User,
    reason: str,
    movement_date: datetime.date | None = None,
) -> StockMovement:
    """Apply a signed stock adjustment (positive = increase, negative = decrease)."""
    if not reason.strip():
        raise ValidationError("A reason is required for an adjustment.", code="reason_required")
    return record_stock_movement(
        store_item=store_item,
        movement_type=StockMovementType.ADJUSTMENT,
        quantity=signed_quantity,
        actor=actor,
        movement_date=movement_date,
        notes=reason,
    )


# --------------------------------------------------------------------------- #
# Stock requests
# --------------------------------------------------------------------------- #


def create_stock_request(
    *,
    site: Any,
    store: SiteStore,
    actor: User,
    items: list[dict[str, Any]],
    request_date: datetime.date | None = None,
    notes: str = "",
) -> StockRequest:
    """Create a DRAFT stock request with its requested items."""
    with transaction.atomic():
        if store.site_id != site.pk:
            raise ValidationError("Store must belong to the site.", code="store_site_mismatch")
        if not items:
            raise ValidationError("A stock request needs at least one item.", code="no_items")
        request = StockRequest(
            site=site,
            store=store,
            request_date=request_date or datetime.date.today(),
            requested_by=actor,
            status=StockRequestStatus.DRAFT,
            notes=notes,
            created_by=actor,
            updated_by=actor,
        )
        request.full_clean()
        request.save()
        for row in items:
            store_item = StoreItem.objects.filter(pk=row["store_item_id"], store_id=store.pk).first()
            if store_item is None:
                raise ValidationError(
                    f"Item {row['store_item_id']} does not belong to this store.", code="item_store_mismatch"
                )
            item = StockRequestItem(
                request=request,
                store_item=store_item,
                requested_quantity=row["requested_quantity"],
                notes=row.get("notes", ""),
            )
            item.full_clean()
            item.save()
        _audit(AuditLog.Action.CREATE, request, actor, f"Created stock request {request.pk}")
    return request


def submit_stock_request(*, request: StockRequest, actor: User) -> StockRequest:
    """Submit a draft request; emits a ``StockRequestSubmitted`` event."""
    with transaction.atomic():
        if request.status != StockRequestStatus.DRAFT:
            raise ValidationError("Only draft requests can be submitted.", code="invalid_status")
        if not request.items.exists():
            raise ValidationError("Cannot submit a request without items.", code="no_items")
        before = model_data(request)
        request.status = StockRequestStatus.SUBMITTED
        request.updated_by = actor
        request.save(update_fields=["status", "updated_by", "updated_at"])
        _audit(AuditLog.Action.STATUS_CHANGE, request, actor, f"Submitted stock request {request.pk}", before=before)
        _emit(
            EVENT_STOCK_REQUEST_SUBMITTED,
            "site_management.stockrequest",
            request.pk,
            actor,
            {
                "request_id": request.pk,
                "store_id": request.store_id,
                "site_id": request.site_id,
                "item_count": request.items.count(),
            },
        )
    return request


def review_stock_request(
    *,
    request: StockRequest,
    actor: User,
    approved: list[dict[str, Any]],
    notes: str = "",
) -> StockRequest:
    """Review a submitted request: approve quantities per item → ZONE_REVIEWED."""
    with transaction.atomic():
        if request.status != StockRequestStatus.SUBMITTED:
            raise ValidationError("Only submitted requests can be reviewed.", code="invalid_status")
        request_items = {item.pk: item for item in request.items.select_related("store_item")}
        for row in approved:
            item = request_items.get(row["item_id"])
            if item is None:
                raise ValidationError(
                    f"Item {row['item_id']} does not belong to this request.", code="item_not_in_request"
                )
            approved_qty = Decimal(str(row["approved_quantity"]))
            if approved_qty < 0:
                raise ValidationError("Approved quantity cannot be negative.", code="approved_quantity_invalid")
            if approved_qty > item.requested_quantity:
                raise ValidationError(
                    "Approved quantity cannot exceed the requested quantity.", code="approved_exceeds_requested"
                )
            item.approved_quantity = approved_qty
            item.save(update_fields=["approved_quantity", "updated_at"])
        before = model_data(request)
        request.status = StockRequestStatus.ZONE_REVIEWED
        request.notes = notes if notes.strip() else request.notes
        request.reviewed_by = actor
        request.reviewed_at = timezone.now()
        request.updated_by = actor
        request.save(update_fields=["status", "notes", "reviewed_by", "reviewed_at", "updated_by", "updated_at"])
        _audit(
            AuditLog.Action.STATUS_CHANGE, request, actor, f"Zone reviewed stock request {request.pk}", before=before
        )
    return request


def reject_stock_request(*, request: StockRequest, actor: User, reason: str) -> StockRequest:
    """Reject a submitted request."""
    with transaction.atomic():
        if request.status not in {StockRequestStatus.SUBMITTED, StockRequestStatus.ZONE_REVIEWED}:
            raise ValidationError("This request cannot be rejected.", code="invalid_status")
        if not reason.strip():
            raise ValidationError("A reason is required to reject a request.", code="reason_required")
        before = model_data(request)
        request.status = StockRequestStatus.REJECTED
        request.notes = (request.notes + "\n" if request.notes else "") + f"Rejected: {reason}"
        request.reviewed_by = actor
        request.reviewed_at = timezone.now()
        request.updated_by = actor
        request.save(update_fields=["status", "notes", "reviewed_by", "reviewed_at", "updated_by", "updated_at"])
        _audit(AuditLog.Action.STATUS_CHANGE, request, actor, f"Rejected stock request {request.pk}", before=before)
    return request


def complete_stock_request(*, request: StockRequest, actor: User) -> StockRequest:
    """Complete a reviewed request by issuing approved quantities against the store."""
    with transaction.atomic():
        if request.status != StockRequestStatus.ZONE_REVIEWED:
            raise ValidationError("Only zone-reviewed requests can be completed.", code="invalid_status")
        issued = 0
        for item in request.items.all():
            if item.approved_quantity is None:
                continue
            record_stock_movement(
                store_item=item.store_item,
                movement_type=StockMovementType.ISSUED,
                quantity=item.approved_quantity,
                actor=actor,
                notes=f"Stock request {request.pk}",
            )
            issued += 1
        if issued == 0:
            raise ValidationError("No approved quantities to complete.", code="no_approved_items")
        before = model_data(request)
        request.status = StockRequestStatus.COMPLETED
        request.updated_by = actor
        request.save(update_fields=["status", "updated_by", "updated_at"])
        _audit(AuditLog.Action.STATUS_CHANGE, request, actor, f"Completed stock request {request.pk}", before=before)
    return request
