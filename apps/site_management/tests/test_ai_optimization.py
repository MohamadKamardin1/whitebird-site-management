from datetime import date
from unittest.mock import patch

import pytest
from django.test import override_settings

from apps.core.models import AuditLog
from apps.site_management.ai_optimization import generate_optimization_brief
from apps.site_management.models import AIOptimizationBrief


class FakeResponse:
    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return {
            "choices": [
                {
                    "message": {
                        "content": '{"headline":"Review attendance","executive_summary":"One evidence-backed summary.","priorities":[{"priority":"high","title":"Attendance review","evidence":"Attendance is below standard.","recommended_action":"Review the daily sheet.","owner_role":"Zone supervisor","due_within_days":1}],"data_quality":[],"reporting_optimizations":["Complete missing daily records."],"confidence":"high"}'
                    }
                }
            ]
        }


@pytest.mark.django_db
def test_deepseek_structured_brief_is_persisted_and_audited(admin_user) -> None:
    with override_settings(DEEPSEEK_API_KEY="test-key"):
        with patch("apps.site_management.ai_optimization.requests.post", return_value=FakeResponse()) as request:
            brief = generate_optimization_brief(user=admin_user, day=date.today())

    assert brief.status == AIOptimizationBrief.Status.COMPLETED
    assert brief.provider == "deepseek"
    assert brief.output["headline"] == "Review attendance"
    assert brief.evidence_fingerprint
    assert AuditLog.objects.filter(object_id=str(brief.pk), model_name__icontains="aioptimizationbrief").exists()
    assert request.call_args.kwargs["json"]["response_format"] == {"type": "json_object"}


@pytest.mark.django_db
def test_missing_deepseek_key_returns_safe_deterministic_brief(admin_user) -> None:
    with override_settings(DEEPSEEK_API_KEY=""):
        brief = generate_optimization_brief(user=admin_user, day=date.today())

    assert brief.status == AIOptimizationBrief.Status.COMPLETED
    assert brief.provider == "fallback"
    assert brief.output["confidence"] == "deterministic_only"
    assert "Advisory only" in brief.output["disclaimer"]
