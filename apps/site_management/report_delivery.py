"""Production report rendering and outbound delivery.

The scheduled task layer calls these functions. They are deterministic for a
period key, create no synthetic operational records, and use a durable
ReportDelivery row to prevent duplicate sends after retries.
"""

from __future__ import annotations

import base64
import io
import json
import logging
from calendar import monthrange
from datetime import date, timedelta
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .models import DailySiteReport, ReportDelivery

logger = logging.getLogger(__name__)
REPORT_RECIPIENT = "admin@whitebirdtanzania.com"


def _period_window(report_type: str, as_of: date) -> tuple[str, date, date, str]:
    if report_type == ReportDelivery.ReportType.DAILY:
        return as_of.isoformat(), as_of, as_of, f"Daily Operations Report — {as_of:%d %B %Y}"
    if report_type == ReportDelivery.ReportType.WEEKLY:
        end = as_of - timedelta(days=as_of.weekday() + 1)
        start = end - timedelta(days=6)
        return (
            f"{start.isoformat()}_{end.isoformat()}",
            start,
            end,
            f"Weekly Operations Report — {start:%d %b} to {end:%d %b %Y}",
        )
    if report_type == ReportDelivery.ReportType.MONTHLY:
        last_month = as_of.replace(day=1) - timedelta(days=1)
        start = last_month.replace(day=1)
        end = last_month.replace(day=monthrange(last_month.year, last_month.month)[1])
        return f"{start:%Y-%m}", start, end, f"Monthly Operations Report — {start:%B %Y}"
    raise ValueError(f"Unsupported report type: {report_type}")


def _safe(value: object, fallback: str = "—") -> str:
    if value is None or value == "":
        return fallback
    if isinstance(value, (dict, list)):
        if isinstance(value, dict):
            return " · ".join(f"{key.replace('_', ' ')}: {item}" for key, item in list(value.items())[:3]) or fallback
        return f"{len(value)} items" if value else fallback
    return str(value).replace("_", " ")


