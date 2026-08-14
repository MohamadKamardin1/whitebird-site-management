"""Seed a realistic, professional demo tenant.

Idempotent: stable business identifiers (zone/site codes, user emails) are
``get_or_create``d so re-running updates rather than duplicates. All data is
fake and safe — no real PII. Uses the public services so every row satisfies
domain validation.

Usage::

    python manage.py seed_rbac
    python manage.py seed_demo [--sites 3]
"""

from __future__ import annotations

import datetime
import decimal
from typing import Any

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from apps.accounts.models import RoleCode, User
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
    Issue,
    IssueCategory,
    IssuePriority,
    IssueSource,
    IssueStatus,
    Job,
    JobStatus,
    OperationalRole,
    Site,
    SiteStatus,
    SiteStore,
    SiteType,
    TraineeProgram,
    TraineeProgramStatus,
    Zone,
)
from apps.site_management.reporting_services import (
    generate_assistant_summary,
    generate_general_management_report,
    generate_site_report,
    generate_zone_summary,
    review_site_report_by_zone,
    submit_assistant_summary,
    submit_general_management_report,
    submit_site_report,
    submit_zone_summary,
)
from apps.site_management.services import create_area, create_shift
from apps.site_management.store_services import (
    add_store_item,
    create_stock_request,
    receive_stock,
    submit_stock_request,
)


