"""Host-facing views: probes, the landing redirect, and the role-aware dashboard."""

from __future__ import annotations

from typing import Any

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.db import connection
from django.http import FileResponse, HttpRequest, HttpResponse, HttpResponseRedirect
from django.shortcuts import redirect, render

from apps.accounts.models import RoleCode
from apps.site_management.dashboard_selectors import all_dashboard_charts, dashboard_kpis


def healthz(request: HttpRequest) -> HttpResponse:
    """Liveness probe — the process is up.

    Deliberately does not touch the database or cache so orchestrators can
    distinguish "process alive" from "dependencies degraded".
    """
    return HttpResponse("OK", content_type="text/plain")


def readyz(request: HttpRequest) -> HttpResponse:
    """Readiness probe — dependencies are reachable.

    Returns HTTP 503 when the database or cache cannot be reached.
    """
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        db_ok = True
    except Exception:
        db_ok = False

    try:
        cache.set("readyz:probe", "ok", timeout=5)
        cache_ok = cache.get("readyz:probe") == "ok"
    except Exception:
        cache_ok = False

    if not (db_ok and cache_ok):
        return HttpResponse("NOT READY", content_type="text/plain", status=503)
    return HttpResponse("OK", content_type="text/plain")


def landing(request: HttpRequest) -> HttpResponseRedirect:
    """Point the platform root at the dashboard when signed in, else the admin."""
    if request.user.is_authenticated:
        return redirect("dashboard")
    return redirect("admin:index")


def react_app(request: HttpRequest) -> Any:
    """Serve the production React entry point produced by the in-repository Vite build."""
    index = settings.STATIC_ROOT / "frontend" / "index.html"
    if not index.exists():
        return HttpResponse(
            "White Bird frontend is not built. Run `pnpm build` in frontend and `collectstatic`.",
            content_type="text/plain",
            status=503,
        )
    return FileResponse(index.open("rb"), content_type="text/html")


_TEMPLATE_BY_ROLE: dict[str, str] = {
    RoleCode.SYSTEM_ADMIN.value: "web/dashboard/general_supervisor.html",
    RoleCode.GENERAL_SUPERVISOR.value: "web/dashboard/general_supervisor.html",
    RoleCode.ASSISTANT_GENERAL_SUPERVISOR.value: "web/dashboard/assistant_general.html",
    RoleCode.ZONE_SUPERVISOR.value: "web/dashboard/zone_supervisor.html",
    RoleCode.SITE_SUPERVISOR.value: "web/dashboard/site_supervisor.html",
    RoleCode.MANAGEMENT_VIEWER.value: "web/dashboard/management.html",
}

_ROLE_LABELS: dict[str, str] = {
    RoleCode.SYSTEM_ADMIN.value: "System Administration",
    RoleCode.GENERAL_SUPERVISOR.value: "General Supervisor",
    RoleCode.ASSISTANT_GENERAL_SUPERVISOR.value: "Assistant General Supervisor",
    RoleCode.ZONE_SUPERVISOR.value: "Zone Supervisor",
    RoleCode.SITE_SUPERVISOR.value: "Site Supervisor",
    RoleCode.MANAGEMENT_VIEWER.value: "Management Viewer",
}

_KPI_DISPLAY = [
    {"key": "active_sites", "label": "Active Sites", "icon": "building", "tone": "primary"},
    {"key": "active_cleaners", "label": "Active Cleaners", "icon": "users", "tone": "accent"},
    {"key": "trainees_in_training", "label": "Trainees", "icon": "graduation", "tone": "primary"},
    {"key": "attendance_rate", "label": "Attendance Rate", "icon": "check", "tone": "success", "suffix": "%"},
    {"key": "absences_today", "label": "Absences Today", "icon": "user-minus", "tone": "danger"},
    {"key": "late_today", "label": "Late Today", "icon": "clock", "tone": "warning"},
    {"key": "open_issues", "label": "Open Issues", "icon": "flag", "tone": "warning"},
    {"key": "overdue_jobs", "label": "Overdue Jobs", "icon": "wrench", "tone": "danger"},
    {"key": "low_stock_items", "label": "Low Stock Items", "icon": "box", "tone": "warning"},
    {
        "key": "inspections_pass_rate",
        "label": "Inspections Pass Rate",
        "icon": "clipboard",
        "tone": "success",
        "suffix": "%",
    },
    {"key": "missing_site_reports", "label": "Missing Reports", "icon": "file", "tone": "danger"},
    {"key": "pending_reports", "label": "Pending Reports", "icon": "clock", "tone": "primary"},
    {"key": "escalated_issues", "label": "Escalated Issues", "icon": "alert", "tone": "danger"},
]

_CHART_DISPLAY = [
    {"key": "attendance_trend", "label": "Attendance Trend (7 days)", "type": "line"},
    {"key": "inspection_trend", "label": "Inspection Trend (7 days)", "type": "line"},
    {"key": "issues_by_category", "label": "Open Issues by Category", "type": "doughnut"},
    {"key": "issues_by_site", "label": "Open Issues by Site", "type": "bar"},
    {"key": "jobs_open_vs_closed", "label": "Open vs Closed Jobs", "type": "doughnut"},
    {"key": "low_stock_by_site", "label": "Low Stock by Site", "type": "bar"},
    {"key": "report_status_by_site", "label": "Report Status (today)", "type": "bar"},
]


def dashboard(request: HttpRequest) -> HttpResponse:
    """Role-aware operations dashboard (session-authenticated)."""
    user = request.user
    if not user.is_authenticated:
        return redirect("admin:login")
    template = _TEMPLATE_BY_ROLE.get(user.role, "web/dashboard/management.html")
    kpi_display = [dict(item) for item in _KPI_DISPLAY]
    kpis = dashboard_kpis(user)
    for item in kpi_display:
        item["value"] = kpis.get(item["key"], 0)
    context = {
        "role_label": _ROLE_LABELS.get(user.role, "Operations"),
        "role": user.role,
        "is_read_only": user.role == RoleCode.MANAGEMENT_VIEWER,
        "kpis": kpis,
        "kpi_display": kpi_display,
        "charts": all_dashboard_charts(user, days=7),
        "chart_display": _CHART_DISPLAY,
    }
    return render(request, template, context)


dashboard = login_required(dashboard)
