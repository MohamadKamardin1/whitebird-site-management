from typing import Any

from django.db import migrations

AREAS = (
    ("Toilet facilities", "TOILETS"),
    ("Garden and grounds", "GARDEN"),
    ("Reception and entrance", "RECEPTION"),
    ("Shared and public areas", "PUBLIC"),
)

ITEMS = (
    ("Area cleaned to the agreed schedule", "yes_no", "Was the area completed within the required service window?"),
    ("High-touch surfaces cleaned", "yes_no", "Check doors, handles, switches, rails, and other high-touch surfaces."),
    (
        "Waste removed and bins reset",
        "yes_no",
        "Confirm waste has been removed and bins are clean and correctly lined.",
    ),
    (
        "Consumables and hygiene supplies available",
        "yes_no",
        "Check soap, tissue, paper products, and other configured consumables.",
    ),
    (
        "Exception details and corrective action",
        "text",
        "If any item failed, record who is responsible, what was done, and the next review time.",
    ),
)


def seed_cleanliness_templates(apps: Any, schema_editor: Any) -> None:
    Site = apps.get_model("site_management", "Site")
    SiteArea = apps.get_model("site_management", "SiteArea")
    InspectionTemplate = apps.get_model("site_management", "InspectionTemplate")
    InspectionTemplateItem = apps.get_model("site_management", "InspectionTemplateItem")
    for site in Site.objects.all():
        areas = list(SiteArea.objects.filter(site=site, is_active=True))
        if not areas:
            areas = [
                SiteArea.objects.create(
                    site=site,
                    area_name=name,
                    area_code=code,
                    description=f"Default cleanliness survey area: {name}.",
                )
                for name, code in AREAS
            ]
        for area in areas:
            template, created = InspectionTemplate.objects.get_or_create(
                site=site,
                area=area,
                template_name=f"Daily Cleanliness Survey · {area.area_name}",
                defaults={
                    "description": "Ready-made daily cleanliness survey for operational site review.",
                    "frequency": "daily",
                    "is_active": True,
                },
            )
            if created:
                InspectionTemplateItem.objects.bulk_create(
                    [
                        InspectionTemplateItem(
                            template=template,
                            item_label=label,
                            item_type=item_type,
                            required=True,
                            sequence=sequence,
                            help_text=help_text,
                        )
                        for sequence, (label, item_type, help_text) in enumerate(ITEMS, start=1)
                    ]
                )


def noop(apps: Any, schema_editor: Any) -> None:
    pass


class Migration(migrations.Migration):
    dependencies = [("site_management", "0017_aioptimizationbrief")]
    operations = [migrations.RunPython(seed_cleanliness_templates, noop)]
