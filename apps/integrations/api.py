"""API router for external provider integrations (DeepSeek + Mapbox)."""

from __future__ import annotations

from ninja import Field, Router, Schema

from apps.accounts.models import RoleCode, User
from apps.accounts.permissions import management_required
from apps.core.errors import ForbiddenActionError
from apps.core.requests import AuthenticatedRequest

from . import deepseek, mapbox
from .transport import ProviderError


class AiSummarizeIn(Schema):
    text: str = Field(min_length=1, max_length=12000)
    instruction: str = Field(default="", max_length=500)


class AiSummarizeOut(Schema):
    summary: str


class GeoFeatureOut(Schema):
    name: str = ""
    place_name: str = ""
    longitude: float | None = None
    latitude: float | None = None


router = Router()


def _management_only(user: User) -> None:
    if not management_required(user):
        raise ForbiddenActionError("Only management roles may use this integration.")


def _management_or_viewer(user: User) -> None:
    if not (management_required(user) or user.role == RoleCode.MANAGEMENT_VIEWER):
        raise ForbiddenActionError("Only management roles may use this integration.")


@router.post("/ai/summarize", response=AiSummarizeOut, tags=["AI"])
def ai_summarize(request: AuthenticatedRequest, payload: AiSummarizeIn) -> AiSummarizeOut:
    """Summarise free text with DeepSeek (management roles only)."""
    _management_only(request.auth)
    if not deepseek.enabled():
        raise ProviderError("DeepSeek", "integration is not configured", status_code=503)
    return AiSummarizeOut(summary=deepseek.summarize(payload.text, instruction=payload.instruction))


@router.get("/geo/geocode", response=GeoFeatureOut, tags=["Geo"])
def geo_geocode(request: AuthenticatedRequest, q: str) -> GeoFeatureOut:
    """Forward-geocode a free-text query with Mapbox."""
    _management_or_viewer(request.auth)
    if not mapbox.enabled():
        raise ProviderError("Mapbox", "integration is not configured", status_code=503)
    return GeoFeatureOut(**mapbox.geocode(q) or {})


@router.get("/geo/reverse", response=GeoFeatureOut, tags=["Geo"])
def geo_reverse(request: AuthenticatedRequest, lng: float, lat: float) -> GeoFeatureOut:
    """Reverse-geocode a coordinate pair with Mapbox."""
    _management_or_viewer(request.auth)
    if not mapbox.enabled():
        raise ProviderError("Mapbox", "integration is not configured", status_code=503)
    return GeoFeatureOut(**mapbox.reverse_geocode(longitude=lng, latitude=lat) or {})
