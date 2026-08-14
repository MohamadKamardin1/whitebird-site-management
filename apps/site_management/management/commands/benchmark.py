"""Benchmark key selectors/endpoints and warn when slow.

Run after ``seed_volume`` to get realistic timings::

    python manage.py seed_volume --zones 3 --sites-per-zone 4 --cleaners-per-site 20 --days 30
    python manage.py benchmark

Prints per-selector wall-clock time, query counts, and warns (exit code 1)
when any selector exceeds the configured threshold.
"""

from __future__ import annotations

import time
from typing import Any

from django.core.management.base import BaseCommand
from django.db import connection
from django.db.models import Count

from apps.accounts.models import RoleCode, User
from apps.site_management.attendance_selectors import attendance_daily_sheet
from apps.site_management.inspection_selectors import inspection_summary
from apps.site_management.issues_selectors import issue_list
from apps.site_management.models import Issue, Site
from apps.site_management.reporting_selectors import reporting_status_dashboard
from apps.site_management.selectors import get_kpi_overview
from apps.site_management.store_selectors import stock_items

WARN_THRESHOLD_MS = 200.0


def _stock_items_for(user: User, sites: list[Site]) -> list[Any]:  # pragma: no cover - interactive ops tool
    if not sites:
        return []
    first_store = sites[0].stores.first()
    if first_store is None:
        return []
    return list(stock_items(user, first_store.pk))


class Command(BaseCommand):
    help = "Benchmark key selectors and warn when any are slow."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("--threshold-ms", type=float, default=WARN_THRESHOLD_MS)
        parser.add_argument("--date", type=str, default="today")

    def handle(self, *args: Any, **options: Any) -> None:  # pragma: no cover - interactive ops tool
        from datetime import date

        threshold = options["threshold_ms"]
        day = date.today()

        user, _ = User.objects.get_or_create(
            email="bench@whitebird.test",
            defaults={"role": RoleCode.SYSTEM_ADMIN, "is_superuser": True},
        )
        sites = list(Site.objects.filter(is_active=True)[:10])
        if not sites:
            self.stdout.write("No sites found. Run `python manage.py seed_volume` first.")
            return

        checks: list[tuple[str, Any]] = [
            ("kpi_overview", lambda: get_kpi_overview()),
            ("inspection_summary", lambda: inspection_summary(user)),
            (
                "issue_list",
                lambda: list(
                    issue_list(
                        user,
                        type(
                            "F",
                            (),
                            {
                                "site_id": None,
                                "status": None,
                                "priority": None,
                                "category": None,
                                "source": None,
                                "assigned_to_id": None,
                                "escalated": None,
                            },
                        )(),
                    )
                ),
            ),
            ("reporting_status_dashboard", lambda: reporting_status_dashboard(user, day)),
            ("attendance_daily_sheet", lambda: attendance_daily_sheet(user, sites[0].pk, day)),
            (
                "stock_items",
                lambda: _stock_items_for(user, sites),
            ),
        ]

        slow = False
        for name, fn in checks:
            start = time.perf_counter()
            n_queries_before = len(connection.queries)
            try:
                result = fn()
            except Exception as exc:
                self.stdout.write(self.style.WARNING(f"{name}: ERROR {exc}"))
                continue
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            queries = len(connection.queries) - n_queries_before
            flag = ""
            if elapsed_ms > threshold:
                flag = self.style.ERROR(" SLOW")
                slow = True
            self.stdout.write(f"{name:<28} {elapsed_ms:8.1f} ms  {queries:>4} queries{flag}")

        total_issues = Issue.objects.aggregate(n=Count("pk"))["n"]
        self.stdout.write(f"DB: {total_issues} issues, {sites[0] if sites else 'n/a'} sample site.")
        if slow:
            self.stdout.write(self.style.ERROR(f"WARNING: one or more selectors exceeded {threshold} ms."))
            raise SystemExit(1)
        self.stdout.write(self.style.SUCCESS("All selectors within budget."))
