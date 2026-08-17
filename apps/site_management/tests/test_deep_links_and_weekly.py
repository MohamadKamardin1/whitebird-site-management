import datetime
from unittest.mock import patch

import pytest
from django.urls import resolve

from apps.site_management.factories import SiteFactory
from apps.site_management.models import DailySiteReport
from apps.site_management.reporting_services import generate_weekly_site_report
from apps.web.views import react_app


def test_app_deep_links_resolve_to_the_react_shell() -> None:
    for path in ("/app/attendance", "/app/inspections", "/app/operations/issues", "/app/stores", "/app/reports"):
        assert resolve(path).func == react_app


@pytest.mark.django_db
def test_weekly_report_contains_monday_to_friday_snapshots(admin_user) -> None:
    site = SiteFactory()
    friday = datetime.date(2026, 8, 14)

    with patch(
        "apps.site_management.reporting_services.site_data_snapshot",
        side_effect=lambda site_id, day: {"day": day.isoformat(), "site_id": site_id},
    ):
        result = generate_weekly_site_report(site_id=site.pk, friday=friday, user=admin_user)

    assert result["report_type"] == "weekly"
    assert result["week_start"] == "2026-08-10"
    assert result["week_end"] == "2026-08-14"
    assert [row["report_date"] for row in result["days"]] == [
        "2026-08-10",
        "2026-08-11",
        "2026-08-12",
        "2026-08-13",
        "2026-08-14",
    ]
    assert all(row["data"]["site_id"] == site.pk for row in result["days"])


@pytest.mark.django_db
def test_weekly_report_keeps_saved_daily_challenges(admin_user) -> None:
    site = SiteFactory()
    friday = datetime.date(2026, 8, 14)
    monday = friday - datetime.timedelta(days=4)
    DailySiteReport.objects.create(
        site=site,
        report_date=monday,
        created_by=admin_user,
        updated_by=admin_user,
        challenges=["Mfumo wa maji una tatizo"],
    )

    result = generate_weekly_site_report(site_id=site.pk, friday=friday, user=admin_user)

    assert result["days"][0]["data"]["challenges"] == ["Mfumo wa maji una tatizo"]


@pytest.mark.django_db
def test_weekly_report_rejects_non_friday(admin_user) -> None:
    site = SiteFactory()
    with pytest.raises(Exception, match="Friday"):
        generate_weekly_site_report(site_id=site.pk, friday=datetime.date(2026, 8, 13), user=admin_user)
