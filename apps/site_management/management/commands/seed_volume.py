"""Seed realistic volume data for performance testing.

Creates zones, sites, users, cleaners, assignments, attendance for the past
N days, inspections, issues/jobs, store items and movements. All data is bulk
created and namespaced by a run tag so repeated runs stay idempotent per run
(rows are created once per run tag).

Usage::

    python manage.py seed_volume --zones 3 --sites-per-zone 4 --cleaners-per-site 20 --days 30

Defaults are modest so tests never depend on large volumes; use the flags to
generate heavy data for benchmarking.
"""

from __future__ import annotations

import datetime
import random
from typing import Any, cast

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.accounts.factories import UserFactory
from apps.accounts.models import User
from apps.site_management.factories import (
    CleanerFactory,
    SiteFactory,
    StoreItemFactory,
    ZoneFactory,
)
from apps.site_management.models import (
    AttendanceRecord,
    AttendanceReviewStatus,
    AttendanceStatus,
    Cleaner,
    CleanerAssignmentStatus,
    CleanerSiteAssignment,
    CleanerStatus,
    Inspection,
    InspectionOverallStatus,
    InspectionTemplate,
    Issue,
    IssuePriority,
    IssueStatus,
    Job,
    JobStatus,
    Site,
    SiteArea,
    SiteStore,
    StockMovement,
    StockMovementType,
    StoreItem,
    Zone,
)

_STATUSES = [s.value for s in AttendanceStatus]
_REVIEW = [r.value for r in AttendanceReviewStatus]
_PRIORITIES = [p.value for p in IssuePriority]


class Command(BaseCommand):
    help = "Seed realistic volume data for performance benchmarking."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("--zones", type=int, default=2, help="Number of zones.")
        parser.add_argument("--sites-per-zone", type=int, default=3, help="Sites per zone.")
        parser.add_argument("--cleaners-per-site", type=int, default=15, help="Cleaners per site.")
        parser.add_argument("--days", type=int, default=30, help="Days of attendance history.")
        parser.add_argument("--items-per-store", type=int, default=20, help="Store items per site.")
        parser.add_argument("--run-tag", type=str, default="bench", help="Run tag to keep idempotent.")

    @transaction.atomic
    def handle(self, *args: Any, **options: Any) -> None:
        zones = options["zones"]
        sites_per_zone = options["sites_per_zone"]
        cleaners = options["cleaners_per_site"]
        days = options["days"]
        items_per_store = options["items_per_store"]
        tag = options["run_tag"]

        random.seed(42)
        today = timezone.localdate()

        if Site.objects.filter(name__startswith=f"[{tag}]").exists():
            self.stdout.write(f"Run tag '{tag}' already seeded; delete those rows to reseed.")
            return

        zone_objs: list[Zone] = []
        for z in range(zones):
            zone_objs.append(cast(Zone, ZoneFactory(name=f"[{tag}] Zone {z + 1}")))  # type: ignore[no-untyped-call]

        user = cast(User, UserFactory())  # type: ignore[no-untyped-call]
        sites: list[Site] = []
        for z in range(zones):
            for s in range(sites_per_zone):
                site = cast(Site, SiteFactory(zone=zone_objs[z], name=f"[{tag}] Site {z + 1}-{s + 1}"))  # type: ignore[no-untyped-call]
                sites.append(site)

                # Cleaners + assignments.
                cleaners_rows: list[Cleaner] = []
                for c in range(cleaners):
                    cleaner = cast(Cleaner, CleanerFactory(status=CleanerStatus.ACTIVE))  # type: ignore[no-untyped-call]
                    cleaners_rows.append(cleaner)
                CleanerSiteAssignment.objects.bulk_create(
                    [
                        CleanerSiteAssignment(
                            cleaner=cleaner,
                            site=site,
                            assignment_type="full_time",
                            start_date=today - datetime.timedelta(days=60),
                            status=CleanerAssignmentStatus.ACTIVE,
                            assigned_by=user,
                        )
                        for cleaner in cleaners_rows
                    ],
                    batch_size=500,
                )

                # Store items + a couple of movements each.
                store = SiteStore.objects.create(site=site, store_name=f"[{tag}] Store {z}-{s}", created_by=user)
                item_objs: list[StoreItem] = []
                for i in range(items_per_store):
                    item_objs.append(
                        cast(
                            StoreItem,
                            StoreItemFactory(  # type: ignore[no-untyped-call]
                                store=store, current_stock=random.randint(1, 60), opening_stock=60
                            ),
                        )
                    )
                StockMovement.objects.bulk_create(
                    [
                        StockMovement(
                            store_item=item,
                            movement_type=StockMovementType.OPENING,
                            quantity=item.opening_stock,
                            movement_date=today - datetime.timedelta(days=30),
                            recorded_by=user,
                        )
                        for item in item_objs
                    ],
                    batch_size=500,
                )

        # Attendance history: 1 record per cleaner per day.
        attendance_rows: list[AttendanceRecord] = []
        for site in sites:
            cleaner_ids = list(site.cleaner_assignments.values_list("cleaner_id", flat=True))
            for day_offset in range(days):
                day = today - datetime.timedelta(days=day_offset)
                for cleaner_id in cleaner_ids:
                    attendance_rows.append(
                        AttendanceRecord(
                            cleaner_id=cleaner_id,
                            site=site,
                            attendance_date=day,
                            status=random.choice(_STATUSES),
                            review_status=random.choice(_REVIEW),
                            recorded_by=user,
                        )
                    )
        AttendanceRecord.objects.bulk_create(attendance_rows, batch_size=2000)

        # Inspections: each site gets an area + inspections referencing a shared template.
        template = InspectionTemplate.objects.create(
            template_name=f"[{tag}] Checklist", frequency="manual", created_by=user
        )
        inspection_rows: list[Inspection] = []
        for site in sites:
            area = SiteArea.objects.create(site=site, area_name=f"[{tag}] Area {site.pk}")
            inspection_rows.extend(
                Inspection(
                    site=site,
                    area=area,
                    template=template,
                    inspection_date=today - datetime.timedelta(days=random.randint(0, days - 1)),
                    overall_status=random.choice([o.value for o in InspectionOverallStatus]),
                    status="reviewed",
                    inspected_by=user,
                )
                for _ in range(5)
            )
        Inspection.objects.bulk_create(inspection_rows, batch_size=1000)

        # Issues + jobs.
        issue_rows = [
            Issue(
                title=f"[{tag}] Issue {i}",
                site=random.choice(sites),
                source="manual",
                issue_category="other",
                priority=random.choice(_PRIORITIES),
                status=random.choice([s.value for s in IssueStatus]),
                raised_by=user,
            )
            for i in range(zones * sites_per_zone * 8)
        ]
        Issue.objects.bulk_create(issue_rows, batch_size=1000)
        job_rows = [
            Job(
                job_title=f"[{tag}] Job {i}",
                site=random.choice(sites),
                assigned_by=user,
                due_date=today + datetime.timedelta(days=random.randint(-3, 7)),
                priority=random.choice(_PRIORITIES),
                status=random.choice([s.value for s in JobStatus]),
            )
            for i in range(zones * sites_per_zone * 6)
        ]
        Job.objects.bulk_create(job_rows, batch_size=1000)

        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded {zones} zones, {len(sites)} sites, "
                f"{len(attendance_rows)} attendance rows, {len(issue_rows)} issues, "
                f"{len(job_rows)} jobs (tag={tag})."
            )
        )
