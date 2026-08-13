"""Seed a fully working demo tenant for the Site Management Module.

Creates an admin superuser, demo staff users, reference catalogs (site types,
statuses, asset categories), sites with departments/assets, and staff
assignments. Idempotent: re-running updates rather than duplicates.
"""

from __future__ import annotations

from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.text import slugify

from apps.accounts.models import RoleCode, User
from apps.site_management.models import (
    Asset,
    AssetCategory,
    AssignmentRole,
    Department,
    Site,
    SiteStatus,
    SiteType,
    StaffAssignment,
)

SITE_TYPES = [
    ("Beach Resort", "beach-resort", "Full-service coastal resort property."),
    ("Villa", "villa", "Private villa with dedicated housekeeping."),
    ("Boutique Hotel", "boutique-hotel", "Small high-touch hotel."),
    ("Campsite", "campsite", "Outdoor camping and glamping grounds."),
]

STATUSES = [
    ("Active", "active", "Operational and receiving guests.", 1, "#10b981"),
    ("Under Renovation", "under-renovation", "Closed or partially open for works.", 2, "#f59e0b"),
    ("Maintenance", "maintenance", "Routine maintenance in progress.", 3, "#3b82f6"),
    ("Inactive", "inactive", "Not currently operating.", 4, "#6b7280"),
]

CATEGORIES = [
    ("Vehicles", "vehicles", "Cars, boats and quad bikes."),
    ("Electronics", "electronics", "TVs, sound systems and IT equipment."),
    ("Furniture", "furniture", "Beds, sofas and outdoor furniture."),
    ("Kitchen Equipment", "kitchen-equipment", "Appliances and utensils."),
]

SITES: list[dict[str, Any]] = [
    {
        "name": "White Bird Beach Resort",
        "city": "Nungwi",
        "region": "Unguja North",
        "capacity": 120,
        "type": "beach-resort",
        "status": "active",
        "address": "Nungwi Beach Road",
        "contact_email": "resort@whitebird.co.tz",
        "contact_phone": "+255 777 000 111",
        "departments": ["Housekeeping", "Front Office", "Kitchen"],
        "assets": [
            ("Safari Land Cruiser", "vehicles", "WB-001"),
            ("Beach House TV", "electronics", "WB-T2-091"),
        ],
    },
    {
        "name": "Jambiani Sea Villa",
        "city": "Jambiani",
        "region": "Unguja South",
        "capacity": 12,
        "type": "villa",
        "status": "active",
        "address": "Jambiani Beachfront",
        "contact_email": "villa@whitebird.co.tz",
        "contact_phone": "+255 777 000 222",
        "departments": ["Housekeeping"],
        "assets": [("Sea Scooter", "vehicles", "WB-SS-004")],
    },
    {
        "name": "Stone Town Boutique",
        "city": "Stone Town",
        "region": "Mjini Magharibi",
        "capacity": 40,
        "type": "boutique-hotel",
        "status": "under-renovation",
        "address": "Kelele Square",
        "contact_email": "boutique@whitebird.co.tz",
        "contact_phone": "+255 777 000 333",
        "departments": ["Front Office", "Kitchen"],
        "assets": [],
    },
]


