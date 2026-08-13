"""Tests for cache utilities and soft-delete managers."""

from __future__ import annotations

from unittest import mock

import pytest
from django.core.cache import cache

from apps.core.cache import (
    cache_key,
    cached_or,
    get_or_set,
    invalidate,
    invalidate_prefix,
    key,
    safe_delete,
    versioned,
)
from apps.site_management.factories import SiteFactory
from apps.site_management.models import Site


class _FakeRedisClient:
    """Mimics the ``scan_iter``/``delete`` surface used by invalidate_prefix."""

    def __init__(self) -> None:
        self.keys: list[str] = []
        self.deleted: list[str] = []

    def scan_iter(self, match: str) -> list[str]:
        prefix = match[:-1] if match.endswith("*") else match
        return [k for k in self.keys if k.startswith(prefix)]

    def delete(self, *keys: str) -> None:
        self.deleted.extend(keys)


@pytest.mark.django_db
def test_cached_or_computes_and_stores() -> None:
    calls = 0

    def loader() -> dict[str, int]:
        nonlocal calls
        calls += 1
        return {"value": 42}

    assert cached_or("probe", (1,), loader, timeout=60) == {"value": 42}
    assert cached_or("probe", (1,), loader, timeout=60) == {"value": 42}
    assert calls == 1


@pytest.mark.django_db
def test_invalidate_removes_single_key() -> None:
    value = cached_or("probe", (7,), lambda: {"x": 1}, timeout=60)
    assert value == {"x": 1}
    invalidate("probe", 7)
    assert cache.get(cache_key("probe", 7)) is None


@pytest.mark.django_db
def test_keys_are_namespaced() -> None:
    assert key("site", "detail", 1).startswith("wbz_site:")
    assert versioned(2, "stats").startswith("wbz_site:v2:")
    assert cache_key("site", 1) == key("site", 1)


@pytest.mark.django_db
def test_get_or_set_uses_factory() -> None:
    calls = 0

    def factory() -> int:
        nonlocal calls
        calls += 1
        return 99

    assert get_or_set("wbz_site:probe:1", factory, 60) == 99
    assert get_or_set("wbz_site:probe:1", factory, 60) == 99
    assert calls == 1


@pytest.mark.django_db
def test_safe_delete() -> None:
    cache.set("wbz_site:x", 1, 60)
    assert safe_delete("wbz_site:x") is True
    assert cache.get("wbz_site:x") is None


@pytest.mark.django_db
def test_invalidate_prefix_scans_and_deletes_redis_keys() -> None:
    fake = _FakeRedisClient()
    fake.keys = ["wbz_site:site:detail:abc", "wbz_site:site:stats:abc", "other:key"]

    class _FakeBackend:
        client = mock.Mock()
        client.get_client.return_value = fake

    with mock.patch("apps.core.cache.cache", _FakeBackend()):
        invalidate_prefix("site:detail")

    assert "wbz_site:site:detail:abc" in fake.deleted
    assert "wbz_site:site:stats:abc" not in fake.deleted


# --------------------------------------------------------------------------- #
# Soft-delete managers
# --------------------------------------------------------------------------- #


@pytest.mark.django_db
def test_soft_delete_manager_hides_archived_rows() -> None:
    alive = SiteFactory()
    archived = SiteFactory()
    archived.is_active = False
    archived.save(update_fields=["is_active", "updated_at"])

    assert set(Site.objects.values_list("pk", flat=True)) == {alive.pk}
    assert set(Site.objects.only_deleted().values_list("pk", flat=True)) == {archived.pk}
    assert set(Site.objects.all_with_deleted().values_list("pk", flat=True)) == {
        alive.pk,
        archived.pk,
    }
