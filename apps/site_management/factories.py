"""Factory-boy factories for the site management app."""

from __future__ import annotations

from datetime import date, timedelta

import factory

from apps.accounts.factories import UserFactory

from .models import (
    AssetCategory,
    AssistantGeneralSupervisorAssignment,
    Site,
    SiteStatus,
    SiteSupervisorAssignment,
    SiteType,
    WorkMode,
    Zone,
    ZoneSupervisorAssignment,
)


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


class ZoneFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Zone

    name = factory.Sequence(lambda n: f"Zone {n}")
    code = factory.Sequence(lambda n: f"ZN{n:02d}")
    is_active = True
    created_by = factory.SubFactory(UserFactory)


class SiteFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Site

    name = factory.Sequence(lambda n: f"Site {n}")
    slug = factory.Sequence(lambda n: f"site-{n}")
    code = factory.Sequence(lambda n: f"SITE{n:03d}")
    zone = factory.SubFactory(ZoneFactory)
    status = factory.SubFactory(SiteStatusFactory)
    site_type = factory.SubFactory(SiteTypeFactory)
    city = "Nungwi"
    region = "Unguja North"
    country = "TZ"
    capacity = 100
    work_mode = WorkMode.FULL_TIME
    working_days = ["mon", "tue", "wed", "thu", "fri"]
    created_by = factory.SubFactory(UserFactory)


class SiteSupervisorAssignmentFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = SiteSupervisorAssignment

    site = factory.SubFactory(SiteFactory)
    user = factory.SubFactory(UserFactory)
    assigned_from = date.today() - timedelta(days=30)
    assigned_to = None
    is_primary = False
    is_active = True


class ZoneSupervisorAssignmentFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ZoneSupervisorAssignment

    zone = factory.SubFactory(ZoneFactory)
    user = factory.SubFactory(UserFactory)
    assigned_from = date.today() - timedelta(days=30)
    assigned_to = None
    is_active = True


class AssistantGeneralSupervisorAssignmentFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = AssistantGeneralSupervisorAssignment

    user = factory.SubFactory(UserFactory)
    all_zones = False
    zone = factory.SubFactory(ZoneFactory)
    assigned_from = date.today() - timedelta(days=30)
    assigned_to = None
    is_active = True
