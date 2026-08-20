"""Site store read selectors (role-scoped, query-efficient)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from django.db.models import Count, F, Q, QuerySet

from apps.accounts.models import User

from .models import SiteStore, StockMovement, StockRequest, StockRequestItem, StoreItem
from .scoping import visible_sites


@dataclass(frozen=True)
class StoreFilter:
    site_id: int | None = None
    search: str | None = None


@dataclass(frozen=True)
class StockMovementFilter:
    store_id: int | None = None
    store_item_id: int | None = None
    movement_type: str | None = None
    date_from: date | None = None
    date_to: date | None = None


@dataclass(frozen=True)
class StockRequestFilter:
    store_id: int | None = None
    status: str | None = None
    site_id: int | None = None
    request_date: date | None = None


def store_list(user: User, spec: StoreFilter) -> QuerySet[SiteStore]:
    """Stores visible to the user, annotated with item counts."""
    qs: QuerySet[SiteStore] = SiteStore.objects.select_related("site", "managed_by").annotate(
        annotated_item_count=Count("items", distinct=True)
    )
    if not (user.is_system_admin or user.is_store_manager or user.is_hr):
        qs = qs.filter(site__in=visible_sites(user))
    if spec.site_id:
        qs = qs.filter(site_id=spec.site_id)
    if spec.search:
        qs = qs.filter(
            Q(store_name__icontains=spec.search)
            | Q(location__icontains=spec.search)
            | Q(site__name__icontains=spec.search)
        )
    return qs


def store_detail(user: User, store_id: int) -> SiteStore | None:
    """A single store with item counts, scoped to the user."""
    return store_list(user, StoreFilter()).filter(pk=store_id).first()


def stock_items(user: User, store_id: int) -> QuerySet[StoreItem]:
    """Active items of a store in the user's scope (single query)."""
    qs: QuerySet[StoreItem] = StoreItem.objects.select_related("store", "store__site").filter(store_id=store_id)
    if not (user.is_system_admin or user.is_store_manager or user.is_hr):
        qs = qs.filter(store__site__in=visible_sites(user))
    return qs.order_by("item_name")


def stock_movements(user: User, spec: StockMovementFilter) -> QuerySet[StockMovement]:
    """Stock movements in the user's scope, with filters and one query."""
    qs: QuerySet[StockMovement] = StockMovement.objects.select_related(
        "store_item", "store_item__store", "store_item__store__site", "cleaner", "area", "recorded_by"
    )
    if not (user.is_system_admin or user.is_store_manager or user.is_hr):
        qs = qs.filter(store_item__store__site__in=visible_sites(user))
    if spec.store_id:
        qs = qs.filter(store_item__store_id=spec.store_id)
    if spec.store_item_id:
        qs = qs.filter(store_item_id=spec.store_item_id)
    if spec.movement_type:
        qs = qs.filter(movement_type=spec.movement_type)
    if spec.date_from:
        qs = qs.filter(movement_date__gte=spec.date_from)
    if spec.date_to:
        qs = qs.filter(movement_date__lte=spec.date_to)
    return qs


def low_stock_items(user: User, site_id: int | None = None) -> QuerySet[StoreItem]:
    """Items at or below their reorder point in the user's scope."""
    qs: QuerySet[StoreItem] = StoreItem.objects.select_related("store", "store__site").filter(
        current_stock__lte=F("minimum_stock_level")
    )
    if not (user.is_system_admin or user.is_store_manager or user.is_hr):
        qs = qs.filter(store__site__in=visible_sites(user))
    if site_id:
        qs = qs.filter(store__site_id=site_id)
    return qs.order_by("store__site__name", "item_name")


def stock_requests(user: User, spec: StockRequestFilter) -> QuerySet[StockRequest]:
    """Stock requests in the user's scope with filters."""
    qs: QuerySet[StockRequest] = StockRequest.objects.select_related(
        "site", "store", "requested_by", "reviewed_by"
    ).prefetch_related("items__store_item")
    if not (user.is_system_admin or user.is_store_manager or user.is_hr):
        qs = qs.filter(site__in=visible_sites(user))
    if spec.store_id:
        qs = qs.filter(store_id=spec.store_id)
    if spec.site_id:
        qs = qs.filter(site_id=spec.site_id)
    if spec.status:
        qs = qs.filter(status=spec.status)
    if spec.request_date:
        qs = qs.filter(request_date=spec.request_date)
    return qs


def stock_request_or_none(request_id: int) -> StockRequest | None:
    """A single stock request with items, or None."""
    return (
        StockRequest.objects.select_related("site", "store", "requested_by", "reviewed_by")
        .prefetch_related("items__store_item")
        .filter(pk=request_id)
        .first()
    )


def stock_request_items(request_id: int) -> list[StockRequestItem]:
    """Items of a request with their store items (one query)."""
    return list(
        StockRequestItem.objects.filter(request_id=request_id)
        .select_related("store_item", "store_item__store")
        .order_by("store_item__item_name")
    )
