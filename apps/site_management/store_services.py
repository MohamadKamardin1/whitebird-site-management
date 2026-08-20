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
    CompanyProduct,
    INCREASING_MOVEMENT_TYPES,
    Cleaner,
    SiteArea,
    SiteStore,
    StockMovement,
    StockMovementType,
    StockRequest,
    StockRequestApproval,
    StockRequestApprovalStage,
    StockRequestItem,
    StockRequestStatus,
    StockTransfer,
    StoreItem,
    StoreMonthlyOpening,
    StoreType,
)
from .services import notify

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
    site: Any | None,
    store_name: str,
    actor: User,
    store_type: str = StoreType.SITE,
    parent_store: SiteStore | None = None,
    location: str = "",
    managed_by: User | None = None,
) -> SiteStore:
    """Create a Super, Power, or Site Store with an optional site assignment."""
    with transaction.atomic():
        store = SiteStore(
            site=site,
            store_name=store_name,
            store_type=store_type,
            parent_store=parent_store,
            location=location,
            managed_by=managed_by,
            created_by=actor,
            updated_by=actor,
        )
        store.full_clean()
        store.save()
        scope = site.name if site else "company distribution network"
        _audit(AuditLog.Action.CREATE, store, actor, f"Created {store.get_store_type_display()} {store.store_name} at {scope}")
    return store


def update_store(
    *,
    store: SiteStore,
    actor: User,
    site: Any | None = None,
    store_name: str | None = None,
    store_type: str | None = None,
    parent_store: SiteStore | None = None,
    location: str | None = None,
    managed_by: User | None = None,
    is_active: bool | None = None,
) -> SiteStore:
    """Update store metadata or soft-deactivate it."""
    with transaction.atomic():
        before = model_data(store)
        if site is not None:
            store.site = site
        if store_name is not None:
            store.store_name = store_name
        if store_type is not None:
            store.store_type = store_type
        if parent_store is not None:
            store.parent_store = parent_store
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


def create_company_product(
    *,
    product_name: str,
    product_code: str,
    unit: str,
    current_unit_cost: Decimal,
    actor: User,
    category: str = "",
    description: str = "",
) -> CompanyProduct:
    with transaction.atomic():
        product = CompanyProduct(
            product_name=product_name,
            product_code=product_code,
            unit=unit,
            current_unit_cost=current_unit_cost,
            category=category,
            description=description,
            created_by=actor,
            updated_by=actor,
        )
        product.full_clean()
        product.save()
        _audit(AuditLog.Action.CREATE, product, actor, f"Created company product {product.product_name}")
    return product


def update_company_product(*, product: CompanyProduct, actor: User, **values: Any) -> CompanyProduct:
    with transaction.atomic():
        before = model_data(product)
        for field, value in values.items():
            if value is not None:
                setattr(product, field, value)
        product.updated_by = actor
        product.full_clean()
        product.save()
        _audit(AuditLog.Action.UPDATE, product, actor, f"Updated company product {product.product_name}", before=before)
    return product


def add_store_item(
    *,
    store: SiteStore,
    item_name: str,
    actor: User,
    product: CompanyProduct | None = None,
    item_code: str = "",
    unit: str = "piece",
    category: str = "",
    unit_cost: Decimal | None = None,
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
            product=product,
            item_name=product.product_name if product else item_name,
            item_code=product.product_code if product else item_code,
            unit=product.unit if product else unit,
            category=product.category if product else category,
            opening_stock=opening_stock,
            current_stock=opening_stock,
            unit_cost=unit_cost if unit_cost is not None else (product.current_unit_cost if product else Decimal("0")),
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
                unit_cost=item.unit_cost,
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
    product: CompanyProduct | None = None,
    item_name: str | None = None,
    item_code: str | None = None,
    unit: str | None = None,
    category: str | None = None,
    unit_cost: Decimal | None = None,
    minimum_stock_level: Decimal | None = None,
    is_active: bool | None = None,
) -> StoreItem:
    """Update item metadata/reorder point. ``current_stock`` is never set here —
    it changes only through recorded movements."""
    with transaction.atomic():
        before = model_data(item)
        if product is not None:
            item.product = product
            item.item_name = product.product_name
            item.item_code = product.product_code
            item.unit = product.unit
            item.category = product.category
        if item_name is not None:
            item.item_name = item_name
        if item_code is not None:
            item.item_code = item_code
        if unit is not None:
            item.unit = unit
        if category is not None:
            item.category = category
        if unit_cost is not None:
            item.unit_cost = unit_cost
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
        t.value
        for t in (
            StockMovementType.ISSUED,
            StockMovementType.TRANSFER_OUT,
            StockMovementType.DAMAGED,
            StockMovementType.LOST,
        )
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
    unit_cost: Decimal | None = None,
    transfer: StockTransfer | None = None,
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
            unit_cost=unit_cost if unit_cost is not None else locked.unit_cost,
            movement_date=movement_date or datetime.date.today(),
            cleaner=cleaner,
            area=area,
            transfer=transfer,
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


