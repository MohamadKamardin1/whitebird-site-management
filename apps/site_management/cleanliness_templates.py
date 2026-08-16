"""Ready-made daily cleanliness survey provisioning."""

from __future__ import annotations

from apps.core.models import AuditLog
from apps.core.services import model_data, record_audit

from .models import InspectionFrequency, InspectionItemType, InspectionTemplate, Site, SiteArea


DEFAULT_CLEANLINESS_AREAS = (
    ("Toilet facilities", "TOILETS"),
    ("Garden and grounds", "GARDEN"),
    ("Reception and entrance", "RECEPTION"),
    ("Shared and public areas", "PUBLIC"),
)


CLEANLINESS_ITEMS = (
    ("Area cleaned to the agreed schedule", InspectionItemType.YES_NO, "Was the area completed within the required service window?"),
    ("High-touch surfaces cleaned", InspectionItemType.YES_NO, "Check doors, handles, switches, rails, and other high-touch surfaces."),
    ("Waste removed and bins reset", InspectionItemType.YES_NO, "Confirm waste has been removed and bins are clean and correctly lined."),
    ("Consumables and hygiene supplies available", InspectionItemType.YES_NO, "Check soap, tissue, paper products, and other configured consumables."),
    ("Exception details and corrective action", InspectionItemType.TEXT, "If any item failed, record who is responsible, what was done, and the next review time."),
)


def provision_site_cleanliness_setup(*, site: Site, actor) -> int:
    """Create default operational areas when absent and then provision surveys."""
    if not site.areas.filter(is_active=True).exists():
        for area_name, area_code in DEFAULT_CLEANLINESS_AREAS:
            area = SiteArea.objects.create(
                site=site,
                area_name=area_name,
                area_code=area_code,
                description=f"Default cleanliness survey area: {area_name}.",
                created_by=actor,
                updated_by=actor,
            )
            record_audit(
                action=AuditLog.Action.CREATE,
                actor=actor,
                entity=area,
                summary=f"Provisioned default operational area {area_name} for {site.name}.",
                after_data=model_data(area),
            )
    return provision_site_cleanliness_templates(site=site, actor=actor)


def provision_site_cleanliness_templates(*, site: Site, actor) -> int:
    """Create missing daily cleanliness checklists for active site areas.

    Existing templates are never overwritten. The function is idempotent and can
    safely be called by a site-creation flow or a deployment data migration.
    """
    created_count = 0
    for area in site.areas.filter(is_active=True):
        template, created = InspectionTemplate.objects.get_or_create(
            site=site,
            area=area,
            template_name=f"Daily Cleanliness Survey · {area.area_name}",
            defaults={
                "description": "Ready-made daily cleanliness survey for operational site review.",
                "frequency": InspectionFrequency.DAILY,
                "created_by": actor,
                "updated_by": actor,
            },
        )
        if not created:
            continue
        created_count += 1
        for sequence, (label, item_type, help_text) in enumerate(CLEANLINESS_ITEMS, start=1):
            template.items.create(
                item_label=label,
                item_type=item_type,
                required=True,
                sequence=sequence,
                help_text=help_text,
            )
        record_audit(
            action=AuditLog.Action.CREATE,
            actor=actor,
            entity=template,
            summary=f"Provisioned ready-made daily cleanliness template for {site.name} / {area.area_name}.",
            after_data=model_data(template),
        )
    return created_count
