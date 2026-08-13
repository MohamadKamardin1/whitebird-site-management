"""Factory-boy factories for the accounts app."""

from __future__ import annotations

from typing import Any

import factory

from apps.accounts.models import Role, User


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User
        django_get_or_create = ("username",)
        skip_postgeneration_save = True

    username = factory.Sequence(lambda n: f"user{n}")
    email = factory.LazyAttribute(lambda obj: f"{obj.username}@whitebird.test")
    role = Role.STAFF
    is_active = True

    @factory.post_generation
    def password(obj: User, create: bool, extracted: Any, **kwargs: Any) -> None:
        if create and extracted:
            obj.set_password(extracted)
            obj.save(update_fields=["password"])


class ApiTokenFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = "accounts.ApiToken"

    user = factory.SubFactory(UserFactory)
    name = "factory-token"
