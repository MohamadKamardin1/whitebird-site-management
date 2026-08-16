"""Role-aware White Bird AI Optimization Engine.

The service is deliberately read-only: it builds evidence from existing scoped
selectors, asks DeepSeek for a structured management brief, validates the
response, and persists the result for audit. It never mutates attendance,
issues, stock, inspections, assignments, or reports.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import date, timedelta
from typing import Any

import requests
from constance import config
from django.conf import settings
from django.utils import timezone

from apps.accounts.models import RoleCode, User
from apps.core.models import AuditLog
from apps.core.services import model_data, record_audit

from .dashboard_selectors import dashboard_kpis
from .models import AIOptimizationBrief
from .reporting_services import site_data_snapshot
from .scoping import visible_sites

logger = logging.getLogger(__name__)

LEADERSHIP_ROLES = frozenset(
    {
        RoleCode.ZONE_SUPERVISOR,
        RoleCode.ASSISTANT_GENERAL_SUPERVISOR,
        RoleCode.GENERAL_SUPERVISOR,
        RoleCode.SYSTEM_ADMIN,
        RoleCode.MANAGEMENT_VIEWER,
    }
)


def _model_name() -> str:
    return str(getattr(config, "DEEPSEEK_MODEL", "") or getattr(settings, "DEEPSEEK_MODEL", "deepseek-v4-pro"))


def _deepseek_api_key() -> str:
    return str(getattr(config, "DEEPSEEK_API_KEY", "") or getattr(settings, "DEEPSEEK_API_KEY", "") or "").strip()


def _scope_key(user: User) -> str:
    sites = list(visible_sites(user).values_list("pk", flat=True))
    scope_hash = hashlib.sha256(",".join(str(value) for value in sorted(sites)).encode()).hexdigest()[:16]
    return f"{user.role}:{scope_hash}"


def _fingerprint(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _integrity_checks(*, user: User, day: date, kpis: dict[str, Any], site_count: int) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    missing = int(kpis.get("missing_site_reports", 0) or 0)
    if missing:
        checks.append(
            {
                "code": "missing_daily_reports",
                "severity": "high",
                "count": missing,
                "message": f"{missing} visible site(s) have no submitted report for {day.isoformat()}.",
            }
        )
    for key, label, severity in (
        ("pending_reports", "reports awaiting review", "medium"),
        ("open_issues", "open issues", "medium"),
        ("escalated_issues", "escalated issues", "high"),
        ("overdue_jobs", "overdue jobs", "high"),
        ("low_stock_items", "low-stock items", "medium"),
    ):
        count = int(kpis.get(key, 0) or 0)
        if count:
            checks.append(
                {
                    "code": key,
                    "severity": severity,
                    "count": count,
                    "message": f"{count} {label} are visible in the authorised scope.",
                }
            )
    attendance_rate = float(kpis.get("attendance_rate", 0) or 0)
    if site_count and attendance_rate < 90:
        checks.append(
            {
                "code": "attendance_rate_below_standard",
                "severity": "high",
                "count": attendance_rate,
                "message": f"Attendance rate is {attendance_rate}% for the selected date.",
            }
        )
    if not checks:
        checks.append(
            {
                "code": "no_integrity_exceptions",
                "severity": "info",
                "count": 0,
                "message": "No deterministic reporting-quality exception was detected in the current scope.",
            }
        )
    return checks


def build_evidence_pack(*, user: User, day: date, weekly: bool = False) -> dict[str, Any]:
    """Build bounded, role-scoped operational evidence from authoritative selectors."""
    scoped_sites = list(visible_sites(user).filter(is_active=True).values("id", "name", "code", "zone__name"))[:100]
    site_ids = [int(row["id"]) for row in scoped_sites]
    kpis = dashboard_kpis(user, day)
    integrity = _integrity_checks(user=user, day=day, kpis=kpis, site_count=len(site_ids))
    days = [day - timedelta(days=offset) for offset in range(4, -1, -1)] if weekly else [day]
    snapshots: dict[str, dict[str, Any]] = {}
    for report_day in days:
        snapshots[report_day.isoformat()] = {
            str(site_id): site_data_snapshot(site_id, report_day) for site_id in site_ids
        }
    return {
        "as_of": day.isoformat(),
        "period": "monday_to_friday" if weekly else "daily",
        "actor_role": user.role,
        "scope_key": _scope_key(user),
        "visible_site_count": len(site_ids),
        "visible_sites": scoped_sites,
        "kpis": kpis,
        "integrity_checks": integrity,
        "snapshots": snapshots,
        "limitations": [
            "Only records in the authenticated user scope are included.",
            "Recommendations are advisory and do not modify operational records.",
            "Missing data is reported as missing; it is never inferred or fabricated.",
        ],
    }


def _fallback_output(evidence: dict[str, Any], reason: str) -> dict[str, Any]:
    checks = evidence.get("integrity_checks", [])
    priorities = [
        {
            "priority": check.get("severity", "medium"),
            "title": check.get("code", "Data-quality exception").replace("_", " ").title(),
            "evidence": check.get("message", "Review the exception in the relevant workspace."),
            "recommended_action": "Open the relevant operational workspace and assign the next accountable action.",
            "owner_role": "Current authorised supervisor",
            "due_within_days": 1 if check.get("severity") == "high" else 3,
        }
        for check in checks[:8]
        if check.get("severity") != "info"
    ]
    return {
        "headline": "White Bird operational brief is available with deterministic controls",
        "executive_summary": "The AI provider was unavailable, so this brief shows only validated operational signals and safe next-step guidance.",
        "priorities": priorities,
        "data_quality": checks,
        "reporting_optimizations": ["Complete missing daily records before escalating summary conclusions."],
        "confidence": "deterministic_only",
        "provider_note": reason,
        "disclaimer": "Advisory only. Use the existing audited White Bird workflows to take action.",
    }


def _validate_output(value: Any, evidence: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("DeepSeek returned a non-object JSON response")
    output = dict(value)
    output["headline"] = str(output.get("headline") or "White Bird operational optimization brief")[:240]
    output["executive_summary"] = str(output.get("executive_summary") or "No executive summary was returned.")[:3000]
    output["priorities"] = output.get("priorities") if isinstance(output.get("priorities"), list) else []
    output["data_quality"] = (
        output.get("data_quality")
        if isinstance(output.get("data_quality"), list)
        else evidence.get("integrity_checks", [])
    )
    output["reporting_optimizations"] = (
        output.get("reporting_optimizations") if isinstance(output.get("reporting_optimizations"), list) else []
    )
    output["confidence"] = str(output.get("confidence") or "review_required")
    output["disclaimer"] = "Advisory only. AI recommendations never change White Bird records automatically."
    return output


def _deepseek_summary(evidence: dict[str, Any], *, weekly: bool) -> tuple[dict[str, Any], str]:
    api_key = _deepseek_api_key()
    if not api_key:
        return _fallback_output(evidence, "DEEPSEEK_API_KEY is not configured."), "fallback"
    base_url = str(
        getattr(settings, "DEEPSEEK_API_BASE", "https://api.deepseek.com") or "https://api.deepseek.com"
    ).rstrip("/")
    schema_example = {
        "headline": "short operational headline",
        "executive_summary": "evidence-backed summary",
        "priorities": [
            {
                "priority": "high|medium|low",
                "title": "",
                "evidence": "",
                "recommended_action": "",
                "owner_role": "",
                "due_within_days": 1,
            }
        ],
        "data_quality": [{"code": "", "severity": "", "count": 0, "message": ""}],
        "reporting_optimizations": ["specific improvement"],
        "confidence": "high|medium|low|review_required",
    }
    system = (
        "You are White Bird AI Optimization Engine. Analyze only the supplied JSON evidence. "
        "Return valid JSON only. Never invent counts, names, dates, or events. Separate observed evidence from recommendations. "
        "Prioritize auditability, data completeness, accountability, safety, attendance, inspections, issues, stock, and report handover. "
        f"The required JSON shape is: {json.dumps(schema_example)}"
    )
    prompt = f"Create a {'Monday-Friday weekly' if weekly else 'daily'} leadership optimization brief for the authorised role. Output JSON. Evidence: {json.dumps(evidence, default=str)}"
    try:
        response = requests.post(
            f"{base_url}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": _model_name(),
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
                "response_format": {"type": "json_object"},
                "max_tokens": 1800,
                "stream": False,
            },
            timeout=45,
        )
        response.raise_for_status()
        body = response.json()
        content = body.get("choices", [{}])[0].get("message", {}).get("content")
        if not content:
            raise ValueError("DeepSeek returned empty content")
        return _validate_output(json.loads(content), evidence), "deepseek"
    except (requests.RequestException, ValueError, json.JSONDecodeError, KeyError, IndexError) as exc:
        logger.warning("DeepSeek optimization request failed: %s", exc)
        return _fallback_output(evidence, "DeepSeek was unavailable or returned invalid structured output."), "fallback"


def generate_optimization_brief(
    *, user: User, day: date, brief_type: str = AIOptimizationBrief.BriefType.ON_DEMAND
) -> AIOptimizationBrief:
    weekly = brief_type == AIOptimizationBrief.BriefType.WEEKLY
    evidence = build_evidence_pack(user=user, day=day, weekly=weekly)
    fingerprint = _fingerprint(evidence)
    brief = AIOptimizationBrief.objects.create(
        brief_type=brief_type,
        report_date=day,
        scope_key=evidence["scope_key"],
        role=user.role,
        evidence_fingerprint=fingerprint,
        evidence_snapshot=evidence,
        status=AIOptimizationBrief.Status.PENDING,
        created_by=user,
        updated_by=user,
        model=_model_name(),
    )
    output, provider_status = _deepseek_summary(evidence, weekly=weekly)
    brief.output = output
    brief.status = AIOptimizationBrief.Status.COMPLETED
    brief.provider = provider_status
    brief.generated_at = timezone.now()
    brief.save(update_fields=["output", "status", "provider", "generated_at", "updated_at"])
    record_audit(
        action=AuditLog.Action.UPDATE,
        actor=user,
        entity=brief,
        summary=f"Generated {brief.get_brief_type_display()} for {brief.scope_key}",
        after_data=model_data(brief),
    )
    return brief


def latest_brief(*, user: User) -> AIOptimizationBrief | None:
    return AIOptimizationBrief.objects.filter(
        scope_key=_scope_key(user), role=user.role, status=AIOptimizationBrief.Status.COMPLETED
    ).first()