def transfer_stock(
    *,
    source_item: StoreItem,
    destination_item: StoreItem,
    quantity: Decimal,
    actor: User,
    transfer_date: datetime.date | None = None,
    unit_cost: Decimal | None = None,
    notes: str = "",
) -> StockTransfer:
    """Transfer a catalogue product between stores with linked debit/credit movements."""
    if source_item.store_id == destination_item.store_id:
        raise ValidationError("Source and destination stores must be different.", code="transfer_same_store")
    if source_item.product_id is None or destination_item.product_id is None:
        raise ValidationError("Transfers require company catalogue products at both stores.", code="transfer_product_required")
    if source_item.product_id != destination_item.product_id:
        raise ValidationError("Source and destination items must represent the same company product.", code="transfer_product_mismatch")
    if quantity <= 0:
        raise ValidationError("Transfer quantity must be positive.", code="transfer_quantity_invalid")
    with transaction.atomic():
        source = StoreItem.objects.select_for_update().select_related("store", "product").get(pk=source_item.pk)
        destination = StoreItem.objects.select_for_update().select_related("store", "product").get(pk=destination_item.pk)
        if source.current_stock < quantity and not config.ALLOW_NEGATIVE_STOCK:
            raise ValidationError("Insufficient stock for this transfer.", code="insufficient_stock")
        transfer = StockTransfer(
            source_store=source.store,
            destination_store=destination.store,
            product=source.product,
            source_item=source,
            destination_item=destination,
            quantity=quantity,
            unit_cost=unit_cost if unit_cost is not None else source.unit_cost,
            transfer_date=transfer_date or datetime.date.today(),
            notes=notes,
            created_by=actor,
            updated_by=actor,
        )
        transfer.full_clean()
        transfer.save()
        record_stock_movement(
            store_item=source,
            movement_type=StockMovementType.TRANSFER_OUT,
            quantity=quantity,
            actor=actor,
            movement_date=transfer.transfer_date,
            notes=f"Transfer {transfer.pk} to {destination.store.store_name}. {notes}".strip(),
            unit_cost=transfer.unit_cost,
            transfer=transfer,
        )
        record_stock_movement(
            store_item=destination,
            movement_type=StockMovementType.TRANSFER_IN,
            quantity=quantity,
            actor=actor,
            movement_date=transfer.transfer_date,
            notes=f"Transfer {transfer.pk} from {source.store.store_name}. {notes}".strip(),
            unit_cost=transfer.unit_cost,
            transfer=transfer,
        )
        _audit(
            AuditLog.Action.CREATE,
            transfer,
            actor,
            f"Transferred {quantity} {source.unit} of {source.item_name} from {source.store.store_name} to {destination.store.store_name}",
        )
    return transfer


