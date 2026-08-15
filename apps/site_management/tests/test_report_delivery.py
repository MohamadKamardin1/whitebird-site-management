from datetime import date
from unittest.mock import patch

import pytest
from django.test import TestCase, override_settings

from apps.site_management.models import ReportDelivery
from apps.site_management.report_delivery import _period_window, deliver_scheduled_report, render_report_pdf


class ReportDeliveryTests(TestCase):
    def test_period_windows_are_deterministic(self) -> None:
        daily = _period_window(ReportDelivery.ReportType.DAILY, date(2026, 8, 15))
        weekly = _period_window(ReportDelivery.ReportType.WEEKLY, date(2026, 8, 15))
        monthly = _period_window(ReportDelivery.ReportType.MONTHLY, date(2026, 8, 15))

        assert daily[:3] == ("2026-08-15", date(2026, 8, 15), date(2026, 8, 15))
        assert weekly[:3] == ("2026-08-03_2026-08-09", date(2026, 8, 3), date(2026, 8, 9))
        assert monthly[:3] == ("2026-07", date(2026, 7, 1), date(2026, 7, 31))

    def test_pdf_is_white_bird_branded_without_records(self) -> None:
        filename, content = render_report_pdf(ReportDelivery.ReportType.DAILY, date(2026, 8, 15))

        assert filename == "whitebird-daily-2026-08-15.pdf"
        assert content.startswith(b"%PDF")
        assert len(content) > 1000

    @override_settings(RESEND_API_KEY="")
    def test_missing_resend_key_is_recorded_as_a_failed_delivery(self) -> None:
        with pytest.raises(RuntimeError, match="RESEND_API_KEY is not configured"):
            deliver_scheduled_report(ReportDelivery.ReportType.DAILY, date(2026, 8, 15))

        delivery = ReportDelivery.objects.get(
            report_type=ReportDelivery.ReportType.DAILY,
            period_key="2026-08-15",
            recipient="admin@whitebirdtanzania.com",
        )
        assert delivery.status == ReportDelivery.DeliveryStatus.FAILED
        assert "RESEND_API_KEY" in delivery.error_message

    @override_settings(RESEND_API_KEY="re_test_key", REPORTS_FROM_EMAIL="reports@whitebirdtanzania.com")
    @patch("apps.site_management.report_delivery._send_resend", return_value="msg_test_123")
    def test_successful_delivery_is_idempotent(self, send_resend) -> None:
        first = deliver_scheduled_report(ReportDelivery.ReportType.DAILY, date(2026, 8, 15))
        second = deliver_scheduled_report(ReportDelivery.ReportType.DAILY, date(2026, 8, 15))

        assert first == "sent"
        assert second == "already_sent"
        assert send_resend.call_count == 1
