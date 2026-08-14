"""Tests for the policy-layer helpers."""

import pytest

from apps.core.errors import ConflictError
from apps.core.policies import ensure_permitted, require


def test_require_raises_when_condition_false() -> None:
    require(True, ConflictError("ok"))
    with pytest.raises(ConflictError):
        require(False, ConflictError("nope"))


def test_ensure_permitted_uses_predicate() -> None:
    ensure_permitted(lambda value: value > 0, 5, ConflictError("nope"))
    with pytest.raises(ConflictError):
        ensure_permitted(lambda value: value > 0, -1, ConflictError("nope"))