class Command(BaseCommand):
    help = "Idempotently seed demo data for the site management module."

    @transaction.atomic
    def handle(self, *args: Any, **options: Any) -> None:
        admin, _ = User.objects.get_or_create(
            email=settings.DEV_ADMIN_EMAIL,
            defaults={
                "role": RoleCode.SYSTEM_ADMIN,
                "is_staff": True,
                "is_superuser": True,
                "first_name": "Platform",
                "last_name": "Admin",
            },
        )
        admin.role = RoleCode.SYSTEM_ADMIN
        admin.is_staff = True
        admin.is_superuser = True
        if not admin.password or admin.password.startswith("!"):
            admin.set_password(settings.DEV_ADMIN_PASSWORD)
        admin.save()

        general = self._ensure_user("general@whitebird.test", "General", "Supervisor", RoleCode.GENERAL_SUPERVISOR)
        zone = self._ensure_user("zone@whitebird.test", "Zone", "Supervisor", RoleCode.ZONE_SUPERVISOR)
        site_supervisor = self._ensure_user(
            "site-supervisor@whitebird.test", "Site", "Supervisor", RoleCode.SITE_SUPERVISOR
        )
        viewer = self._ensure_user("viewer@whitebird.test", "Viewer", "User", RoleCode.MANAGEMENT_VIEWER)

        self._seed_reference_data()

        for spec in SITES:
            site, created = Site.objects.get_or_create(
                code=self._code(spec["name"]),
                defaults={
                    "name": spec["name"],
                    "slug": slugify(spec["name"]),
                    "site_type": SiteType.objects.get(slug=spec["type"]),
                    "status": SiteStatus.objects.get(slug=spec["status"]),
                    "city": spec["city"],
                    "region": spec["region"],
                    "address": spec["address"],
                    "capacity": spec["capacity"],
                    "contact_email": spec["contact_email"],
                    "contact_phone": spec["contact_phone"],
                    "created_by": admin,
                },
            )
            if created:
                self.stdout.write(f"  site: {site.name}")
            else:
                site.status = SiteStatus.objects.get(slug=spec["status"])
                site.save(update_fields=["status", "updated_at"])

            for dept_name in spec["departments"]:
                Department.objects.get_or_create(site=site, name=dept_name)
            for asset_name, category_slug, serial in spec["assets"]:
                Asset.objects.get_or_create(
                    site=site,
                    serial_number=serial,
                    defaults={
                        "name": asset_name,
                        "category": AssetCategory.objects.get(slug=category_slug),
                    },
                )

        resort = Site.objects.get(code=self._code("White Bird Beach Resort"))
        StaffAssignment.objects.get_or_create(
            site=resort,
            user=general,
            defaults={
                "role": AssignmentRole.SITE_MANAGER,
                "is_primary": True,
                "assigned_by": admin,
            },
        )
        StaffAssignment.objects.get_or_create(
            site=resort,
            user=zone,
            defaults={"role": AssignmentRole.SITE_MANAGER, "assigned_by": admin},
        )
        StaffAssignment.objects.get_or_create(
            site=resort,
            user=site_supervisor,
            defaults={"role": AssignmentRole.STAFF, "assigned_by": admin},
        )
        StaffAssignment.objects.get_or_create(
            site=resort,
            user=viewer,
            defaults={"role": AssignmentRole.STAFF, "assigned_by": admin},
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Seed complete. Admin login: {settings.DEV_ADMIN_EMAIL} / {settings.DEV_ADMIN_PASSWORD}"
            )
        )

    # ------------------------------------------------------------------ #

    def _ensure_user(self, email: str, first: str, last: str, role: RoleCode) -> User:
        user, created = User.objects.get_or_create(
            email=email,
            defaults={
                "first_name": first,
                "last_name": last,
                "role": role.value,
            },
        )
        user.role = role.value
        if not user.password or user.password.startswith("!"):
            user.set_password("changeme-password-1")
        user.save()
        if created:
            self.stdout.write(f"  user: {email}")
        return user

    def _seed_reference_data(self) -> None:
        for name, slug, description in SITE_TYPES:
            SiteType.objects.get_or_create(slug=slug, defaults={"name": name, "description": description})
        for name, slug, description, order, color in STATUSES:
            SiteStatus.objects.get_or_create(
                slug=slug,
                defaults={
                    "name": name,
                    "description": description,
                    "order": order,
                    "color": color,
                },
            )
        for name, slug, description in CATEGORIES:
            AssetCategory.objects.get_or_create(slug=slug, defaults={"name": name, "description": description})

    @staticmethod
    def _code(name: str) -> str:
        words = [word for word in name.upper().replace("-", " ").split() if word]
        return "".join(word[0] for word in words)[:4] + "01"
