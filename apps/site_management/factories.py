"""Factory-boy factories for the site management app."""

from __future__ import annotations

import factory

from apps.accounts.factories import UserFactory

from .models import AssetCategory, Site, SiteStatus, SiteType


class SiteTypeFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = SiteType
        django_get_or_create = ("slug",)

    name = factory.Sequence(lambda n: f"Type {n}")
    slug = factory.Sequence(lambda n: f"type-{n}")


class SiteStatusFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = SiteStatus
        django_get_or_create = ("slug",)

    name = factory.Sequence(lambda n: f"Status {n}")
    slug = factory.Sequence(lambda n: f"status-{n}")
    color = "#9c7c38"


class AssetCategoryFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = AssetCategory
        django_get_or_create = ("slug",)

    name = factory.Sequence(lambda n: f"Category {n}")
    slug = factory.Sequence(lambda n: f"category-{n}")


class SiteFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Site

    name = factory.Sequence(lambda n: f"Site {n}")
    slug = factory.Sequence(lambda n: f"site-{n}")
    code = factory.Sequence(lambda n: f"SITE{n:03d}")
    status = factory.SubFactory(SiteStatusFactory)
    site_type = factory.SubFactory(SiteTypeFactory)
    city = "Nungwi"
    region = "Unguja North"
    country = "TZ"
    capacity = 100
    created_by = factory.SubFactory(UserFactory)
