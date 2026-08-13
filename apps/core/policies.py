"""Policy-layer helpers.

Policies own permission and data-scoping decisions. Routers call a policy
before delegating to a service; services assume the policy already passed.
This module provides tiny, testable building blocks.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar

from .errors import DomainError

T = TypeVar("T")


def require(condition: bool, error: DomainError) -> None:
    """Raise ``error`` unless ``condition`` is truthy."""
    if not condition:
        raise error


def ensure_permitted(predicate: Callable[[Any], bool], value: Any, error: DomainError) -> None:
    """Raise ``error`` unless ``predicate(value)`` is truthy."""
    if not predicate(value):
        raise error
