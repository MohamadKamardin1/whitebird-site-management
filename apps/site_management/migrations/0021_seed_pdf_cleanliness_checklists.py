from typing import Any

from django.db import migrations


AREAS = (
    ("Toilets / Vyooni", "TOILETS", "Toilet facilities and hygiene supplies."),
    ("Offices / Ofisini", "OFFICES", "Office floors, furniture, equipment, and readiness."),
    ("Indoor areas / Eneo la ndani", "INDOOR", "Indoor floors, entrances, furniture, and water readiness."),
    ("Outdoor areas / Eneo la nje", "OUTDOOR", "Paths, parking, fences, grass, and surrounding areas."),
    ("Garden / Bustani", "GARDEN", "Garden maintenance, watering, pruning, and safe paths."),
    ("Store and equipment / Usimamizi wa store", "STORE", "Store keys, equipment return, cleaning, and repair separation."),
    ("Staff performance / Maendeleo ya wafanyakazi", "STAFF", "Daily staff punctuality, attendance, conduct, and task completion."),
)

ITEMS = {
    "TOILETS": (
        "Floor and wall surfaces have been washed and cleaned",
        "Mirrors have been cleaned",
        "Rubbish bin has been cleaned",
        "Toilet has been washed and cleaned",
        "Soap, brushes, and cleaning tools are washed and stored properly",
        "Water has been put into the cleaning tank",
        "Water has been put into the hand-washing container",
        "Towels have been placed",
        "Toilet paper has been placed",
    ),
    "OFFICES": (
        "Floor and wall surfaces have been cleaned",
        "Chairs, tables, and office equipment have been dusted",
        "Rubbish bin has been washed and cleaned",
        "Desk has been arranged and cleaned",
        "Floors, doors, and windows have been cleaned",
        "Tables have been arranged and curtains straightened",
        "Ceiling has been wiped and cobwebs removed",
        "Furniture has been arranged",
        "Rubbish bin has been placed",
    ),
    "INDOOR": (
        "Floor and wall surfaces have been cleaned",
        "Stairs have been cleaned before opening",
        "Rubbish bin has been cleaned",
        "Entrance has been wiped and cleaned",
        "Floors and doors have been cleaned",
        "Furniture has been arranged and curtains straightened",
        "Ceiling has been wiped and cobwebs removed",
        "Furniture has been arranged",
        "Bin has been placed",
        "Water has been put in the water container and it has been covered",
    ),
    "OUTDOOR": (
        "Grass has been cut",
        "Parking area has been cleaned",
        "Fence has been cleaned",
        "Paths and passages have been cleaned",
        "All surrounding areas have been cleaned",
        "Outdoor area has been watered",
        "Rubbish bin has been wiped and cleaned",
    ),
    "GARDEN": (
        "Grass has been cut",
        "Flower beds have been watered",
        "Flowers have been pruned",
        "Garden area has been cleared",
        "Garden area has been watered",
        "Safe paths have been created",
        "Garden has been maintained with care",
        "Branches have been cut",
        "Damaged plants have been removed or replaced",
    ),
    "STORE": (
        "Store door is locked and the key has been handed over",
        "Store door is locked and the key has been returned to the store",
        "All equipment is returned to its place and organized",
        "Used equipment has been washed and returned to the store",
        "Used equipment is returned to its proper location",
        "Equipment needing repair has been separated and reported",
    ),
    "STAFF": (
        "Worker can perform within the required time",
        "Worker is honest and hardworking",
        "Worker completes tasks before the required time",
        "Worker is present in all assigned work areas",
        "Worker does not leave the work area without informing the supervisor",
        "Worker follows instructions and performs assigned work",
    ),
}


def seed_pdf_checklists(apps: Any, schema_editor: Any) -> None:
    Site = apps.get_model("site_management", "Site")
    SiteArea = apps.get_model("site_management", "SiteArea")
    InspectionTemplate = apps.get_model("site_management", "InspectionTemplate")
    InspectionTemplateItem = apps.get_model("site_management", "InspectionTemplateItem")

    for site in Site.objects.all():
        for area_name, area_code, description in AREAS:
            area, _ = SiteArea.objects.get_or_create(
                site=site,
                area_code=area_code,
                defaults={"area_name": area_name, "description": description, "is_active": True},
            )
            template, created = InspectionTemplate.objects.get_or_create(
                site=site,
                area=area,
                template_name=f"Daily Cleanliness Survey · {area.area_name}",
                defaults={
                    "description": f"PDF-derived daily cleanliness worksheet for {area.area_name}.",
                    "frequency": "daily",
                    "is_active": True,
                },
            )
            if not created:
                continue
            InspectionTemplateItem.objects.bulk_create(
                [
                    InspectionTemplateItem(
                        template=template,
                        item_label=item_label,
                        item_type="yes_no",
                        required=True,
                        sequence=sequence,
                        help_text="Answer the row and record an exception when the check is not complete.",
                    )
                    for sequence, item_label in enumerate(ITEMS[area_code], start=1)
                ]
            )


def noop(apps: Any, schema_editor: Any) -> None:
    pass


class Migration(migrations.Migration):
    dependencies = [("site_management", "0020_seed_site_stores")]
    operations = [migrations.RunPython(seed_pdf_checklists, noop)]