def render_report_pdf(report_type: str, as_of: date) -> tuple[str, bytes]:
    period_key, start, end, title = _period_window(report_type, as_of)
    rows = list(
        DailySiteReport.objects.filter(report_date__range=(start, end))
        .select_related("site", "site__zone")
        .order_by("report_date", "site__name")
    )
    buffer = io.BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=16 * mm,
        leftMargin=16 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title=title,
        author="White Bird Zanzibar",
    )
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="WhiteBirdTitle",
            parent=styles["Title"],
            fontName="Helvetica-Bold",
            fontSize=20,
            leading=24,
            textColor=colors.HexColor("#0B3540"),
            alignment=TA_LEFT,
            spaceAfter=6,
        )
    )
    styles.add(
        ParagraphStyle(
            name="WhiteBirdMeta",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=9,
            leading=13,
            textColor=colors.HexColor("#58706E"),
            spaceAfter=4,
        )
    )
    styles.add(
        ParagraphStyle(
            name="WhiteBirdSection",
            parent=styles["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=14,
            textColor=colors.HexColor("#0F7667"),
            spaceBefore=12,
            spaceAfter=6,
        )
    )
    styles.add(
        ParagraphStyle(
            name="WhiteBirdBody",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=9,
            leading=13,
            textColor=colors.HexColor("#294A4D"),
        )
    )
    story: list[object] = [
        Paragraph("WHITE BIRD ZANZIBAR", styles["WhiteBirdMeta"]),
        Paragraph(title, styles["WhiteBirdTitle"]),
        Paragraph(
            f"Period: {start:%d %B %Y} — {end:%d %B %Y} · Generated: {timezone.now():%d %B %Y %H:%M UTC}",
            styles["WhiteBirdMeta"],
        ),
        Spacer(1, 5 * mm),
    ]
    story.append(Paragraph("Operational coverage", styles["WhiteBirdSection"]))
    story.append(
        Paragraph(
            "This report contains records returned by the White Bird reporting model for the selected period. It is an operational summary for review and follow-up, not a replacement for the immutable source records.",
            styles["WhiteBirdBody"],
        )
    )
    story.append(Spacer(1, 4 * mm))
    table_data = [["Date", "Site", "Zone", "Attendance", "Stock", "Inspections", "Issues", "Status"]]
    for report in rows:
        table_data.append(
            [
                report.report_date.strftime("%d %b %Y"),
                _safe(report.site.name),
                _safe(report.site.zone.name if report.site.zone else None),
                _safe(report.attendance_summary),
                _safe(report.store_summary),
                _safe(report.inspection_summary),
                _safe(report.issues_summary),
                _safe(report.status),
            ]
        )
    if len(table_data) == 1:
        table_data.append(["—", "No report records returned", "—", "—", "—", "—", "—", "—"])
    table = Table(
        table_data, repeatRows=1, colWidths=[22 * mm, 31 * mm, 25 * mm, 27 * mm, 27 * mm, 27 * mm, 27 * mm, 19 * mm]
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0B3540")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 7),
                ("LEADING", (0, 0), (-1, -1), 9),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#D7D1C4")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#FFFDF8"), colors.HexColor("#F5F2E9")]),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.append(table)
    story.extend(
        [
            Spacer(1, 6 * mm),
            Paragraph("Review route", styles["WhiteBirdSection"]),
            Paragraph(
                "Daily site reports route to the assigned zone supervisor for review. The administrator mailbox receives this PDF delivery for central oversight. Any correction must be made through the authenticated White Bird workflow so the source record and audit trail remain authoritative.",
                styles["WhiteBirdBody"],
            ),
        ]
    )
    document.build(story)
    return f"whitebird-{report_type}-{period_key}.pdf", buffer.getvalue()


def _send_resend(*, subject: str, filename: str, content: bytes, recipient: str) -> str:
    api_key = str(getattr(settings, "RESEND_API_KEY", "") or "").strip()
    if not api_key:
        raise RuntimeError("RESEND_API_KEY is not configured")
    sender = str(getattr(settings, "REPORTS_FROM_EMAIL", "noreply@whitebirdtanzania.com"))
    payload = {
        "from": sender,
        "to": [recipient],
        "subject": subject,
        "text": "Attached is the scheduled White Bird Zanzibar operational report. Review and follow up through the authenticated operations workspace.",
        "attachments": [{"filename": filename, "content": base64.b64encode(content).decode("ascii")}],
    }
    request = Request(
        "https://api.resend.com/emails",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=20) as response:
            result = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError) as exc:
        raise RuntimeError(f"Resend delivery failed: {exc}") from exc
    return str(result.get("id", ""))


def deliver_scheduled_report(report_type: str, as_of: date | None = None) -> str:
    as_of = as_of or timezone.localdate()
    period_key, start, _end, title = _period_window(report_type, as_of)
    recipient = str(getattr(settings, "REPORTS_RECIPIENT_EMAIL", REPORT_RECIPIENT) or REPORT_RECIPIENT)
    delivery, _ = ReportDelivery.objects.get_or_create(
        report_type=report_type, period_key=period_key, recipient=recipient, defaults={"report_date": start}
    )
    if delivery.status == ReportDelivery.DeliveryStatus.SENT:
        return "already_sent"
    try:
        filename, content = render_report_pdf(report_type, as_of)
        provider_id = _send_resend(subject=title, filename=filename, content=content, recipient=recipient)
        delivery.status = ReportDelivery.DeliveryStatus.SENT
        delivery.provider_message_id = provider_id
        delivery.error_message = ""
        delivery.sent_at = timezone.now()
        delivery.save(update_fields=["status", "provider_message_id", "error_message", "sent_at", "updated_at"])
        return "sent"
    except Exception as exc:
        logger.exception("Scheduled %s report delivery failed for %s", report_type, period_key)
        delivery.status = ReportDelivery.DeliveryStatus.FAILED
        delivery.error_message = str(exc)[:4000]
        delivery.save(update_fields=["status", "error_message", "updated_at"])
        raise