def record_monthly_opening(
    *,
    store_item: StoreItem,
    opening_month: datetime.date,
    opening_quantity: Decimal,
    unit_cost: Decimal,
    actor: User,
) -> StoreMonthlyOpening:
    """Capture an auditable opening quantity and cost for one store item/month."""
    month = opening_month.replace(day=1)
    with transaction.atomic():
        if StoreMonthlyOpening.objects.filter(store_item=store_item, opening_month=month).exists():
            raise ValidationError("This store item already has an opening record for the selected month.", code="opening_exists")
        movement = record_stock_movement(
            store_item=store_item,
            movement_type=StockMovementType.OPENING,
            quantity=opening_quantity,
            actor=actor,
            movement_date=month,
            notes=f"Monthly opening stock for {month.isoformat()}",
            unit_cost=unit_cost,
        )
        opening = StoreMonthlyOpening(
            store_item=store_item,
            opening_month=month,
            opening_quantity=opening_quantity,
            unit_cost=unit_cost,
            opening_movement=movement,
            created_by=actor,
            updated_by=actor,
        )
        opening.full_clean()
        opening.save()
        _audit(AuditLog.Action.CREATE, opening, actor, f"Recorded monthly opening for {store_item.item_name} at {store_item.store.store_name}")
    return opening


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
            notify(
                recipient=managed_by,
                verb="low_stock",
                title=f"Low stock: {item.item_name}",
                body=f"{item.item_name} is at {item.current_stock} {item.unit} (min {item.minimum_stock_level}).",
                object_type="site_management.storeitem",
                object_id=item.pk,
                link=f"/admin/site_management/storeitem/{item.pk}/change/",
                dedup_key=f"low-stock:{item.pk}",
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


def _require_site_supervisor_request_window(actor: User) -> None:
    """Site Supervisors may prepare or submit a monthly request only through day 17."""
    if actor.role == "site_supervisor" and timezone.localdate().day > 17:
        raise ValidationError("Monthly stock requests cannot be created or changed after the 17th.", code="request_window_closed")


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
        _require_site_supervisor_request_window(actor)
        if store.site_id != site.pk:
            raise ValidationError("Store must belong to the site.", code="store_site_mismatch")
        if not items:
            raise ValidationError("A stock request needs at least one item.", code="no_items")
        requested_date = request_date or datetime.date.today()
        request = StockRequest(
            site=site,
            store=store,
            request_date=requested_date,
            request_month=requested_date.replace(day=1),
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
                quantity_left=row.get("quantity_left", 0),
                unit=store_item.unit,
                notes=row.get("notes", ""),
            )
            item.full_clean()
            item.save()
        _audit(AuditLog.Action.CREATE, request, actor, f"Created stock request {request.pk}")
    return request


def update_stock_request(
    *, request: StockRequest, actor: User, items: list[dict[str, Any]], notes: str = ""
) -> StockRequest:
    """Replace a Site Supervisor draft before the monthly request lock date."""
    _require_site_supervisor_request_window(actor)
    with transaction.atomic():
        if request.status != StockRequestStatus.DRAFT:
            raise ValidationError("Only draft requests can be changed.", code="invalid_status")
        if request.requested_by_id != actor.pk and not actor.is_system_admin:
            raise ValidationError("Only the requesting Site Supervisor can update this draft.", code="requester_required")
        if not items:
            raise ValidationError("A stock request needs at least one item.", code="no_items")
        before = model_data(request)
        request.items.all().delete()
        for row in items:
            store_item = StoreItem.objects.filter(pk=row["store_item_id"], store_id=request.store_id, is_active=True).first()
            if store_item is None:
                raise ValidationError("A selected item does not belong to this request store.", code="item_store_mismatch")
            request_item = StockRequestItem(
                request=request,
                store_item=store_item,
                requested_quantity=row["requested_quantity"],
                quantity_left=row.get("quantity_left", 0),
                unit=store_item.unit,
                notes=row.get("notes", ""),
            )
            request_item.full_clean()
            request_item.save()
        request.notes = notes
        request.updated_by = actor
        request.save(update_fields=["notes", "updated_by", "updated_at"])
        _audit(AuditLog.Action.UPDATE, request, actor, f"Updated stock request {request.pk}", before=before)
    return request


def submit_stock_request(*, request: StockRequest, actor: User) -> StockRequest:
    """Submit a draft request; emits a ``StockRequestSubmitted`` event."""
    with transaction.atomic():
        _require_site_supervisor_request_window(actor)
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
    """Record a Zone Supervisor's physical verification quantities."""
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
            item.verified_quantity = approved_qty
            item.approved_quantity = approved_qty  # legacy-compatible verified value
            item.save(update_fields=["verified_quantity", "approved_quantity", "updated_at"])
        before = model_data(request)
        request.status = StockRequestStatus.ZONE_VERIFIED
        request.notes = notes if notes.strip() else request.notes
        request.reviewed_by = actor
        request.reviewed_at = timezone.now()
        request.updated_by = actor
        request.save(update_fields=["status", "notes", "reviewed_by", "reviewed_at", "updated_by", "updated_at"])
        StockRequestApproval.objects.create(
            request=request,
            stage=StockRequestApprovalStage.ZONE_VERIFIED,
            decision_by=actor,
            notes=notes,
            created_by=actor,
            updated_by=actor,
        )
        _audit(AuditLog.Action.STATUS_CHANGE, request, actor, f"Zone verified stock request {request.pk}", before=before)
    return request


def assistant_approve_stock_request(
    *, request: StockRequest, actor: User, approved: list[dict[str, Any]], notes: str = ""
) -> StockRequest:
    """Record Assistant General Supervisor approval after a physical zone verification."""
    with transaction.atomic():
        if request.status != StockRequestStatus.ZONE_VERIFIED:
            raise ValidationError("Only zone-verified requests can be approved by an Assistant General Supervisor.", code="invalid_status")
        request_items = {item.pk: item for item in request.items.select_related("store_item")}
        for row in approved:
            item = request_items.get(row["item_id"])
            if item is None:
                raise ValidationError("A selected item does not belong to this request.", code="item_not_in_request")
            quantity = Decimal(str(row["approved_quantity"]))
            cap = item.verified_quantity if item.verified_quantity is not None else item.requested_quantity
            if quantity < 0 or quantity > cap:
                raise ValidationError("Assistant approval must be between zero and the verified quantity.", code="assistant_quantity_invalid")
            item.assistant_approved_quantity = quantity
            item.save(update_fields=["assistant_approved_quantity", "updated_at"])
        before = model_data(request)
        request.status = StockRequestStatus.ASSISTANT_APPROVED
        request.notes = notes if notes.strip() else request.notes
        request.reviewed_by = actor
        request.reviewed_at = timezone.now()
        request.updated_by = actor
        request.save(update_fields=["status", "notes", "reviewed_by", "reviewed_at", "updated_by", "updated_at"])
        StockRequestApproval.objects.create(
            request=request,
            stage=StockRequestApprovalStage.ASSISTANT_APPROVED,
            decision_by=actor,
            notes=notes,
            created_by=actor,
            updated_by=actor,
        )
        _audit(AuditLog.Action.STATUS_CHANGE, request, actor, f"Assistant approved stock request {request.pk}", before=before)
    return request


def start_hr_stock_packing(*, request: StockRequest, actor: User, notes: str = "") -> StockRequest:
    """Move an Assistant-approved request into the HR packing queue."""
    with transaction.atomic():
        if request.status != StockRequestStatus.ASSISTANT_APPROVED:
            raise ValidationError("Only Assistant-approved requests can enter HR packing.", code="invalid_status")
        before = model_data(request)
        request.status = StockRequestStatus.HR_PACKING
        request.notes = notes if notes.strip() else request.notes
        request.updated_by = actor
        request.save(update_fields=["status", "notes", "updated_by", "updated_at"])
        StockRequestApproval.objects.create(
            request=request,
            stage=StockRequestApprovalStage.HR_PACKED,
            decision_by=actor,
            notes=notes,
            created_by=actor,
            updated_by=actor,
        )
        _audit(AuditLog.Action.STATUS_CHANGE, request, actor, f"HR began packing stock request {request.pk}", before=before)
    return request


def assemble_stock_request(
    *, request: StockRequest, actor: User, packed: list[dict[str, Any]], notes: str = ""
) -> StockRequest:
    """Record the final quantities HR assembled for a request."""
    with transaction.atomic():
        if request.status != StockRequestStatus.HR_PACKING:
            raise ValidationError("Only requests in HR packing can be assembled.", code="invalid_status")
        request_items = {item.pk: item for item in request.items.all()}
        for row in packed:
            item = request_items.get(row["item_id"])
            if item is None:
                raise ValidationError("A selected item does not belong to this request.", code="item_not_in_request")
            quantity = Decimal(str(row["packed_quantity"]))
            cap = item.assistant_approved_quantity or Decimal("0")
            if quantity < 0 or quantity > cap:
                raise ValidationError("Packed quantity must be between zero and the Assistant-approved quantity.", code="packed_quantity_invalid")
            item.packed_quantity = quantity
            item.save(update_fields=["packed_quantity", "updated_at"])
        before = model_data(request)
        request.status = StockRequestStatus.ASSEMBLED
        request.notes = notes if notes.strip() else request.notes
        request.updated_by = actor
        request.save(update_fields=["status", "notes", "updated_by", "updated_at"])
        StockRequestApproval.objects.create(
            request=request,
            stage=StockRequestApprovalStage.ASSEMBLED,
            decision_by=actor,
            notes=notes,
            created_by=actor,
            updated_by=actor,
        )
        _audit(AuditLog.Action.STATUS_CHANGE, request, actor, f"HR assembled stock request {request.pk}", before=before)
    return request


def reject_stock_request(*, request: StockRequest, actor: User, reason: str) -> StockRequest:
    """Reject a submitted request."""
    with transaction.atomic():
        if request.status not in {
            StockRequestStatus.SUBMITTED,
            StockRequestStatus.ZONE_REVIEWED,
            StockRequestStatus.ZONE_VERIFIED,
            StockRequestStatus.ASSISTANT_APPROVED,
            StockRequestStatus.HR_PACKING,
        }:
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
        StockRequestApproval.objects.get_or_create(
            request=request,
            stage=StockRequestApprovalStage.REJECTED,
            defaults={"decision_by": actor, "notes": reason, "created_by": actor, "updated_by": actor},
        )
        _audit(AuditLog.Action.STATUS_CHANGE, request, actor, f"Rejected stock request {request.pk}", before=before)
    return request


def complete_stock_request(*, request: StockRequest, actor: User) -> StockRequest:
    """Close an HR-assembled request after its separately audited transfer handover."""
    with transaction.atomic():
        if request.status != StockRequestStatus.ASSEMBLED:
            raise ValidationError("Only HR-assembled requests can be completed.", code="invalid_status")
        before = model_data(request)
        request.status = StockRequestStatus.COMPLETED
        request.updated_by = actor
        request.save(update_fields=["status", "updated_by", "updated_at"])
        _audit(AuditLog.Action.STATUS_CHANGE, request, actor, f"Completed stock request {request.pk}", before=before)
    return request
