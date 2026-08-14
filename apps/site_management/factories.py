"""Factory-boy factories for the site management app."""

from __future__ import annotations

import datetime
from datetime import date, timedelta

import factory

from apps.accounts.factories import UserFactory

from .models import (
    AssetCategory,
    AssistantGeneralSupervisorAssignment,
    AttendanceRecord,
    Cleaner,
    CleanerAreaSchedule,
    CleanerDocument,
    CleanerShiftAssignment,
    CleanerSiteAssignment,
    OperationalRole,
    Site,
    SiteArea,
    SiteShift,
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


class SiteShiftFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = SiteShift

    site = factory.SubFactory(SiteFactory)
    shift_name = factory.Sequence(lambda n: f"Shift {n}")
    shift_code = factory.Sequence(lambda n: f"SH{n:02d}")
    start_time = datetime.time(8, 0)
    end_time = datetime.time(16, 0)
    effective_days = ["mon", "tue", "wed", "thu", "fri"]
    sequence = 0
    is_active = True


class SiteAreaFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = SiteArea

    site = factory.SubFactory(SiteFactory)
    area_name = factory.Sequence(lambda n: f"Area {n}")
    area_code = factory.Sequence(lambda n: f"AR{n:02d}")
    floor = ""
    is_active = True


class OperationalRoleFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = OperationalRole
        django_get_or_create = ("code",)

    name = factory.Sequence(lambda n: f"Role {n}")
    code = factory.Sequence(lambda n: f"role-{n}")
    is_active = True


class CleanerFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Cleaner

    first_name = factory.Sequence(lambda n: f"Cleaner{n}")
    last_name = factory.Sequence(lambda n: f"Last{n}")
    id_type = "nida"
    id_number = factory.Sequence(lambda n: f"NIDA{n:08d}")
    gender = "female"
    birth_date = date(1990, 1, 1)
    living_location = "Stone Town"
    status = "applicant"
    created_by = factory.SubFactory(UserFactory)


class CleanerDocumentFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = CleanerDocument

    cleaner = factory.SubFactory(CleanerFactory)
    document_type = "nida"
    document_number = factory.Sequence(lambda n: f"DOC{n:06d}")
    file = factory.django.FileField(data=b"%PDF-1.4 test document")
    original_filename = factory.Sequence(lambda n: f"doc-{n}.pdf")
    content_type = "application/pdf"
    size_bytes = 19
    file_hash = factory.Sequence(lambda n: f"hash{n:064d}")
    status = "pending"


class CleanerSiteAssignmentFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = CleanerSiteAssignment

    cleaner = factory.SubFactory(CleanerFactory)
    site = factory.SubFactory(SiteFactory)
    assignment_type = "full_time"
    start_date = date.today()
    status = "draft"
    assigned_by = factory.SubFactory(UserFactory)


class CleanerShiftAssignmentFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = CleanerShiftAssignment

    assignment = factory.SubFactory(CleanerSiteAssignmentFactory)
    shift = factory.SubFactory(SiteShiftFactory)
    effective_from = date.today()
    is_active = True


class CleanerAreaScheduleFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = CleanerAreaSchedule

    assignment = factory.SubFactory(CleanerSiteAssignmentFactory)
    site_area = factory.SubFactory(SiteAreaFactory)
    operational_role = factory.SubFactory(OperationalRoleFactory)
    date = date.today()
    start_time = datetime.time(8, 0)
    end_time = datetime.time(16, 0)
    is_active = True


class AttendanceRecordFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = AttendanceRecord

    cleaner = factory.SubFactory(CleanerFactory)
    site = factory.SubFactory(SiteFactory)
    attendance_date = date.today()
    status = "present"
    review_status = "draft"
    recorded_by = factory.SubFactory(UserFactory)