class Command(BaseCommand):
    help = "Seed a complete, realistic demo tenant (idempotent)."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("--sites", type=int, default=3, help="Sites to create per zone.")
        parser.add_argument("--cleaners", type=int, default=8, help="Cleaners per site.")

    @transaction.atomic
    def handle(self, *args: Any, **options: Any) -> None:
        sites_per_zone = options["sites"]
        cleaners_per_site = options["cleaners"]

        admin = self._user("admin@whitebird.local", RoleCode.SYSTEM_ADMIN, is_superuser=True)
        gs = self._user("general@whitebird.local", RoleCode.GENERAL_SUPERVISOR)
        ags = self._user("assistant@whitebird.local", RoleCode.ASSISTANT_GENERAL_SUPERVISOR)
        zone_user = self._user("zone@whitebird.local", RoleCode.ZONE_SUPERVISOR)
        site_user = self._user("site@whitebird.local", RoleCode.SITE_SUPERVISOR)
        self._user("viewer@whitebird.local", RoleCode.MANAGEMENT_VIEWER)

        zone = self._zone("ZNZ-N", "Unguja North")
        site_type = self._site_type()
        status = self._status()
        role = self._operational_role()

        sites: list[Site] = []
        for i in range(sites_per_zone):
            code = f"WB-{i + 1:02d}"
            site, created = Site.objects.get_or_create(
                code=code,
                defaults={
                    "name": f"White Bird {['Beach Resort', 'Villa Bay', 'Boutique Hotel'][i % 3]} {i + 1}",
                    "slug": slugify(code),
                    "zone": zone,
                    "site_type": site_type,
                    "status": status,
                    "work_mode": "full_time_and_shift",
                    "city": "Nungwi",
                    "region": "Unguja North",
                    "country": "TZ",
                    "capacity": 80 + i * 20,
                    "created_by": admin,
                },
            )
            sites.append(site)
            self._configure_site(site, role, admin)

        site = sites[0]
        self._assign_supervisor(site, site_user)
        self._assign_supervisor(site, zone_user, is_zone=True)

        # Cleaners, documents, assignments.
        for site_index, site in enumerate(sites):
            for n in range(cleaners_per_site):
                self._cleaner(site, admin, n, site_index, gs)

        # Attendance for the last 3 days.
        today = timezone.localdate()
        for day_offset in range(3):
            day = today - datetime.timedelta(days=day_offset)
            for site in sites:
                self._attendance(site, day, admin)

        # Inspections.
        self._inspections(site, today, admin)

        # Issues + jobs.
        self._issues_jobs(site, today, admin)

        # Store data.
        self._store(site, admin, today)

        # Reporting chain for today.
        self._reports(site, today, admin, zone_user, gs)

        self.stdout.write(
            self.style.SUCCESS(
                f"Demo tenant ready: {len(sites)} sites, {Cleaner.objects.count()} cleaners, "
                f"users for every role. Admin: {admin.email}"
            )
        )

    # -- helpers ----------------------------------------------------------- #

    def _user(self, email: str, role: RoleCode, is_superuser: bool = False) -> User:
        user, _ = User.objects.get_or_create(
            email=email,
            defaults={
                "role": role,
                "is_superuser": is_superuser,
                "is_staff": True,
                "is_active": True,
                "password": "demo-password-1",
            },
        )
        return user

    def _zone(self, code: str, name: str) -> Zone:
        zone, _ = Zone.objects.get_or_create(code=code, defaults={"name": name})
        return zone

    def _site_type(self) -> SiteType:
        obj, _ = SiteType.objects.get_or_create(slug="beach-resort", defaults={"name": "Beach Resort"})
        return obj

    def _status(self) -> SiteStatus:
        obj, _ = SiteStatus.objects.get_or_create(
            slug="operational", defaults={"name": "Operational", "color": "#2E7D32"}
        )
        return obj

    def _operational_role(self) -> OperationalRole:
        obj, _ = OperationalRole.objects.get_or_create(code="cleaner", defaults={"name": "Cleaner"})
        return obj

    def _configure_site(self, site: Site, role: OperationalRole, admin: User) -> None:
        if not site.shifts.exists():
            create_shift(
                site=site,
                shift_name="Morning",
                shift_code=f"AM-{site.code}",
                start_time=datetime.time(7, 0),
                end_time=datetime.time(15, 0),
                effective_days=["mon", "tue", "wed", "thu", "fri"],
                actor=admin,
            )
        for area_name in ("Lobby", "Rooms", "Pool Deck"):
            if not site.areas.filter(area_name=area_name).exists():
                create_area(
                    site=site, area_name=area_name, area_code=f"{site.code}-{area_name[:2].upper()}", actor=admin
                )

    def _assign_supervisor(self, site: Site, user: User, is_zone: bool = False) -> Any:
        obj: Any = None
        if is_zone:
            from apps.site_management.models import ZoneSupervisorAssignment

            obj, _ = ZoneSupervisorAssignment.objects.get_or_create(
                zone=site.zone,
                user=user,
                is_active=True,
                defaults={"assigned_from": timezone.localdate() - datetime.timedelta(days=30)},
            )
            return obj
        from apps.site_management.models import SiteSupervisorAssignment

        obj, _ = SiteSupervisorAssignment.objects.get_or_create(
            site=site,
            user=user,
            is_active=True,
            defaults={"assigned_from": timezone.localdate() - datetime.timedelta(days=30)},
        )
        return obj

    def _cleaner(self, site: Site, admin: User, n: int, site_index: int, gs: User) -> Any:
        first = f"Demo{site_index}{n}"
        cleaner, _ = Cleaner.objects.get_or_create(
            id_type="nida",
            id_number=f"NIDA{site_index:02d}{n:04d}",
            defaults={
                "first_name": first,
                "last_name": f"Worker{n}",
                "gender": "female" if n % 2 == 0 else "male",
                "birth_date": datetime.date(1990 + (n % 15), 1, 1),
                "living_location": "Stone Town",
                "status": CleanerStatus.ACTIVE,
                "created_by": admin,
            },
        )
        assignment, _ = CleanerSiteAssignment.objects.get_or_create(
            cleaner=cleaner,
            site=site,
            defaults={
                "assignment_type": "full_time",
                "start_date": timezone.localdate() - datetime.timedelta(days=60),
                "status": CleanerAssignmentStatus.ACTIVE,
                "assigned_by": admin,
            },
        )
        if n == 0:
            # One trainee per site.
            TraineeProgram.objects.get_or_create(
                cleaner=cleaner,
                defaults={
                    "site": site,
                    "start_date": timezone.localdate() - datetime.timedelta(days=5),
                    "expected_end_date": timezone.localdate() + datetime.timedelta(days=55),
                    "status": TraineeProgramStatus.IN_TRAINING,
                    "created_by": gs,
                },
            )
        return assignment

    def _attendance(self, site: Site, day: datetime.date, admin: User) -> None:
        cleaners = list(
            site.cleaner_assignments.filter(status=CleanerAssignmentStatus.ACTIVE).values_list("cleaner_id", flat=True)
        )
        statuses = [
            AttendanceStatus.PRESENT,
            AttendanceStatus.PRESENT,
            AttendanceStatus.LATE,
            AttendanceStatus.ABSENT,
            AttendanceStatus.SICK,
            AttendanceStatus.PRESENT,
        ]
        rows = [
            AttendanceRecord(
                cleaner_id=cid,
                site=site,
                attendance_date=day,
                status=statuses[i % len(statuses)],
                review_status=AttendanceReviewStatus.SUBMITTED,
                recorded_by=admin,
            )
            for i, cid in enumerate(cleaners)
        ]
        existing = set(
            AttendanceRecord.objects.filter(site=site, attendance_date=day).values_list("cleaner_id", flat=True)
        )
        AttendanceRecord.objects.bulk_create([r for r in rows if r.cleaner_id not in existing])

    def _inspections(self, site: Site, day: datetime.date, admin: User) -> None:
        area = site.areas.first()
        if area is None:
            return
        template = self._inspection_template(admin, site)
        for status in (InspectionOverallStatus.PASSED, InspectionOverallStatus.NEEDS_ATTENTION):
            Inspection.objects.get_or_create(
                site=site,
                inspection_date=day,
                defaults={
                    "area": area,
                    "template": template,
                    "overall_status": status,
                    "status": "reviewed",
                    "inspected_by": admin,
                },
            )

    def _inspection_template(self, admin: User, site: Site) -> Any:
        return self._template_or_create(admin, site)

    def _template_or_create(self, admin: User, site: Site) -> Any:
        from apps.site_management.inspection_services import create_template

        template = site.inspection_templates.first()
        if template is not None:
            return template
        return create_template(
            template_name="Housekeeping Audit",
            actor=admin,
            site=site,
            items=[
                {"item_label": "Cleanliness", "item_type": "pass_fail", "sequence": 1},
                {"item_label": "Condition", "item_type": "photo", "sequence": 2},
            ],
        )

    def _issues_jobs(self, site: Site, day: datetime.date, admin: User) -> None:
        issue, _ = Issue.objects.get_or_create(
            title="Leaking tap in room 12",
            site=site,
            defaults={
                "source": IssueSource.MANUAL,
                "issue_category": IssueCategory.MAINTENANCE,
                "priority": IssuePriority.HIGH,
                "status": IssueStatus.OPEN,
                "raised_by": admin,
            },
        )
        Job.objects.get_or_create(
            job_title="Repair leaking tap",
            site=site,
            defaults={
                "issue": issue,
                "assigned_by": admin,
                "due_date": day + datetime.timedelta(days=2),
                "priority": IssuePriority.HIGH,
                "status": JobStatus.ASSIGNED,
            },
        )

    def _store(self, site: Site, admin: User, day: datetime.date) -> None:
        store, _ = SiteStore.objects.get_or_create(site=site, store_name="Main Store", defaults={"created_by": admin})
        if not store.items.exists():
            item = add_store_item(store=store, item_name="Detergent", actor=admin, opening_stock=decimal.Decimal("40"))
            receive_stock(store_item=item, quantity=decimal.Decimal("10"), actor=admin, movement_date=day)
            low = add_store_item(
                store=store,
                item_name="Glass Cleaner",
                actor=admin,
                opening_stock=decimal.Decimal("3"),
                minimum_stock_level=decimal.Decimal("5"),
            )
            request = create_stock_request(
                site=site,
                store=store,
                actor=admin,
                items=[{"store_item_id": low.pk, "requested_quantity": decimal.Decimal("12")}],
                request_date=day,
            )
            submit_stock_request(request=request, actor=admin)

    def _reports(self, site: Site, day: datetime.date, admin: User, zone_user: User, gs: User) -> None:
        from apps.site_management.models import DailySiteReport

        if DailySiteReport.objects.filter(site=site, report_date=day).exists():
            return
        if site.zone_id is None:
            return
        report = generate_site_report(site_id=site.pk, day=day, user=admin)
        submit_site_report(report=report, user=admin)
        review_site_report_by_zone(report=report, user=zone_user)
        zone_report = generate_zone_summary(zone_id=site.zone_id, day=day, user=zone_user)
        submit_zone_summary(report=zone_report, user=zone_user)
        assistant = generate_assistant_summary(day=day, user=gs, zone_ids=[site.zone_id])
        submit_assistant_summary(report=assistant, user=gs)
        general = generate_general_management_report(day=day, user=gs)
        submit_general_management_report(report=general, user=gs)
