"""Reusable pagination and sorting helpers for Django Ninja.

Page size defaults and caps come from django-constance so operators can tune
them at runtime without a deploy.
"""

from __future__ import annotations

from typing import Any

from constance import config
from ninja import Field, Schema


class PageParams(Schema):
    """Query parameters shared by every paginated list endpoint."""

    page: int = Field(1, ge=1, description="1-based page number.")
    page_size: int | None = Field(None, ge=1, description="Page size (capped at MAX_PAGE_SIZE).")


class Paginated[T](Schema):
    """Standard paginated response envelope: count/next/previous/results."""

    count: int
    next: str | None = None
    previous: str | None = None
    results: list[T]


def resolve_page_size(page_size: int | None, default: int | None = None, maximum: int | None = None) -> int:
    """Coerce a requested page size within the configured bounds."""
    default = default if default is not None else int(config.DEFAULT_PAGE_SIZE)
    maximum = maximum if maximum is not None else int(config.MAX_PAGE_SIZE)
    if page_size is None:
        page_size = default
    return max(1, min(page_size, maximum))


def paginate(
    queryset: Any,
    page: int,
    page_size: int | None,
    default_page_size: int | None = None,
    maximum_page_size: int | None = None,
) -> tuple[list[Any], int, int, int]:
    """Slice a queryset for a page.

    Returns ``(items, count, page, page_size)`` so callers can build the
    ``next``/``previous`` links with their request's absolute URL.
    """
    resolved = resolve_page_size(page_size, default_page_size, maximum_page_size)
    count = queryset.count()
    start = (page - 1) * resolved
    end = start + resolved
    return list(queryset[start:end]), count, page, resolved


def build_page_url(request: Any, page: int, page_size: int) -> str | None:
    """Build an absolute URL for a given page, preserving other query params."""
    query = request.GET.copy()
    query["page"] = str(page)
    query["page_size"] = str(page_size)
    return f"{request.build_absolute_uri(request.path)}?{query.urlencode()}"


def paginated_response[T](
    request: Any,
    queryset: Any,
    page: int,
    page_size: int | None,
    items: list[T],
    count: int,
) -> Paginated[T]:
    """Assemble a :class:`Paginated` response with correct page links."""
    resolved = resolve_page_size(page_size)
    total_pages = max(1, -(-count // resolved))
    next_page = build_page_url(request, page + 1, resolved) if page < total_pages else None
    previous_page = build_page_url(request, page - 1, resolved) if page > 1 else None
    return Paginated(count=count, next=next_page, previous=previous_page, results=items)


def apply_ordering(queryset: Any, sort: str | None, allowed_fields: list[str]) -> Any:
    """Apply a whitelisted sort key to a queryset.

    ``sort`` accepts ``field`` or ``-field``. Unknown fields are ignored so a
    client can never inject arbitrary ordering.
    """
    if not sort:
        return queryset
    descending = sort.startswith("-")
    field = sort[1:] if descending else sort
    if field in allowed_fields:
        return queryset.order_by(f"-{field}" if descending else field)
    return queryset
