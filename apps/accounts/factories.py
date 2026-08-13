"""Factory-boy factories for the accounts app."""

from __future__ import annotations

from typing import Any

import factory

from apps.accounts.models import ApiToken, RoleCode, User


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User
        django_get_or_create = ("email",)
        skip_postgeneration_save = True

    email = factory.Sequence(lambda n: f"user{n}@whitebird.test")
    role = RoleCode.MANAGEMENT_VIEWER
    timezone = "Africa/Dar_es_Salaam"
    is_active = True

    @factory.post_generation
    def password(obj: User, create: bool, extracted: Any, **kwargs: Any) -> None:
        if create and extracted:
            obj.set_password(extracted)
            obj.save(update_fields=["password"])


class ApiTokenFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ApiToken

    user = factory.SubFactory(UserFactory)
    name = "factory-token"
