"""Shared managers and querysets: soft delete, safe defaults."""

from __future__ import annotations

from typing import TypeVar

from django.db import models
from django.db.models import QuerySet

ModelT = TypeVar("ModelT", bound=models.Model)


class SoftDeleteQuerySet(QuerySet[ModelT]):
    """QuerySet that hides soft-deleted rows by default."""

    def alive(self) -> SoftDeleteQuerySet[ModelT]:
        return self.filter(is_active=True)

    def deleted(self) -> SoftDeleteQuerySet[ModelT]:
        return self.filter(is_active=False)


class SoftDeleteManager(models.Manager[ModelT]):
    """Manager returning only active (non-archived) rows unless asked otherwise."""

    def get_queryset(self) -> SoftDeleteQuerySet[ModelT]:
        return SoftDeleteQuerySet(self.model, using=self._db).filter(is_active=True)

    def all_with_deleted(self) -> SoftDeleteQuerySet[ModelT]:
        return SoftDeleteQuerySet(self.model, using=self._db)

    def only_deleted(self) -> SoftDeleteQuerySet[ModelT]:
        return SoftDeleteQuerySet(self.model, using=self._db).filter(is_active=False)
